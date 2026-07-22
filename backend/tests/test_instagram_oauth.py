from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import httpx

from app.config import Settings
from app.services.instagram_oauth import (
    InstagramOAuthError,
    build_authorize_url,
    decode_state,
    encode_state,
    exchange_code_for_token,
    exchange_for_long_lived,
    parse_signed_request,
)


def _settings(**overrides) -> Settings:
    base = {
        "jwt_secret": "test-jwt-secret",
        "ig_app_id": "3345064788998743",
        "ig_app_secret": "app-secret",
    }
    return Settings(**{**base, **overrides})


class AuthorizeUrlTests(unittest.TestCase):
    def test_carries_app_id_redirect_scopes_and_state(self) -> None:
        url = build_authorize_url("app-1", "https://example.test/api/instagram/oauth/callback", "st.ate")
        query = parse_qs(urlparse(url).query)

        self.assertEqual(query["client_id"], ["app-1"])
        self.assertEqual(query["redirect_uri"], ["https://example.test/api/instagram/oauth/callback"])
        self.assertEqual(query["response_type"], ["code"])
        self.assertEqual(query["state"], ["st.ate"])
        self.assertIn("instagram_business_manage_comments", query["scope"][0])

    def test_missing_app_id_is_a_clear_error(self) -> None:
        with self.assertRaises(InstagramOAuthError):
            build_authorize_url("", "https://example.test/cb", "state")


class StateTests(unittest.TestCase):
    def test_roundtrip(self) -> None:
        settings = _settings()
        state = encode_state(settings, {"brand_id": "brand-42"})

        self.assertEqual(decode_state(settings, state)["brand_id"], "brand-42")

    def test_tampered_state_is_rejected(self) -> None:
        settings = _settings()
        body, _, signature = encode_state(settings, {"brand_id": "brand-42"}).partition(".")
        forged = base64.urlsafe_b64encode(json.dumps({"brand_id": "attacker", "iat": int(time.time())}).encode())

        with self.assertRaises(InstagramOAuthError):
            decode_state(settings, f"{forged.decode().rstrip('=')}.{signature}")

    def test_state_signed_with_another_secret_is_rejected(self) -> None:
        state = encode_state(_settings(jwt_secret="other-secret"), {"brand_id": "brand-42"})

        with self.assertRaises(InstagramOAuthError):
            decode_state(_settings(), state)

    def test_expired_state_is_rejected(self) -> None:
        settings = _settings()
        with patch("app.services.instagram_oauth.time.time", return_value=time.time() - 3600):
            state = encode_state(settings, {"brand_id": "brand-42"})

        with self.assertRaises(InstagramOAuthError):
            decode_state(settings, state)


class CodeExchangeTests(unittest.TestCase):
    def test_accepts_the_instagram_login_data_envelope(self) -> None:
        response = httpx.Response(
            200,
            json={"data": [{"access_token": "IGAA-short", "user_id": 17841408713125332, "permissions": "x"}]},
            request=httpx.Request("POST", "https://api.instagram.com/oauth/access_token"),
        )

        with patch("app.services.instagram_oauth.httpx.post", return_value=response):
            result = exchange_code_for_token("app", "secret", "https://example.test/cb", "code-1")

        self.assertEqual(result["access_token"], "IGAA-short")
        self.assertEqual(result["user_id"], "17841408713125332")

    def test_accepts_the_flat_shape(self) -> None:
        response = httpx.Response(
            200,
            json={"access_token": "IGAA-short", "user_id": 42},
            request=httpx.Request("POST", "https://api.instagram.com/oauth/access_token"),
        )

        with patch("app.services.instagram_oauth.httpx.post", return_value=response):
            result = exchange_code_for_token("app", "secret", "https://example.test/cb", "code-1")

        self.assertEqual(result["access_token"], "IGAA-short")

    def test_meta_error_message_is_surfaced(self) -> None:
        response = httpx.Response(
            400,
            json={"error_message": "Invalid platform app"},
            request=httpx.Request("POST", "https://api.instagram.com/oauth/access_token"),
        )

        with patch("app.services.instagram_oauth.httpx.post", return_value=response):
            with self.assertRaises(InstagramOAuthError) as raised:
                exchange_code_for_token("app", "secret", "https://example.test/cb", "code-1")

        self.assertIn("Invalid platform app", str(raised.exception))

    def test_network_failure_does_not_leak_the_secret(self) -> None:
        request = httpx.Request("POST", "https://api.instagram.com/oauth/access_token")
        with patch(
            "app.services.instagram_oauth.httpx.post",
            side_effect=httpx.ConnectTimeout("boom", request=request),
        ):
            with self.assertRaises(InstagramOAuthError) as raised:
                exchange_code_for_token("app", "top-secret-value", "https://example.test/cb", "code-1")

        self.assertNotIn("top-secret-value", str(raised.exception))


class LongLivedTokenTests(unittest.TestCase):
    def test_returns_token_and_lifetime(self) -> None:
        response = httpx.Response(
            200,
            json={"access_token": "IGAA-long", "token_type": "bearer", "expires_in": 5183944},
            request=httpx.Request("GET", "https://graph.instagram.com/access_token"),
        )

        with patch("app.services.instagram_oauth.httpx.get", return_value=response):
            result = exchange_for_long_lived("secret", "IGAA-short")

        self.assertEqual(result["access_token"], "IGAA-long")
        self.assertEqual(result["expires_in"], 5183944)

    def test_error_response_raises(self) -> None:
        response = httpx.Response(
            400,
            json={"error": {"message": "Invalid access token"}},
            request=httpx.Request("GET", "https://graph.instagram.com/access_token"),
        )

        with patch("app.services.instagram_oauth.httpx.get", return_value=response):
            with self.assertRaises(InstagramOAuthError) as raised:
                exchange_for_long_lived("secret", "IGAA-short")

        self.assertIn("Invalid access token", str(raised.exception))


class SignedRequestTests(unittest.TestCase):
    @staticmethod
    def _signed(secret: str, payload: dict) -> str:
        body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        signature = base64.urlsafe_b64encode(
            hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest()
        ).decode().rstrip("=")
        return f"{signature}.{body}"

    def test_valid_signature_returns_payload(self) -> None:
        signed = self._signed("app-secret", {"user_id": "17841408713125332"})

        self.assertEqual(parse_signed_request("app-secret", signed)["user_id"], "17841408713125332")

    def test_wrong_secret_is_rejected(self) -> None:
        signed = self._signed("someone-elses-secret", {"user_id": "1"})

        with self.assertRaises(InstagramOAuthError):
            parse_signed_request("app-secret", signed)

    def test_missing_signed_request_is_rejected(self) -> None:
        with self.assertRaises(InstagramOAuthError):
            parse_signed_request("app-secret", None)


if __name__ == "__main__":
    unittest.main()
