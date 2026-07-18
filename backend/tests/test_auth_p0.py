from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi import HTTPException
from starlette.requests import Request

from app.config import Settings
from app.main import facebook_webhook_receive, instagram_webhook_receive, require_auth
from app.services.auth import create_token


def build_request(
    path: str,
    *,
    method: str = "GET",
    query_string: bytes = b"",
    authorization: str | None = None,
) -> Request:
    headers = []
    if authorization:
        headers.append((b"authorization", authorization.encode()))
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": query_string,
            "headers": headers,
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
        }
    )


class AuthTokenTransportTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.settings = Settings(
            _env_file=None,
            auth_enabled=True,
            jwt_secret="unit-test-secret",
            admin_username="admin",
            admin_password="password",
        )
        self.token, _ = create_token(self.settings, "admin")

    async def test_events_rejects_query_string_token(self) -> None:
        request = build_request("/events", query_string=f"access_token={self.token}".encode())

        with patch("app.main.get_settings", return_value=self.settings):
            with self.assertRaises(HTTPException) as raised:
                await require_auth(request)

        self.assertEqual(raised.exception.status_code, 401)

    async def test_events_accepts_bearer_header(self) -> None:
        request = build_request("/events", authorization=f"Bearer {self.token}")

        with patch("app.main.get_settings", return_value=self.settings):
            await require_auth(request)

    async def test_facebook_webhook_is_public_to_dashboard_auth(self) -> None:
        request = build_request("/facebook/webhook")

        with patch("app.main.get_settings", return_value=self.settings):
            await require_auth(request)


class MetaWebhookSignatureTests(unittest.IsolatedAsyncioTestCase):
    async def test_instagram_post_fails_closed_without_app_secret(self) -> None:
        settings = Settings(_env_file=None, ig_app_secret="")

        with patch("app.main.get_settings", return_value=settings):
            with self.assertRaises(HTTPException) as raised:
                await instagram_webhook_receive(build_request("/instagram/webhook", method="POST"))

        self.assertEqual(raised.exception.status_code, 503)

    async def test_facebook_post_fails_closed_without_app_secret(self) -> None:
        settings = Settings(_env_file=None, fb_app_secret="")

        with patch("app.main.get_settings", return_value=settings):
            with self.assertRaises(HTTPException) as raised:
                await facebook_webhook_receive(build_request("/facebook/webhook", method="POST"))

        self.assertEqual(raised.exception.status_code, 503)


if __name__ == "__main__":
    unittest.main()
