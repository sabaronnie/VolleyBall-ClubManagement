from datetime import date
from decimal import Decimal
import json

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from django.http import JsonResponse
from django.test import RequestFactory

from .decorators import admin_required
from .models import (
    AssignedAccountRole,
    Club,
    ClubMembership,
    ClubRole,
    DirectorPaymentAuditLog,
    ParentLinkApprovalStatus,
    ParentPlayerRelation,
    PaymentSchedule,
    PlayerAccessPolicy,
    PlayerFeeRecord,
    PlayerProfile,
    Team,
    TeamMembership,
    TeamRole,
    User,
    VerificationStatus,
)
from .permissions import (
    can_player_make_payments,
    can_player_update_own_emergency_contact,
    is_player_parent_managed,
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
        self.assertIn("pending", response.json()["message"].lower())
        self.assertEqual(response.json()["user"]["verification_status"], VerificationStatus.PENDING)

        user = User.objects.get(email="player@example.com")
        self.assertEqual(user.first_name, "Ronnie")
        self.assertEqual(user.last_name, "Saba")
        self.assertTrue(user.check_password("StrongPassword123!"))
        self.assertEqual(user.verification_status, VerificationStatus.PENDING)
        self.assertIsNotNone(user.date_of_birth)

    def test_register_requires_date_of_birth(self):
        response = self.client.post(
            reverse("core:register"),
            data=json.dumps(
                {
                    "email": "nodob@example.com",
                    "password": "StrongPassword123!",
                    "first_name": "No",
                    "last_name": "Dob",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("date_of_birth", response.json().get("errors", {}))
        self.assertEqual(User.objects.filter(email="nodob@example.com").count(), 0)

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
                    "date_of_birth": "2004-06-15",
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

    def test_login_rejects_pending_verification(self):
        User.objects.create_user(
            email="pending@example.com",
            password="StrongPassword123!",
            first_name="Wait",
            last_name="User",
            verification_status=VerificationStatus.PENDING,
        )

        response = self.client.post(
            reverse("core:login"),
            data=json.dumps(
                {
                    "email": "pending@example.com",
                    "password": "StrongPassword123!",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertIn("pending", response.json()["errors"]["verification"].lower())


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
        profile = response.json().get("account_profile") or {}
        self.assertIn("roles", profile)
        self.assertIn("display_role", profile)
        self.assertIn("pending_fees", profile)
        self.assertIn("linked_parents", profile)
        self.assertIn("linked_children", profile)
        self.assertIn("is_director_or_staff", response.json())
        self.assertFalse(response.json()["is_director_or_staff"])
        self.assertIn("viewer_is_staff", response.json())
        self.assertFalse(response.json()["viewer_is_staff"])
        self.assertEqual(response.json()["user"]["id"], user.id)

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

    def test_create_team_allows_coach_who_coaches_in_club(self):
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
        club = Club.objects.create_club(name="NetUp Volleyball Club", director=director)
        existing = Team.objects.create_team(club=club, name="U16 Girls", season="2026")
        TeamMembership.objects.add_member(user=coach, team=existing, role=TeamRole.COACH)
        token = generate_auth_token(coach)

        response = self.client.post(
            reverse("core:create-team", kwargs={"club_id": club.id}),
            data=json.dumps(
                {
                    "name": "U18 Girls",
                    "short_name": "U18G",
                    "season": "2026",
                    "age_group": "U18",
                    "gender": "girls",
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 201)
        new_team = Team.objects.get(club=club, name="U18 Girls")
        self.assertTrue(
            TeamMembership.objects.active()
            .filter(user=coach, team=new_team, role=TeamRole.COACH)
            .exists()
        )


class ViewTeamMembersEndpointTests(TestCase):
    def test_view_team_members_returns_active_members_for_authenticated_user(self):
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
        token = generate_auth_token(director)

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
        self.assertTrue(payload["can_add_player"])
        self.assertTrue(payload["can_add_coach"])
        self.assertTrue(payload["can_manage_team"])

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

    def test_view_team_members_forbidden_for_unrelated_user(self):
        director = User.objects.create_user(
            email="dir2@example.com",
            password="StrongPassword123!",
        )
        stranger = User.objects.create_user(
            email="stranger@example.com",
            password="StrongPassword123!",
        )
        club = Club.objects.create_club(name="Private Club", director=director)
        team = Team.objects.create_team(club=club, name="T1", season="2026")
        token = generate_auth_token(stranger)
        response = self.client.get(
            reverse("core:view-team-members", kwargs={"team_id": team.id}),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 403)


class AddTeamMemberEndpointTests(TestCase):
    def test_club_director_can_add_coach_to_team(self):
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
        club = Club.objects.create_club(name="NetUp Volleyball Club", director=director)
        team = Team.objects.create_team(club=club, name="U16 Girls", season="2026")
        token = generate_auth_token(director)

        response = self.client.post(
            reverse("core:add-team-member", kwargs={"team_id": team.id}),
            data=json.dumps({"user_id": coach.id, "role": TeamRole.COACH}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            TeamMembership.objects.filter(
                user=coach,
                team=team,
                role=TeamRole.COACH,
                is_active=True,
            ).exists()
        )

    def test_club_director_can_add_player_to_team(self):
        director = User.objects.create_user(
            email="director@example.com",
            password="StrongPassword123!",
            first_name="Club",
            last_name="Director",
        )
        player = User.objects.create_user(
            email="player@example.com",
            password="StrongPassword123!",
            first_name="Player",
            last_name="User",
        )
        club = Club.objects.create_club(name="NetUp Volleyball Club", director=director)
        team = Team.objects.create_team(club=club, name="U16 Girls", season="2026")
        token = generate_auth_token(director)

        response = self.client.post(
            reverse("core:add-team-member", kwargs={"team_id": team.id}),
            data=json.dumps({"user_id": player.id, "role": TeamRole.PLAYER}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            TeamMembership.objects.filter(
                user=player,
                team=team,
                role=TeamRole.PLAYER,
                is_active=True,
            ).exists()
        )

    def test_add_player_schedules_next_month_default_monthly_fee(self):
        director = User.objects.create_user(
            email="director-feejoin@example.com",
            password="StrongPassword123!",
            first_name="Club",
            last_name="Director",
        )
        player = User.objects.create_user(
            email="player-feejoin@example.com",
            password="StrongPassword123!",
            first_name="Player",
            last_name="User",
        )
        club = Club.objects.create_club(name="NetUp Fee Join Club", director=director)
        team = Team.objects.create_team(club=club, name="U16 Fee Join", season="2026")
        token = generate_auth_token(director)

        response = self.client.post(
            reverse("core:add-team-member", kwargs={"team_id": team.id}),
            data=json.dumps({"user_id": player.id, "role": TeamRole.PLAYER}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 201)
        today = timezone.localdate()
        if today.month == 12:
            expected_first = date(today.year + 1, 1, 1)
        else:
            expected_first = date(today.year, today.month + 1, 1)
        rec = PlayerFeeRecord.objects.get(club=club, player=player, team=team)
        self.assertEqual(rec.due_date, expected_first)
        self.assertEqual(rec.billing_period_start, expected_first)
        self.assertEqual(rec.amount_due, Decimal("75.00"))

    def test_coach_can_add_player_to_team(self):
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
        club = Club.objects.create_club(name="NetUp Volleyball Club", director=director)
        team = Team.objects.create_team(club=club, name="U16 Girls", season="2026")
        TeamMembership.objects.add_member(user=coach, team=team, role=TeamRole.COACH)
        token = generate_auth_token(coach)

        response = self.client.post(
            reverse("core:add-team-member", kwargs={"team_id": team.id}),
            data=json.dumps({"user_id": player.id, "role": TeamRole.PLAYER}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            TeamMembership.objects.filter(
                user=player,
                team=team,
                role=TeamRole.PLAYER,
                is_active=True,
            ).exists()
        )

    def test_coach_cannot_add_coach_to_team(self):
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
        other_coach = User.objects.create_user(
            email="coach2@example.com",
            password="StrongPassword123!",
            first_name="Other",
            last_name="Coach",
        )
        club = Club.objects.create_club(name="NetUp Volleyball Club", director=director)
        team = Team.objects.create_team(club=club, name="U16 Girls", season="2026")
        TeamMembership.objects.add_member(user=coach, team=team, role=TeamRole.COACH)
        token = generate_auth_token(coach)

        response = self.client.post(
            reverse("core:add-team-member", kwargs={"team_id": team.id}),
            data=json.dumps({"user_id": other_coach.id, "role": TeamRole.COACH}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            TeamMembership.objects.filter(
                user=other_coach,
                team=team,
                is_active=True,
            ).exists()
        )


class TeamCaptainEndpointTests(TestCase):
    def test_club_director_can_set_player_as_captain(self):
        director = User.objects.create_user(
            email="director@example.com",
            password="StrongPassword123!",
            first_name="Club",
            last_name="Director",
        )
        player = User.objects.create_user(
            email="player@example.com",
            password="StrongPassword123!",
            first_name="Player",
            last_name="User",
        )
        club = Club.objects.create_club(name="NetUp Volleyball Club", director=director)
        team = Team.objects.create_team(club=club, name="U16 Girls", season="2026")
        TeamMembership.objects.add_member(user=player, team=team, role=TeamRole.PLAYER)
        token = generate_auth_token(director)

        response = self.client.post(
            reverse("core:set-team-captain", kwargs={"team_id": team.id, "player_id": player.id}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 200)
        membership = TeamMembership.objects.get(user=player, team=team)
        self.assertTrue(membership.is_captain)

    def test_coach_can_remove_player_as_captain(self):
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
        club = Club.objects.create_club(name="NetUp Volleyball Club", director=director)
        team = Team.objects.create_team(club=club, name="U16 Girls", season="2026")
        TeamMembership.objects.add_member(user=coach, team=team, role=TeamRole.COACH)
        TeamMembership.objects.add_member(
            user=player,
            team=team,
            role=TeamRole.PLAYER,
            is_captain=True,
        )
        token = generate_auth_token(coach)

        response = self.client.delete(
            reverse(
                "core:remove-team-captain",
                kwargs={"team_id": team.id, "player_id": player.id},
            ),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 200)
        membership = TeamMembership.objects.get(user=player, team=team)
        self.assertFalse(membership.is_captain)

    def test_cannot_set_captain_for_non_player_membership(self):
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
        club = Club.objects.create_club(name="NetUp Volleyball Club", director=director)
        team = Team.objects.create_team(club=club, name="U16 Girls", season="2026")
        TeamMembership.objects.add_member(user=coach, team=team, role=TeamRole.COACH)
        token = generate_auth_token(director)

        response = self.client.post(
            reverse("core:set-team-captain", kwargs={"team_id": team.id, "player_id": coach.id}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 404)


class RemoveTeamMemberEndpointTests(TestCase):
    def test_club_director_can_remove_coach_team_membership(self):
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
        club = Club.objects.create_club(name="NetUp Volleyball Club", director=director)
        team = Team.objects.create_team(club=club, name="U16 Girls", season="2026")
        TeamMembership.objects.add_member(user=coach, team=team, role=TeamRole.COACH)
        token = generate_auth_token(director)

        response = self.client.delete(
            reverse("core:remove-team-member", kwargs={"team_id": team.id, "target_user_id": coach.id}),
            data=json.dumps({}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            TeamMembership.objects.filter(
                user=coach,
                team=team,
                is_active=True,
            ).exists()
        )

    def test_coach_can_remove_player_team_membership(self):
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
        club = Club.objects.create_club(name="NetUp Volleyball Club", director=director)
        team = Team.objects.create_team(club=club, name="U16 Girls", season="2026")
        TeamMembership.objects.add_member(user=coach, team=team, role=TeamRole.COACH)
        TeamMembership.objects.add_member(user=player, team=team, role=TeamRole.PLAYER)
        token = generate_auth_token(coach)

        response = self.client.delete(
            reverse("core:remove-team-member", kwargs={"team_id": team.id, "target_user_id": player.id}),
            data=json.dumps({}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            TeamMembership.objects.filter(
                user=player,
                team=team,
                is_active=True,
            ).exists()
        )

    def test_coach_cannot_remove_parent_because_parent_has_no_team_membership(self):
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
        parent = User.objects.create_user(
            email="parent@example.com",
            password="StrongPassword123!",
            first_name="Parent",
            last_name="User",
        )
        player = User.objects.create_user(
            email="player@example.com",
            password="StrongPassword123!",
            first_name="Player",
            last_name="User",
        )
        club = Club.objects.create_club(name="NetUp Volleyball Club", director=director)
        team = Team.objects.create_team(club=club, name="U16 Girls", season="2026")
        TeamMembership.objects.add_member(user=coach, team=team, role=TeamRole.COACH)
        TeamMembership.objects.add_member(user=player, team=team, role=TeamRole.PLAYER)
        relation, _ = ParentPlayerRelation.objects.link(parent=parent, player=player)
        token = generate_auth_token(coach)

        response = self.client.delete(
            reverse("core:remove-team-member", kwargs={"team_id": team.id, "target_user_id": parent.id}),
            data=json.dumps({}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 404)
        relation.refresh_from_db()
        self.assertTrue(relation.is_active)

    def test_coach_cannot_remove_coach_team_membership(self):
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
        other_coach = User.objects.create_user(
            email="coach2@example.com",
            password="StrongPassword123!",
            first_name="Other",
            last_name="Coach",
        )
        club = Club.objects.create_club(name="NetUp Volleyball Club", director=director)
        team = Team.objects.create_team(club=club, name="U16 Girls", season="2026")
        TeamMembership.objects.add_member(user=coach, team=team, role=TeamRole.COACH)
        TeamMembership.objects.add_member(user=other_coach, team=team, role=TeamRole.COACH)
        token = generate_auth_token(coach)

        response = self.client.delete(
            reverse(
                "core:remove-team-member",
                kwargs={"team_id": team.id, "target_user_id": other_coach.id},
            ),
            data=json.dumps({}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(
            TeamMembership.objects.filter(
                user=other_coach,
                team=team,
                is_active=True,
            ).exists()
        )


class ParentAssociationEndpointTests(TestCase):
    def test_player_can_add_parent_association(self):
        player = User.objects.create_user(
            email="player@example.com",
            password="StrongPassword123!",
            first_name="Player",
            last_name="User",
            date_of_birth=date(2010, 4, 1),
        )
        parent = User.objects.create_user(
            email="parent@example.com",
            password="StrongPassword123!",
            first_name="Parent",
            last_name="User",
        )
        token = generate_auth_token(player)

        response = self.client.post(
            reverse("core:add-parent-association", kwargs={"player_id": player.id}),
            data=json.dumps({"parent_id": parent.id, "is_legal_guardian": True}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 201)
        relation = ParentPlayerRelation.objects.get(parent=parent, player=player)
        self.assertTrue(relation.is_active)
        self.assertTrue(relation.is_legal_guardian)

    def test_coach_can_add_parent_association_for_team_player(self):
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
            date_of_birth=date(2010, 4, 1),
        )
        parent = User.objects.create_user(
            email="parent@example.com",
            password="StrongPassword123!",
            first_name="Parent",
            last_name="User",
        )
        club = Club.objects.create_club(name="NetUp Volleyball Club", director=director)
        team = Team.objects.create_team(club=club, name="U16 Girls", season="2026")
        TeamMembership.objects.add_member(user=coach, team=team, role=TeamRole.COACH)
        TeamMembership.objects.add_member(user=player, team=team, role=TeamRole.PLAYER)
        token = generate_auth_token(coach)

        response = self.client.post(
            reverse("core:add-parent-association", kwargs={"player_id": player.id}),
            data=json.dumps({"parent_id": parent.id}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            ParentPlayerRelation.objects.active().filter(parent=parent, player=player).exists()
        )

    def test_minor_player_cannot_remove_parent_association(self):
        player = User.objects.create_user(
            email="player@example.com",
            password="StrongPassword123!",
            first_name="Player",
            last_name="User",
            date_of_birth=date(2010, 4, 1),
        )
        parent = User.objects.create_user(
            email="parent@example.com",
            password="StrongPassword123!",
            first_name="Parent",
            last_name="User",
        )
        ParentPlayerRelation.objects.link(parent=parent, player=player)
        token = generate_auth_token(player)

        response = self.client.delete(
            reverse(
                "core:remove-parent-association",
                kwargs={"player_id": player.id, "parent_id": parent.id},
            ),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(
            ParentPlayerRelation.objects.active().filter(parent=parent, player=player).exists()
        )

    def test_adult_player_can_remove_parent_association(self):
        player = User.objects.create_user(
            email="player@example.com",
            password="StrongPassword123!",
            first_name="Player",
            last_name="User",
            date_of_birth=date(2000, 4, 1),
        )
        parent = User.objects.create_user(
            email="parent@example.com",
            password="StrongPassword123!",
            first_name="Parent",
            last_name="User",
        )
        ParentPlayerRelation.objects.link(parent=parent, player=player)
        token = generate_auth_token(player)

        response = self.client.delete(
            reverse(
                "core:remove-parent-association",
                kwargs={"player_id": player.id, "parent_id": parent.id},
            ),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            ParentPlayerRelation.objects.active().filter(parent=parent, player=player).exists()
        )

    def test_club_director_can_remove_parent_association(self):
        director = User.objects.create_user(
            email="director@example.com",
            password="StrongPassword123!",
            first_name="Club",
            last_name="Director",
        )
        player = User.objects.create_user(
            email="player@example.com",
            password="StrongPassword123!",
            first_name="Player",
            last_name="User",
            date_of_birth=date(2010, 4, 1),
        )
        parent = User.objects.create_user(
            email="parent@example.com",
            password="StrongPassword123!",
            first_name="Parent",
            last_name="User",
        )
        club = Club.objects.create_club(name="NetUp Volleyball Club", director=director)
        team = Team.objects.create_team(club=club, name="U16 Girls", season="2026")
        TeamMembership.objects.add_member(user=player, team=team, role=TeamRole.PLAYER)
        ParentPlayerRelation.objects.link(parent=parent, player=player)
        token = generate_auth_token(director)

        response = self.client.delete(
            reverse(
                "core:remove-parent-association",
                kwargs={"player_id": player.id, "parent_id": parent.id},
            ),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            ParentPlayerRelation.objects.active().filter(parent=parent, player=player).exists()
        )


class PlayerParentManagementEndpointTests(TestCase):
    def test_parent_can_view_and_update_minor_player_management_settings(self):
        parent = User.objects.create_user(
            email="parent@example.com",
            password="StrongPassword123!",
            first_name="Parent",
            last_name="User",
        )
        player = User.objects.create_user(
            email="player@example.com",
            password="StrongPassword123!",
            first_name="Player",
            last_name="User",
            date_of_birth=date(2010, 4, 1),
        )
        ParentPlayerRelation.objects.link(parent=parent, player=player, is_legal_guardian=True)
        token = generate_auth_token(parent)

        get_response = self.client.get(
            reverse("core:manage-player-parent-access", kwargs={"player_id": player.id}),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(get_response.json()["policy"]["is_parent_managed"], False)

        patch_response = self.client.patch(
            reverse("core:manage-player-parent-access", kwargs={"player_id": player.id}),
            data=json.dumps(
                {
                    "is_parent_managed": True,
                    "can_self_make_payments": False,
                    "can_self_update_emergency_contact": False,
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(patch_response.status_code, 200)
        policy = PlayerAccessPolicy.objects.get(player=player)
        self.assertTrue(policy.is_parent_managed)
        self.assertFalse(policy.can_self_make_payments)
        self.assertFalse(policy.can_self_update_emergency_contact)

    def test_parent_cannot_manage_access_for_adult_player(self):
        parent = User.objects.create_user(
            email="parent@example.com",
            password="StrongPassword123!",
            first_name="Parent",
            last_name="User",
        )
        player = User.objects.create_user(
            email="player@example.com",
            password="StrongPassword123!",
            first_name="Player",
            last_name="User",
            date_of_birth=date(2000, 4, 1),
        )
        ParentPlayerRelation.objects.link(parent=parent, player=player)
        token = generate_auth_token(parent)

        response = self.client.patch(
            reverse("core:manage-player-parent-access", kwargs={"player_id": player.id}),
            data=json.dumps({"is_parent_managed": True}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 403)


class PlayerParentManagedPermissionTests(TestCase):
    def test_parent_managed_policy_restricts_minor_player_self_service(self):
        parent = User.objects.create_user(
            email="parent@example.com",
            password="StrongPassword123!",
            first_name="Parent",
            last_name="User",
        )
        player = User.objects.create_user(
            email="player@example.com",
            password="StrongPassword123!",
            first_name="Player",
            last_name="User",
            date_of_birth=date(2010, 4, 1),
        )
        ParentPlayerRelation.objects.link(parent=parent, player=player)
        PlayerAccessPolicy.objects.create(
            player=player,
            is_parent_managed=True,
            can_self_make_payments=False,
            can_self_update_emergency_contact=False,
        )

        self.assertTrue(is_player_parent_managed(player))
        self.assertFalse(can_player_make_payments(player))
        self.assertFalse(can_player_update_own_emergency_contact(player))

    def test_adult_player_ignores_parent_managed_policy(self):
        parent = User.objects.create_user(
            email="parent@example.com",
            password="StrongPassword123!",
            first_name="Parent",
            last_name="User",
        )
        player = User.objects.create_user(
            email="player@example.com",
            password="StrongPassword123!",
            first_name="Player",
            last_name="User",
            date_of_birth=date(2000, 4, 1),
        )
        ParentPlayerRelation.objects.link(parent=parent, player=player)
        PlayerAccessPolicy.objects.create(
            player=player,
            is_parent_managed=True,
            can_self_make_payments=False,
            can_self_update_emergency_contact=False,
        )

        self.assertFalse(is_player_parent_managed(player))
        self.assertTrue(can_player_make_payments(player))
        self.assertTrue(can_player_update_own_emergency_contact(player))


class UpdateTeamMemberDataEndpointTests(TestCase):
    def test_player_can_update_their_own_emergency_contact(self):
        director = User.objects.create_user(
            email="director@example.com",
            password="StrongPassword123!",
            first_name="Club",
            last_name="Director",
        )
        player = User.objects.create_user(
            email="player@example.com",
            password="StrongPassword123!",
            first_name="Player",
            last_name="User",
            date_of_birth=date(2010, 4, 1),
        )
        club = Club.objects.create_club(name="NetUp Volleyball Club", director=director)
        team = Team.objects.create_team(club=club, name="U16 Girls", season="2026")
        TeamMembership.objects.add_member(user=player, team=team, role=TeamRole.PLAYER)
        token = generate_auth_token(player)

        response = self.client.patch(
            reverse(
                "core:update-team-member-data",
                kwargs={"team_id": team.id, "target_user_id": player.id},
            ),
            data=json.dumps({"emergency_contact": "+96170000000"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 200)
        player.refresh_from_db()
        self.assertEqual(player.emergency_contact, "+96170000000")

    def test_parent_managed_player_cannot_update_their_own_emergency_contact(self):
        director = User.objects.create_user(
            email="director@example.com",
            password="StrongPassword123!",
            first_name="Club",
            last_name="Director",
        )
        parent = User.objects.create_user(
            email="parent@example.com",
            password="StrongPassword123!",
            first_name="Parent",
            last_name="User",
        )
        player = User.objects.create_user(
            email="player@example.com",
            password="StrongPassword123!",
            first_name="Player",
            last_name="User",
            date_of_birth=date(2010, 4, 1),
        )
        club = Club.objects.create_club(name="NetUp Volleyball Club", director=director)
        team = Team.objects.create_team(club=club, name="U16 Girls", season="2026")
        TeamMembership.objects.add_member(user=player, team=team, role=TeamRole.PLAYER)
        ParentPlayerRelation.objects.link(parent=parent, player=player)
        PlayerAccessPolicy.objects.create(
            player=player,
            is_parent_managed=True,
            can_self_update_emergency_contact=False,
        )
        token = generate_auth_token(player)

        response = self.client.patch(
            reverse(
                "core:update-team-member-data",
                kwargs={"team_id": team.id, "target_user_id": player.id},
            ),
            data=json.dumps({"emergency_contact": "+96170000000"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 403)

    def test_parent_can_update_their_childs_emergency_contact(self):
        director = User.objects.create_user(
            email="director@example.com",
            password="StrongPassword123!",
            first_name="Club",
            last_name="Director",
        )
        parent = User.objects.create_user(
            email="parent@example.com",
            password="StrongPassword123!",
            first_name="Parent",
            last_name="User",
        )
        player = User.objects.create_user(
            email="player@example.com",
            password="StrongPassword123!",
            first_name="Player",
            last_name="User",
            date_of_birth=date(2010, 4, 1),
        )
        club = Club.objects.create_club(name="NetUp Volleyball Club", director=director)
        team = Team.objects.create_team(club=club, name="U16 Girls", season="2026")
        TeamMembership.objects.add_member(user=player, team=team, role=TeamRole.PLAYER)
        ParentPlayerRelation.objects.link(parent=parent, player=player)
        token = generate_auth_token(parent)

        response = self.client.patch(
            reverse(
                "core:update-team-member-data",
                kwargs={"team_id": team.id, "target_user_id": player.id},
            ),
            data=json.dumps({"emergency_contact": "+96171111111"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 200)
        player.refresh_from_db()
        self.assertEqual(player.emergency_contact, "+96171111111")

    def test_coach_can_update_player_profile_fields_only(self):
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
            date_of_birth=date(2010, 4, 1),
        )
        club = Club.objects.create_club(name="NetUp Volleyball Club", director=director)
        team = Team.objects.create_team(club=club, name="U16 Girls", season="2026")
        TeamMembership.objects.add_member(user=coach, team=team, role=TeamRole.COACH)
        TeamMembership.objects.add_member(user=player, team=team, role=TeamRole.PLAYER)
        token = generate_auth_token(coach)

        response = self.client.patch(
            reverse(
                "core:update-team-member-data",
                kwargs={"team_id": team.id, "target_user_id": player.id},
            ),
            data=json.dumps(
                {
                    "jersey_number": 8,
                    "primary_position": "Setter",
                    "notes": "Strong serve receive.",
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 200)
        profile = PlayerProfile.objects.get(user=player)
        self.assertEqual(profile.jersey_number, 8)
        self.assertEqual(profile.primary_position, "Setter")
        self.assertEqual(profile.notes, "Strong serve receive.")

    def test_coach_cannot_update_player_emergency_contact(self):
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
            date_of_birth=date(2010, 4, 1),
        )
        club = Club.objects.create_club(name="NetUp Volleyball Club", director=director)
        team = Team.objects.create_team(club=club, name="U16 Girls", season="2026")
        TeamMembership.objects.add_member(user=coach, team=team, role=TeamRole.COACH)
        TeamMembership.objects.add_member(user=player, team=team, role=TeamRole.PLAYER)
        token = generate_auth_token(coach)

        response = self.client.patch(
            reverse(
                "core:update-team-member-data",
                kwargs={"team_id": team.id, "target_user_id": player.id},
            ),
            data=json.dumps({"emergency_contact": "+96172222222"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 400)

    def test_other_user_can_update_their_own_emergency_contact_only(self):
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
        club = Club.objects.create_club(name="NetUp Volleyball Club", director=director)
        team = Team.objects.create_team(club=club, name="U16 Girls", season="2026")
        TeamMembership.objects.add_member(user=coach, team=team, role=TeamRole.COACH)
        token = generate_auth_token(coach)

        response = self.client.patch(
            reverse(
                "core:update-team-member-data",
                kwargs={"team_id": team.id, "target_user_id": coach.id},
            ),
            data=json.dumps({"emergency_contact": "+96173333333"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 200)
        coach.refresh_from_db()
        self.assertEqual(coach.emergency_contact, "+96173333333")


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


class DirectorPaymentApiTests(TestCase):
    def test_payment_overview_forbidden_without_director_role(self):
        director = User.objects.create_user(
            email="d-fee@example.com",
            password="StrongPassword123!",
        )
        club = Club.objects.create_club(name="Fee Club A", director=director)
        player = User.objects.create_user(
            email="p-fee@example.com",
            password="StrongPassword123!",
        )
        team = Team.objects.create_team(club=club, name="Team Fee A", season="2026")
        TeamMembership.objects.add_member(user=player, team=team, role=TeamRole.PLAYER)

        stranger = User.objects.create_user(
            email="stranger-fee@example.com",
            password="StrongPassword123!",
        )
        token = generate_auth_token(stranger)

        response = self.client.get(
            reverse("core:director-payment-overview", kwargs={"club_id": club.id}),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 403)

    def test_director_payment_rows_groups_by_family(self):
        director = User.objects.create_user(
            email="dir-rows@example.com",
            password="StrongPassword123!",
        )
        club = Club.objects.create_club(name="Rows Club", director=director)
        player = User.objects.create_user(
            email="prows@example.com",
            password="StrongPassword123!",
            first_name="Row",
            last_name="Family",
        )
        team = Team.objects.create_team(club=club, name="Rows Team", season="2026")
        TeamMembership.objects.add_member(user=player, team=team, role=TeamRole.PLAYER)
        PlayerFeeRecord.objects.create(
            club=club,
            player=player,
            team=team,
            description="A",
            amount_due=Decimal("10.00"),
            amount_paid=Decimal("0.00"),
            due_date=timezone.localdate(),
        )
        PlayerFeeRecord.objects.create(
            club=club,
            player=player,
            team=team,
            description="B",
            amount_due=Decimal("5.00"),
            amount_paid=Decimal("1.00"),
            due_date=timezone.localdate(),
        )
        token = generate_auth_token(director)
        response = self.client.get(
            reverse("core:director-payment-rows", kwargs={"club_id": club.id}),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["families"]), 1)
        fam = data["families"][0]
        self.assertEqual(fam["player_id"], player.id)
        self.assertEqual(len(fam["lines"]), 2)
        self.assertEqual(Decimal(fam["total_remaining"]), Decimal("14.00"))

    def test_payment_overview_returns_real_rows_for_director(self):
        director = User.objects.create_user(
            email="dir-fee@example.com",
            password="StrongPassword123!",
        )
        club = Club.objects.create_club(name="Fee Club B", director=director)
        player = User.objects.create_user(
            email="player-fee@example.com",
            password="StrongPassword123!",
            first_name="Pat",
            last_name="Lee",
        )
        team = Team.objects.create_team(club=club, name="Team Fee B", season="2026")
        TeamMembership.objects.add_member(user=player, team=team, role=TeamRole.PLAYER)

        PlayerFeeRecord.objects.create(
            club=club,
            player=player,
            team=team,
            amount_due=Decimal("100.00"),
            amount_paid=Decimal("0.00"),
            due_date=timezone.localdate(),
        )

        token = generate_auth_token(director)
        response = self.client.get(
            reverse("core:director-payment-overview", kwargs={"club_id": club.id}),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["kpis"]["registration_player_count"], 1)
        self.assertEqual(data["kpis"]["outstanding_payer_count"], 1)
        self.assertEqual(len(data["family_summaries"]), 1)
        self.assertEqual(data["family_summaries"][0]["overall_status"], "pending")
        self.assertEqual(data["family_summaries"][0]["player_id"], player.id)

    def test_renewals_due_today_lists_only_unpaid_due_today(self):
        director = User.objects.create_user(
            email="dir-renew@example.com",
            password="StrongPassword123!",
        )
        club = Club.objects.create_club(name="Renew Club", director=director)
        player_a = User.objects.create_user(
            email="pa-renew@example.com",
            password="StrongPassword123!",
            first_name="A",
            last_name="One",
        )
        player_b = User.objects.create_user(
            email="pb-renew@example.com",
            password="StrongPassword123!",
            first_name="B",
            last_name="Two",
        )
        team = Team.objects.create_team(club=club, name="Renew Team", season="2026")
        TeamMembership.objects.add_member(user=player_a, team=team, role=TeamRole.PLAYER)
        TeamMembership.objects.add_member(user=player_b, team=team, role=TeamRole.PLAYER)
        today = timezone.localdate()
        PlayerFeeRecord.objects.create(
            club=club,
            player=player_a,
            team=team,
            description="Due today",
            amount_due=Decimal("50.00"),
            amount_paid=Decimal("0.00"),
            due_date=today,
        )
        PlayerFeeRecord.objects.create(
            club=club,
            player=player_b,
            team=team,
            description="Paid today",
            amount_due=Decimal("50.00"),
            amount_paid=Decimal("50.00"),
            due_date=today,
            paid_at=timezone.now(),
        )
        token = generate_auth_token(director)
        response = self.client.get(
            reverse("core:director-renewals-due-today", kwargs={"club_id": club.id}),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["family_count"], 1)
        self.assertEqual(len(data["families"][0]["lines"]), 1)
        self.assertEqual(data["families"][0]["lines"][0]["player"]["email"], player_a.email)

    def test_materialize_month_creates_one_row_per_rostered_player(self):
        director = User.objects.create_user(
            email="dir-mat@example.com",
            password="StrongPassword123!",
        )
        club = Club.objects.create_club(name="Mat Club", director=director)
        club.default_monthly_player_fee = Decimal("40.00")
        club.save(update_fields=["default_monthly_player_fee"])
        p1 = User.objects.create_user(email="m1@example.com", password="StrongPassword123!")
        p2 = User.objects.create_user(email="m2@example.com", password="StrongPassword123!")
        team = Team.objects.create_team(club=club, name="Mat Team", season="2026")
        TeamMembership.objects.add_member(user=p1, team=team, role=TeamRole.PLAYER)
        TeamMembership.objects.add_member(user=p2, team=team, role=TeamRole.PLAYER)
        period = date(2026, 7, 1)
        token = generate_auth_token(director)
        response = self.client.post(
            reverse("core:director-materialize-monthly-fees", kwargs={"club_id": club.id}),
            data=json.dumps({"period_start": "2026-07-15"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["created_count"], 2)
        self.assertEqual(
            PlayerFeeRecord.objects.filter(club=club, billing_period_start=period).count(),
            2,
        )
        self.assertTrue(
            DirectorPaymentAuditLog.objects.filter(
                club=club,
                action=DirectorPaymentAuditLog.Action.MONTHLY_FEES_MATERIALIZED,
            ).exists()
        )

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_bulk_email_renewals_due_today_sends_locmem_mail(self):
        director = User.objects.create_user(
            email="dir-bulk@example.com",
            password="StrongPassword123!",
        )
        club = Club.objects.create_club(name="Bulk Club", director=director)
        player = User.objects.create_user(
            email="bulk-player@example.com",
            password="StrongPassword123!",
            first_name="Bulk",
            last_name="Player",
        )
        team = Team.objects.create_team(club=club, name="Bulk Team", season="2026")
        TeamMembership.objects.add_member(user=player, team=team, role=TeamRole.PLAYER)
        today = timezone.localdate()
        PlayerFeeRecord.objects.create(
            club=club,
            player=player,
            team=team,
            description="Due today bulk",
            amount_due=Decimal("30.00"),
            amount_paid=Decimal("0.00"),
            due_date=today,
        )
        mail.outbox.clear()
        token = generate_auth_token(director)
        response = self.client.post(
            reverse("core:director-bulk-email-renewals-today", kwargs={"club_id": club.id}),
            data=json.dumps({}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["emailed_count"], 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Monthly fee due", mail.outbox[0].subject)
        self.assertTrue(len(mail.outbox[0].attachments) >= 1)
        self.assertTrue(
            DirectorPaymentAuditLog.objects.filter(
                club=club,
                action=DirectorPaymentAuditLog.Action.BULK_STATEMENTS_SENT,
            ).exists()
        )

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_email_renewals_due_today_for_one_player_sends_one_mail(self):
        director = User.objects.create_user(
            email="dir-onefam@example.com",
            password="StrongPassword123!",
        )
        club = Club.objects.create_club(name="One Fam Club", director=director)
        player = User.objects.create_user(
            email="onefam-player@example.com",
            password="StrongPassword123!",
            first_name="One",
            last_name="Fam",
        )
        team = Team.objects.create_team(club=club, name="One Fam Team", season="2026")
        TeamMembership.objects.add_member(user=player, team=team, role=TeamRole.PLAYER)
        today = timezone.localdate()
        PlayerFeeRecord.objects.create(
            club=club,
            player=player,
            team=team,
            description="Due A",
            amount_due=Decimal("10.00"),
            amount_paid=Decimal("0.00"),
            due_date=today,
        )
        PlayerFeeRecord.objects.create(
            club=club,
            player=player,
            team=team,
            description="Due B",
            amount_due=Decimal("5.00"),
            amount_paid=Decimal("0.00"),
            due_date=today,
        )
        mail.outbox.clear()
        token = generate_auth_token(director)
        response = self.client.post(
            reverse("core:director-email-renewals-today-player", kwargs={"club_id": club.id}),
            data=json.dumps({"player_id": player.id}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["fee_line_count"], 2)
        self.assertEqual(response.json()["emailed_count"], 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Fees due today", mail.outbox[0].subject)
        self.assertTrue(len(mail.outbox[0].attachments) >= 1)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_email_outstanding_notice_for_player_lists_all_lines(self):
        director = User.objects.create_user(
            email="dir-out@example.com",
            password="StrongPassword123!",
        )
        club = Club.objects.create_club(name="Out Club", director=director)
        player = User.objects.create_user(
            email="out-player@example.com",
            password="StrongPassword123!",
            first_name="Out",
            last_name="Standing",
        )
        team = Team.objects.create_team(club=club, name="Out Team", season="2026")
        TeamMembership.objects.add_member(user=player, team=team, role=TeamRole.PLAYER)
        PlayerFeeRecord.objects.create(
            club=club,
            player=player,
            team=team,
            description="Line one",
            amount_due=Decimal("40.00"),
            amount_paid=Decimal("0.00"),
            due_date=timezone.localdate(),
        )
        PlayerFeeRecord.objects.create(
            club=club,
            player=player,
            team=team,
            description="Line two",
            amount_due=Decimal("2.00"),
            amount_paid=Decimal("1.00"),
            due_date=timezone.localdate(),
        )
        mail.outbox.clear()
        token = generate_auth_token(director)
        response = self.client.post(
            reverse("core:director-email-outstanding-notice", kwargs={"club_id": club.id}),
            data=json.dumps({"player_id": player.id}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["fee_line_count"], 2)
        body = mail.outbox[0].body
        self.assertIn("Line one", body)
        self.assertIn("Line two", body)
        self.assertTrue(len(mail.outbox[0].attachments) >= 1)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_director_record_payment_sends_balance_pdf_email(self):
        director = User.objects.create_user(
            email="dir-paypdf@example.com",
            password="StrongPassword123!",
        )
        club = Club.objects.create_club(name="Pay PDF Club", director=director)
        player = User.objects.create_user(
            email="player-paypdf@example.com",
            password="StrongPassword123!",
            first_name="Pay",
            last_name="Pdf",
        )
        team = Team.objects.create_team(club=club, name="Pay PDF Team", season="2026")
        TeamMembership.objects.add_member(user=player, team=team, role=TeamRole.PLAYER)
        rec = PlayerFeeRecord.objects.create(
            club=club,
            player=player,
            team=team,
            description="Dues",
            amount_due=Decimal("50.00"),
            amount_paid=Decimal("0.00"),
            due_date=timezone.localdate(),
        )
        mail.outbox.clear()
        token = generate_auth_token(director)
        response = self.client.post(
            reverse(
                "core:director-record-fee-payment",
                kwargs={"club_id": club.id, "record_id": rec.id},
            ),
            data=json.dumps({"amount": "20", "note": "cash"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Updated balance", mail.outbox[0].subject)
        atts = getattr(mail.outbox[0], "attachments", None) or []
        self.assertTrue(len(atts) >= 1)

    def test_payment_lookup_player_returns_rows_and_primary(self):
        director = User.objects.create_user(
            email="dir-lookup@example.com",
            password="StrongPassword123!",
        )
        club = Club.objects.create_club(name="Lookup Club", director=director)
        player = User.objects.create_user(
            email="pl-lookup@example.com",
            password="StrongPassword123!",
            first_name="Look",
            last_name="Up",
        )
        team = Team.objects.create_team(club=club, name="Lookup Team", season="2026")
        TeamMembership.objects.add_member(user=player, team=team, role=TeamRole.PLAYER)
        rec = PlayerFeeRecord.objects.create(
            club=club,
            player=player,
            team=team,
            description="Monthly",
            amount_due=Decimal("75.00"),
            amount_paid=Decimal("10.00"),
            due_date=timezone.localdate(),
        )
        rec2 = PlayerFeeRecord.objects.create(
            club=club,
            player=player,
            team=team,
            description="Second line",
            amount_due=Decimal("25.00"),
            amount_paid=Decimal("0.00"),
            due_date=timezone.localdate(),
        )
        token = generate_auth_token(director)
        response = self.client.get(
            reverse("core:director-payment-lookup-player", kwargs={"club_id": club.id}),
            {"player_id": str(player.id)},
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["player"]["id"], player.id)
        self.assertEqual(len(data["fee_rows"]), 2)
        ids = {row["id"] for row in data["fee_rows"]}
        self.assertSetEqual(ids, {rec.id, rec2.id})
        self.assertEqual(Decimal(data["outstanding_total_remaining"]), Decimal("90.00"))
        self.assertEqual(data["primary_fee_record_id"], rec2.id)

    @override_settings(PAYMENTS_REQUIRE_TEAM_ROSTER=True)
    def test_payment_lookup_player_rejects_non_roster_user(self):
        director = User.objects.create_user(
            email="dir-noroster@example.com",
            password="StrongPassword123!",
        )
        club = Club.objects.create_club(name="No Roster Club", director=director)
        outsider = User.objects.create_user(
            email="outsider@example.com",
            password="StrongPassword123!",
        )
        token = generate_auth_token(director)
        response = self.client.get(
            reverse("core:director-payment-lookup-player", kwargs={"club_id": club.id}),
            {"player_id": str(outsider.id)},
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("player_id", response.json().get("errors", {}))

    def test_download_receipt_pdf_400_when_unpaid(self):
        director = User.objects.create_user(
            email="dir-nopay@example.com",
            password="StrongPassword123!",
        )
        club = Club.objects.create_club(name="No Pay Club", director=director)
        player = User.objects.create_user(email="p-nopay@example.com", password="StrongPassword123!")
        team = Team.objects.create_team(club=club, name="No Pay Team", season="2026")
        TeamMembership.objects.add_member(user=player, team=team, role=TeamRole.PLAYER)
        rec = PlayerFeeRecord.objects.create(
            club=club,
            player=player,
            team=team,
            amount_due=Decimal("20.00"),
            amount_paid=Decimal("0.00"),
            due_date=timezone.localdate(),
        )
        token = generate_auth_token(director)
        response = self.client.get(
            reverse(
                "core:director-download-receipt-pdf",
                kwargs={"club_id": club.id, "record_id": rec.id},
            ),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("fee", response.json().get("errors", {}))

    def test_download_receipt_pdf_returns_pdf_bytes(self):
        director = User.objects.create_user(
            email="dir-pdf@example.com",
            password="StrongPassword123!",
        )
        club = Club.objects.create_club(name="PDF Club", director=director)
        player = User.objects.create_user(email="p-pdf@example.com", password="StrongPassword123!")
        team = Team.objects.create_team(club=club, name="PDF Team", season="2026")
        TeamMembership.objects.add_member(user=player, team=team, role=TeamRole.PLAYER)
        rec = PlayerFeeRecord.objects.create(
            club=club,
            player=player,
            team=team,
            amount_due=Decimal("20.00"),
            amount_paid=Decimal("5.00"),
            due_date=timezone.localdate(),
        )
        token = generate_auth_token(director)
        response = self.client.get(
            reverse(
                "core:director-download-receipt-pdf",
                kwargs={"club_id": club.id, "record_id": rec.id},
            ),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_send_payment_reminder_attaches_pdf(self):
        director = User.objects.create_user(
            email="dir-rem@example.com",
            password="StrongPassword123!",
        )
        club = Club.objects.create_club(name="Rem Club", director=director)
        player = User.objects.create_user(
            email="p-rem@example.com",
            password="StrongPassword123!",
            first_name="Rem",
            last_name="Player",
        )
        parent = User.objects.create_user(email="parent-rem@example.com", password="StrongPassword123!")
        ParentPlayerRelation.objects.link(parent=parent, player=player)
        team = Team.objects.create_team(club=club, name="Rem Team", season="2026")
        TeamMembership.objects.add_member(user=player, team=team, role=TeamRole.PLAYER)
        rec = PlayerFeeRecord.objects.create(
            club=club,
            player=player,
            team=team,
            description="Due fee",
            amount_due=Decimal("40.00"),
            amount_paid=Decimal("0.00"),
            due_date=timezone.localdate(),
        )
        mail.outbox.clear()
        token = generate_auth_token(director)
        response = self.client.post(
            reverse(
                "core:director-send-payment-reminder",
                kwargs={"club_id": club.id, "record_id": rec.id},
            ),
            data=json.dumps({}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        sent = set(response.json()["sent_to"])
        self.assertEqual(sent, {player.email, parent.email})
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertEqual(len(msg.attachments), 1)
        filename, content, mimetype = msg.attachments[0]
        self.assertTrue(filename.endswith(".pdf"))
        self.assertEqual(mimetype, "application/pdf")
        self.assertTrue(content.startswith(b"%PDF"))
        self.assertTrue(
            DirectorPaymentAuditLog.objects.filter(
                club=club,
                action=DirectorPaymentAuditLog.Action.REMINDER_SENT,
            ).exists()
        )

    def test_delete_inactive_payment_schedule_succeeds(self):
        director = User.objects.create_user(email="sched-del@example.com", password="StrongPassword123!")
        club = Club.objects.create_club(name="Sched Del Club", director=director)
        sched = PaymentSchedule.objects.create(
            club=club,
            team=None,
            player=None,
            scope=PaymentSchedule.Scope.CLUB,
            frequency=PaymentSchedule.Frequency.MONTHLY,
            amount=Decimal("50.00"),
            description="Test",
            start_date=timezone.localdate(),
            is_active=False,
            created_by=director,
        )
        token = generate_auth_token(director)
        response = self.client.post(
            reverse("core:delete-payment-schedule", kwargs={"club_id": club.id, "schedule_id": sched.id}),
            data=json.dumps({}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(PaymentSchedule.objects.filter(id=sched.id).exists())

    def test_delete_active_payment_schedule_returns_400(self):
        director = User.objects.create_user(email="sched-act@example.com", password="StrongPassword123!")
        club = Club.objects.create_club(name="Sched Act Club", director=director)
        sched = PaymentSchedule.objects.create(
            club=club,
            team=None,
            player=None,
            scope=PaymentSchedule.Scope.CLUB,
            frequency=PaymentSchedule.Frequency.MONTHLY,
            amount=Decimal("50.00"),
            description="Active",
            start_date=timezone.localdate(),
            is_active=True,
            created_by=director,
        )
        token = generate_auth_token(director)
        response = self.client.post(
            reverse("core:delete-payment-schedule", kwargs={"club_id": club.id, "schedule_id": sched.id}),
            data=json.dumps({}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 400)
        self.assertTrue(PaymentSchedule.objects.filter(id=sched.id).exists())


class DirectorUserDirectoryApiTests(TestCase):
    def test_directory_forbidden_for_non_director(self):
        u = User.objects.create_user(email="nodir@example.com", password="StrongPassword123!")
        token = generate_auth_token(u)
        response = self.client.get(
            reverse("core:directors-user-directory"),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 403)

    def test_directory_lists_users_and_set_role_updates(self):
        director = User.objects.create_user(
            email="dir-dirlist@example.com",
            password="StrongPassword123!",
        )
        Club.objects.create_club(name="Dir List Club", director=director)
        target = User.objects.create_user(
            email="target-role@example.com",
            password="StrongPassword123!",
            first_name="Tar",
            last_name="Get",
            verification_status=VerificationStatus.VERIFIED,
        )
        token = generate_auth_token(director)
        response = self.client.get(
            reverse("core:directors-user-directory"),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreaterEqual(data["count"], 2)
        ids = {row["id"] for row in data["users"]}
        self.assertIn(director.id, ids)
        self.assertIn(target.id, ids)

        response2 = self.client.post(
            reverse("core:directors-set-account-role", kwargs={"user_id": target.id}),
            data=json.dumps({"role": "parent"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response2.status_code, 200)
        self.assertEqual(response2.json()["user"]["assigned_account_role"], "parent")
        self.assertEqual(response2.json()["user"]["role"], "parent")
        target.refresh_from_db()
        self.assertEqual(target.assigned_account_role, "parent")

    def test_set_role_promotes_to_director(self):
        director = User.objects.create_user(
            email="dir-promo@example.com",
            password="StrongPassword123!",
        )
        club = Club.objects.create_club(name="Promo Club", director=director)
        target = User.objects.create_user(
            email="target-promo@example.com",
            password="StrongPassword123!",
            verification_status=VerificationStatus.VERIFIED,
            assigned_account_role=AssignedAccountRole.PLAYER,
        )
        token = generate_auth_token(director)
        response = self.client.post(
            reverse("core:directors-set-account-role", kwargs={"user_id": target.id}),
            data=json.dumps({"role": "director", "club_id": club.id}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user"]["role"], "director")
        self.assertTrue(
            ClubMembership.objects.active()
            .filter(user=target, club=club, role=ClubRole.CLUB_DIRECTOR)
            .exists()
        )

    def test_set_role_self_downgrade_director_forbidden(self):
        director = User.objects.create_user(
            email="dir-self@example.com",
            password="StrongPassword123!",
        )
        Club.objects.create_club(name="Self Club", director=director)
        token = generate_auth_token(director)
        response = self.client.post(
            reverse("core:directors-set-account-role", kwargs={"user_id": director.id}),
            data=json.dumps({"role": "player"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 403)

    def test_set_role_downgrades_other_director(self):
        director_a = User.objects.create_user(
            email="dir-a@example.com",
            password="StrongPassword123!",
        )
        director_b = User.objects.create_user(
            email="dir-b@example.com",
            password="StrongPassword123!",
        )
        club = Club.objects.create_club(name="Two Dir Club", director=director_a)
        ClubMembership.objects.assign_director(user=director_b, club=club)
        token = generate_auth_token(director_a)
        response = self.client.post(
            reverse("core:directors-set-account-role", kwargs={"user_id": director_b.id}),
            data=json.dumps({"role": "player"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        director_b.refresh_from_db()
        self.assertEqual(director_b.assigned_account_role, AssignedAccountRole.PLAYER)
        self.assertFalse(
            ClubMembership.objects.active()
            .filter(user=director_b, club=club, role=ClubRole.CLUB_DIRECTOR)
            .exists()
        )


class ParentLinkDirectorQueueTests(TestCase):
    def test_director_sees_pending_when_parent_is_in_club_but_child_not_on_team(self):
        """Pending link when only the parent has a club membership."""
        director = User.objects.create_user(email="pl2-dir@example.com", password="StrongPassword123!")
        club = Club.objects.create_club(name="PL2 Club", director=director)
        team = Team.objects.create(club=club, name="PL2 Team")
        child = User.objects.create_user(
            email="pl2-child@example.com",
            password="StrongPassword123!",
            assigned_account_role=AssignedAccountRole.PLAYER,
        )
        parent = User.objects.create_user(
            email="pl2-par@example.com",
            password="StrongPassword123!",
            assigned_account_role=AssignedAccountRole.PARENT,
        )
        TeamMembership.objects.add_member(user=parent, team=team, role=TeamRole.COACH)
        ParentPlayerRelation.objects.link(
            parent=parent,
            player=child,
            approval_status=ParentLinkApprovalStatus.PENDING,
        )
        token = generate_auth_token(director)
        response = self.client.get(
            reverse("core:directors-pending-parent-links"),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json().get("requests", [])), 1)

    def test_director_sees_pending_link_when_player_has_multiple_team_roles(self):
        """Pending link still listed when the player has more than one team role."""
        director = User.objects.create_user(email="pl-dir@example.com", password="StrongPassword123!")
        club = Club.objects.create_club(name="PL Club", director=director)
        team = Team.objects.create(club=club, name="PL Team")
        player = User.objects.create_user(
            email="pl-child@example.com",
            password="StrongPassword123!",
            assigned_account_role=AssignedAccountRole.PLAYER,
        )
        parent = User.objects.create_user(
            email="pl-par@example.com",
            password="StrongPassword123!",
            assigned_account_role=AssignedAccountRole.PARENT,
        )
        TeamMembership.objects.add_member(user=player, team=team, role=TeamRole.PLAYER)
        other_team = Team.objects.create(club=club, name="PL Other")
        TeamMembership.objects.add_member(user=player, team=other_team, role=TeamRole.COACH)
        ParentPlayerRelation.objects.link(
            parent=parent,
            player=player,
            approval_status=ParentLinkApprovalStatus.PENDING,
        )
        token = generate_auth_token(director)
        response = self.client.get(
            reverse("core:directors-pending-parent-links"),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json().get("requests", [])), 1)


class CoachRosterRbacTests(TestCase):
    def test_coach_cannot_add_parent_assigned_user_as_player(self):
        director = User.objects.create_user(email="rb-dir@example.com", password="StrongPassword123!")
        coach = User.objects.create_user(
            email="rb-coach@example.com",
            password="StrongPassword123!",
            assigned_account_role=AssignedAccountRole.COACH,
        )
        club = Club.objects.create_club(name="RB Club", director=director)
        team = Team.objects.create(club=club, name="RB Team")
        TeamMembership.objects.add_member(user=coach, team=team, role=TeamRole.COACH)
        parent_user = User.objects.create_user(
            email="rb-parentuser@example.com",
            password="StrongPassword123!",
            assigned_account_role=AssignedAccountRole.PARENT,
        )
        token = generate_auth_token(coach)
        response = self.client.post(
            reverse("core:add-team-member", kwargs={"team_id": team.id}),
            data=json.dumps({"user_id": parent_user.id, "role": TeamRole.PLAYER}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 403)
