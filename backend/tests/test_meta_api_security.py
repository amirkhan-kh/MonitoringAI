from __future__ import annotations

import unittest
from unittest.mock import patch

import httpx

from app.services.facebook_api import FacebookApi, FacebookApiError, detect_page
from app.services.instagram_api import (
    InstagramApi,
    InstagramApiError,
    detect_account,
    exchange_long_lived_token,
)
from app.workers.facebook_worker import _is_auth_error as is_facebook_auth_error
from app.workers.instagram_worker import _is_auth_error as is_instagram_auth_error


class InstagramApiSecurityTests(unittest.TestCase):
    def test_network_error_does_not_expose_access_token(self) -> None:
        access_token = "secret-instagram-access-token"
        request = httpx.Request(
            "GET",
            f"https://graph.facebook.com/v21.0/me?access_token={access_token}",
        )

        with patch(
            "app.services.instagram_api.httpx.get",
            side_effect=httpx.ConnectTimeout(
                f"request failed for access_token={access_token}",
                request=request,
            ),
        ):
            with self.assertRaises(InstagramApiError) as raised:
                InstagramApi(access_token).get_account("123")

        self.assertEqual(str(raised.exception), "Instagram Graph API request failed (network error)")
        self.assertNotIn(access_token, str(raised.exception))
        self.assertIsNone(raised.exception.__cause__)

    def test_http_error_does_not_expose_response_body_or_query_token(self) -> None:
        access_token = "secret-instagram-access-token"
        response = httpx.Response(
            400,
            json={"error": {"message": f"Bad token {access_token}", "code": 190}},
        )

        with patch("app.services.instagram_api.httpx.get", return_value=response) as mocked_get:
            with self.assertRaises(InstagramApiError) as raised:
                InstagramApi(access_token).get_account("123")

        error = raised.exception
        self.assertEqual(error.status_code, 400)
        self.assertEqual(error.error_code, 190)
        self.assertNotIn(access_token, str(error))
        self.assertNotIn("Bad token", str(error))
        _, kwargs = mocked_get.call_args
        self.assertNotIn("access_token", kwargs["params"])
        self.assertEqual(kwargs["headers"]["Authorization"], f"Bearer {access_token}")

    def test_detection_error_is_safe_when_meta_echoes_token(self) -> None:
        access_token = "secret-instagram-detection-token"
        responses = [
            httpx.Response(
                400,
                json={"error": {"message": access_token, "code": 190}},
            )
            for _ in range(3)
        ]

        with patch("app.services.instagram_api.httpx.get", side_effect=responses) as mocked_get:
            with self.assertRaises(InstagramApiError) as raised:
                detect_account(access_token)

        self.assertNotIn(access_token, str(raised.exception))
        self.assertIn("Meta code 190", str(raised.exception))
        for call in mocked_get.call_args_list:
            self.assertNotIn("access_token", call.kwargs["params"])

    def test_token_exchange_failure_does_not_expose_secrets(self) -> None:
        app_secret = "secret-meta-app-secret"
        short_token = "secret-short-access-token"
        response = httpx.Response(
            400,
            json={"error": {"message": f"{app_secret} {short_token}", "code": 190}},
        )

        with patch("app.services.instagram_api.httpx.post", return_value=response) as mocked_post:
            with self.assertRaises(InstagramApiError) as raised:
                exchange_long_lived_token("123", app_secret, short_token)

        self.assertNotIn(app_secret, str(raised.exception))
        self.assertNotIn(short_token, str(raised.exception))
        self.assertEqual(raised.exception.error_code, 190)
        url = mocked_post.call_args.args[0]
        self.assertNotIn(app_secret, url)
        self.assertNotIn(short_token, url)


class FacebookApiSecurityTests(unittest.TestCase):
    def test_network_error_does_not_expose_access_token(self) -> None:
        access_token = "secret-facebook-access-token"
        request = httpx.Request(
            "GET",
            f"https://graph.facebook.com/v21.0/me?access_token={access_token}",
        )

        with patch(
            "app.services.facebook_api.httpx.get",
            side_effect=httpx.ConnectError(
                f"request failed for access_token={access_token}",
                request=request,
            ),
        ):
            with self.assertRaises(FacebookApiError) as raised:
                FacebookApi(access_token).get_page("123")

        self.assertEqual(str(raised.exception), "Facebook Graph API request failed (network error)")
        self.assertNotIn(access_token, str(raised.exception))
        self.assertIsNone(raised.exception.__cause__)

    def test_http_error_does_not_expose_response_body_or_query_token(self) -> None:
        access_token = "secret-facebook-access-token"
        response = httpx.Response(
            400,
            json={"error": {"message": f"Bad token {access_token}", "code": 190}},
        )

        with patch("app.services.facebook_api.httpx.get", return_value=response) as mocked_get:
            with self.assertRaises(FacebookApiError) as raised:
                FacebookApi(access_token).get_page("123")

        error = raised.exception
        self.assertEqual(error.status_code, 400)
        self.assertEqual(error.error_code, 190)
        self.assertNotIn(access_token, str(error))
        self.assertNotIn("Bad token", str(error))
        _, kwargs = mocked_get.call_args
        self.assertNotIn("access_token", kwargs["params"])
        self.assertEqual(kwargs["headers"]["Authorization"], f"Bearer {access_token}")

    def test_detection_error_is_safe_when_meta_echoes_token(self) -> None:
        access_token = "secret-facebook-detection-token"
        responses = [
            httpx.Response(
                400,
                json={"error": {"message": access_token, "code": 190}},
            )
            for _ in range(2)
        ]

        with patch("app.services.facebook_api.httpx.get", side_effect=responses) as mocked_get:
            with self.assertRaises(FacebookApiError) as raised:
                detect_page(access_token)

        self.assertNotIn(access_token, str(raised.exception))
        self.assertIn("Meta code 190", str(raised.exception))
        for call in mocked_get.call_args_list:
            self.assertNotIn("access_token", call.kwargs["params"])

    def test_meta_code_190_is_classified_as_auth_error(self) -> None:
        instagram_error = InstagramApiError(
            "Instagram Graph API request failed (HTTP 400) (Meta code 190)",
            status_code=400,
            error_code=190,
        )
        facebook_error = FacebookApiError(
            "Facebook Graph API request failed (HTTP 400) (Meta code 190)",
            status_code=400,
            error_code=190,
        )

        self.assertTrue(is_instagram_auth_error(instagram_error))
        self.assertTrue(is_facebook_auth_error(facebook_error))


if __name__ == "__main__":
    unittest.main()
