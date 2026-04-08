from django.test import TestCase
from django.urls import reverse
import json

from django.http import JsonResponse
from django.test import RequestFactory

from .decorators import admin_required
from .models import (
    Club,
    ClubMembership,
    ClubRole,
    ParentPlayerRelation,
    Team,
    TeamMembership,
    TeamRole,
    User,
)
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
        self.assertEqual(response.json()["owned_clubs"], [])
        self.assertEqual(response.json()["coached_teams"], [])
        self.assertEqual(response.json()["player_teams"], [])
        self.assertEqual(response.json()["children"], [])

    def test_me_returns_owned_clubs_and_team_lists_for_user_roles(self):
        user = User.objects.create_user(
            email="multirole@example.com",
            password="StrongPassword123!",
            first_name="Multi",
            last_name="Role",
        )
        owned_club = Club.objects.create_club(name="NetUp Volleyball Club", director=user)
        coach_club = Club.objects.create_club(
            name="Spike Academy",
            director=User.objects.create_user(
                email="director@example.com",
                password="StrongPassword123!",
                first_name="Club",
                last_name="Director",
            ),
        )
        player_club = Club.objects.create_club(
            name="Serve Stars",
            director=User.objects.create_user(
                email="director2@example.com",
                password="StrongPassword123!",
                first_name="Club",
                last_name="Director",
            ),
        )
        coached_team = Team.objects.create_team(club=coach_club, name="U18 Boys", season="2026")
        player_team = Team.objects.create_team(club=player_club, name="U16 Girls", season="2026")
        TeamMembership.objects.add_member(user=user, team=coached_team, role=TeamRole.COACH)
        TeamMembership.objects.add_member(user=user, team=player_team, role=TeamRole.PLAYER)
        token = generate_auth_token(user)

        response = self.client.get(
            reverse("core:me"),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["user"]["email"], user.email)
        self.assertEqual(len(payload["owned_clubs"]), 1)
        self.assertEqual(payload["owned_clubs"][0]["id"], owned_club.id)
        self.assertEqual(payload["owned_clubs"][0]["name"], owned_club.name)
        self.assertEqual(len(payload["coached_teams"]), 1)
        self.assertEqual(payload["coached_teams"][0]["id"], coached_team.id)
        self.assertEqual(payload["coached_teams"][0]["club_id"], coach_club.id)
        self.assertEqual(len(payload["player_teams"]), 1)
        self.assertEqual(payload["player_teams"][0]["id"], player_team.id)
        self.assertEqual(payload["player_teams"][0]["club_id"], player_club.id)
        self.assertEqual(payload["children"], [])

    def test_me_returns_child_player_teams_for_parent(self):
        parent = User.objects.create_user(
            email="parent@example.com",
            password="StrongPassword123!",
            first_name="Parent",
            last_name="User",
        )
        child = User.objects.create_user(
            email="child@example.com",
            password="StrongPassword123!",
            first_name="Child",
            last_name="Player",
        )
        club = Club.objects.create_club(
            name="Family Club",
            director=User.objects.create_user(
                email="familydirector@example.com",
                password="StrongPassword123!",
                first_name="Family",
                last_name="Director",
            ),
        )
        child_team = Team.objects.create_team(club=club, name="U14 Mixed", season="2026")
        TeamMembership.objects.add_member(user=child, team=child_team, role=TeamRole.PLAYER)
        ParentPlayerRelation.objects.link(parent=parent, player=child)
        token = generate_auth_token(parent)

        response = self.client.get(
            reverse("core:me"),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["player_teams"], [])
        self.assertEqual(len(payload["children"]), 1)
        self.assertEqual(payload["children"][0]["user"]["id"], child.id)
        self.assertEqual(payload["children"][0]["user"]["email"], child.email)
        self.assertEqual(len(payload["children"][0]["teams"]), 1)
        self.assertEqual(payload["children"][0]["teams"][0]["id"], child_team.id)
        self.assertEqual(payload["children"][0]["teams"][0]["club_id"], club.id)

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


class ViewTeamMembersEndpointTests(TestCase):
    def test_view_team_members_returns_active_members_for_authenticated_user(self):
        requester = User.objects.create_user(
            email="viewer@example.com",
            password="StrongPassword123!",
            first_name="View",
            last_name="Only",
        )
        director = User.objects.create_user(
            email="director@example.com",
            password="StrongPassword123!",
            first_name="Club",
            last_name="Director",
        )
        coach = User.objects.create_user(
            email="coach@example.com",
            password="StrongPassword123!",
            first_name="Coach",
            last_name="User",
        )
        player = User.objects.create_user(
            email="player@example.com",
            password="StrongPassword123!",
            first_name="Player",
            last_name="User",
        )
        inactive_player = User.objects.create_user(
            email="inactive@example.com",
            password="StrongPassword123!",
            first_name="Inactive",
            last_name="Player",
        )
        club = Club.objects.create_club(name="NetUp Volleyball Club", director=director)
        team = Team.objects.create_team(club=club, name="U16 Girls", season="2026")
        TeamMembership.objects.add_member(user=coach, team=team, role=TeamRole.COACH)
        TeamMembership.objects.add_member(
            user=player,
            team=team,
            role=TeamRole.PLAYER,
            is_captain=True,
        )
        inactive_membership = TeamMembership.objects.add_member(
            user=inactive_player,
            team=team,
            role=TeamRole.PLAYER,
        )
        TeamMembership.objects.deactivate(inactive_membership)
        token = generate_auth_token(requester)

        response = self.client.get(
            reverse("core:view-team-members", kwargs={"team_id": team.id}),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["team"]["id"], team.id)
        self.assertEqual(payload["team"]["name"], team.name)
        self.assertEqual(len(payload["members"]), 2)
        self.assertEqual(payload["members"][0]["membership"]["role"], TeamRole.COACH)
        self.assertEqual(payload["members"][0]["user"]["id"], coach.id)
        self.assertEqual(payload["members"][1]["membership"]["role"], TeamRole.PLAYER)
        self.assertEqual(payload["members"][1]["user"]["id"], player.id)
        self.assertTrue(payload["members"][1]["membership"]["is_captain"])

    def test_view_team_members_requires_authentication(self):
        director = User.objects.create_user(
            email="director@example.com",
            password="StrongPassword123!",
            first_name="Club",
            last_name="Director",
        )
        club = Club.objects.create_club(name="NetUp Volleyball Club", director=director)
        team = Team.objects.create_team(club=club, name="U16 Girls", season="2026")

        response = self.client.get(
            reverse("core:view-team-members", kwargs={"team_id": team.id}),
        )

        self.assertEqual(response.status_code, 401)


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
