import json
import time

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase, override_settings


User = get_user_model()


@override_settings(
    LOGIN_RATE_LIMIT_MAX_ATTEMPTS=5,
    LOGIN_RATE_LIMIT_WINDOW_SECONDS=1,
)
class LoginRateLimitTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()
        self.email = "ratelimit@test.local"
        self.password = "StrongPass123!"
        User.objects.create_user(
            email=self.email,
            password=self.password,
            first_name="Rate",
            last_name="Tester",
        )

    def _login(self, email, password):
        return self.client.post(
            "/api/auth/login/",
            data=json.dumps({"email": email, "password": password}),
            content_type="application/json",
        )

    def test_first_five_failed_attempts_allowed_sixth_blocked(self):
        for _ in range(5):
            response = self._login(self.email, "WrongPass123!")
            self.assertEqual(response.status_code, 401)

        blocked_response = self._login(self.email, "WrongPass123!")
        self.assertEqual(blocked_response.status_code, 429)
        self.assertIn("Too many login attempts", blocked_response.json()["errors"]["auth"])

    def test_attempts_allowed_again_after_window_expires(self):
        for _ in range(5):
            self._login(self.email, "WrongPass123!")

        blocked_response = self._login(self.email, "WrongPass123!")
        self.assertEqual(blocked_response.status_code, 429)

        time.sleep(1.1)
        response_after_window = self._login(self.email, "WrongPass123!")
        self.assertEqual(response_after_window.status_code, 401)

    def test_successful_login_still_works_under_limit(self):
        response = self._login(self.email, self.password)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("token", body)
