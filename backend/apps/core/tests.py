from django.test import TestCase
from django.urls import reverse
import json

from .models import User


class RegisterEndpointTests(TestCase):
    def test_register_creates_user(self):
        response = self.client.post(
            reverse("core:register"),
            data=json.dumps(
                {
                    "email": "player@example.com",
                    "password": "StrongPassword123!",
                    "first_name": "Ronnie",
                    "last_name": "Saba",
                    "date_of_birth": "2005-04-01",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(User.objects.count(), 1)

        user = User.objects.get(email="player@example.com")
        self.assertEqual(user.first_name, "Ronnie")
        self.assertEqual(user.last_name, "Saba")
        self.assertTrue(user.check_password("StrongPassword123!"))

    def test_register_rejects_duplicate_email(self):
        User.objects.create_user(
            email="player@example.com",
            password="StrongPassword123!",
            first_name="Existing",
            last_name="User",
        )

        response = self.client.post(
            reverse("core:register"),
            data=json.dumps(
                {
                    "email": "player@example.com",
                    "password": "AnotherStrongPassword123!",
                    "first_name": "Ronnie",
                    "last_name": "Saba",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(User.objects.count(), 1)
