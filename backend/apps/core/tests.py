from django.test import TestCase
from django.urls import reverse
import json

from django.http import JsonResponse
from django.test import RequestFactory

from .decorators import admin_required
from .models import Club, ClubMembership, ClubRole, Team, User
from .tokens import generate_auth_token, verify_auth_token


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


class LoginEndpointTests(TestCase):
    def test_login_returns_token_for_valid_credentials(self):
        user = User.objects.create_user(
            email="coach@example.com",
            password="StrongPassword123!",
            first_name="Coach",
            last_name="User",
        )

        response = self.client.post(
            reverse("core:login"),
            data=json.dumps(
                {
                    "email": "coach@example.com",
                    "password": "StrongPassword123!",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        token = response.json()["token"]
        payload = verify_auth_token(token)
        self.assertEqual(payload["user_id"], user.id)
        self.assertEqual(payload["email"], user.email)

    def test_login_rejects_invalid_credentials(self):
        User.objects.create_user(
            email="coach@example.com",
            password="StrongPassword123!",
            first_name="Coach",
            last_name="User",
        )

        response = self.client.post(
            reverse("core:login"),
            data=json.dumps(
                {
                    "email": "coach@example.com",
                    "password": "WrongPassword!",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 401)


class LoginRequiredDecoratorTests(TestCase):
    def test_me_returns_authenticated_user_for_valid_bearer_token(self):
        user = User.objects.create_user(
            email="player@example.com",
            password="StrongPassword123!",
            first_name="Ronnie",
            last_name="Saba",
        )
        token = generate_auth_token(user)

        response = self.client.get(
            reverse("core:me"),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user"]["email"], user.email)

    def test_me_rejects_missing_authorization_header(self):
        response = self.client.get(reverse("core:me"))

        self.assertEqual(response.status_code, 401)

    def test_me_rejects_invalid_token(self):
        response = self.client.get(
            reverse("core:me"),
            HTTP_AUTHORIZATION="Bearer invalid-token",
        )

        self.assertEqual(response.status_code, 401)


class CreateClubEndpointTests(TestCase):
    def test_create_club_creates_club_and_assigns_creator_as_director(self):
        user = User.objects.create_user(
            email="director@example.com",
            password="StrongPassword123!",
            first_name="Club",
            last_name="Director",
        )
        token = generate_auth_token(user)

        response = self.client.post(
            reverse("core:create-club"),
            data=json.dumps(
                {
                    "name": "NetUp Volleyball Club",
                    "short_name": "NetUp",
                    "city": "Beirut",
                    "country": "Lebanon",
                    "contact_email": "info@netup.com",
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Club.objects.count(), 1)

        club = Club.objects.get(name="NetUp Volleyball Club")
        self.assertTrue(
            ClubMembership.objects.filter(
                user=user,
                club=club,
                role=ClubRole.CLUB_DIRECTOR,
                is_active=True,
            ).exists()
        )

    def test_create_club_requires_authentication(self):
        response = self.client.post(
            reverse("core:create-club"),
            data=json.dumps({"name": "NetUp Volleyball Club"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 401)


class CreateTeamEndpointTests(TestCase):
    def test_create_team_allows_club_director(self):
        user = User.objects.create_user(
            email="director@example.com",
            password="StrongPassword123!",
            first_name="Club",
            last_name="Director",
        )
        club = Club.objects.create_club(name="NetUp Volleyball Club", director=user)
        token = generate_auth_token(user)

        response = self.client.post(
            reverse("core:create-team", kwargs={"club_id": club.id}),
            data=json.dumps(
                {
                    "name": "U16 Girls",
                    "short_name": "U16G",
                    "season": "2026",
                    "age_group": "U16",
                    "gender": "girls",
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(Team.objects.filter(club=club, name="U16 Girls").exists())

    def test_create_team_rejects_user_who_cannot_manage_club(self):
        director = User.objects.create_user(
            email="director@example.com",
            password="StrongPassword123!",
            first_name="Club",
            last_name="Director",
        )
        other_user = User.objects.create_user(
            email="player@example.com",
            password="StrongPassword123!",
            first_name="Player",
            last_name="User",
        )
        club = Club.objects.create_club(name="NetUp Volleyball Club", director=director)
        token = generate_auth_token(other_user)

        response = self.client.post(
            reverse("core:create-team", kwargs={"club_id": club.id}),
            data=json.dumps({"name": "U16 Girls"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 403)


class UpdateTeamDetailsEndpointTests(TestCase):
    def test_update_team_details_allows_club_director(self):
        director = User.objects.create_user(
            email="director@example.com",
            password="StrongPassword123!",
            first_name="Club",
            last_name="Director",
        )
        club = Club.objects.create_club(name="NetUp Volleyball Club", director=director)
        team = Team.objects.create_team(club=club, name="U16 Girls", season="2026")
        token = generate_auth_token(director)

        response = self.client.patch(
            reverse("core:update-team-details", kwargs={"team_id": team.id}),
            data=json.dumps({"home_venue": "Main Gym", "season": "2027"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 200)

    def test_update_team_details_allows_coach_of_team(self):
        director = User.objects.create_user(
            email="director@example.com",
            password="StrongPassword123!",
            first_name="Club",
            last_name="Director",
        )
        coach = User.objects.create_user(
            email="coach@example.com",
            password="StrongPassword123!",
            first_name="Team",
            last_name="Coach",
        )
        club = Club.objects.create_club(name="NetUp Volleyball Club", director=director)
        team = Team.objects.create_team(club=club, name="U16 Girls")
        TeamMembership.objects.add_member(user=coach, team=team, role=TeamRole.COACH)
        token = generate_auth_token(coach)

        response = self.client.patch(
            reverse("core:update-team-details", kwargs={"team_id": team.id}),
            data=json.dumps({"home_venue": "Secondary Gym"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 200)

    def test_update_team_details_rejects_user_without_permission(self):
        director = User.objects.create_user(
            email="director@example.com",
            password="StrongPassword123!",
            first_name="Club",
            last_name="Director",
        )
        other_user = User.objects.create_user(
            email="player@example.com",
            password="StrongPassword123!",
            first_name="Player",
            last_name="User",
        )
        club = Club.objects.create_club(name="NetUp Volleyball Club", director=director)
        team = Team.objects.create_team(club=club, name="U16 Girls")
        token = generate_auth_token(other_user)

        response = self.client.patch(
            reverse("core:update-team-details", kwargs={"team_id": team.id}),
            data=json.dumps({"home_venue": "Secondary Gym"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 403)


class AdminRequiredDecoratorTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_admin_required_allows_staff_user_with_valid_token(self):
        user = User.objects.create_user(
            email="director@example.com",
            password="StrongPassword123!",
            first_name="Club",
            last_name="Director",
            is_staff=True,
        )
        token = generate_auth_token(user)

        @admin_required
        def protected_view(request):
            return JsonResponse({"ok": True})

        request = self.factory.get(
            "/api/auth/admin-only/",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        response = protected_view(request)

        self.assertEqual(response.status_code, 200)

    def test_admin_required_rejects_non_staff_user(self):
        user = User.objects.create_user(
            email="coach@example.com",
            password="StrongPassword123!",
            first_name="Coach",
            last_name="User",
        )
        token = generate_auth_token(user)

        @admin_required
        def protected_view(request):
            return JsonResponse({"ok": True})

        request = self.factory.get(
            "/api/auth/admin-only/",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        response = protected_view(request)

        self.assertEqual(response.status_code, 403)
