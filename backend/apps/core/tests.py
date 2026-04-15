from datetime import date, time, timedelta
from decimal import Decimal
import json

from django.core import mail
from django.contrib.auth.hashers import check_password
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from django.http import JsonResponse
from django.test import RequestFactory

from .decorators import admin_required
from .attendance_reminders import (
    sweep_incomplete_attendance_reminders,
    sync_incomplete_attendance_notifications_for_session_id,
)
from .models import (
    AssignedAccountRole,
    Club,
    ClubMembership,
    ContactSubmission,
    ClubRole,
    DirectorPaymentAuditLog,
    FeePaymentLedgerEntry,
    Notification,
    ParentLinkApprovalStatus,
    ParentPlayerRelation,
    PaymentSchedule,
    PlayerAccessPolicy,
    PlayerFeeRecord,
    PlayerParentInvitation,
    PlayerParentInvitationStatus,
    PlayerProfile,
    PlayerWeeklySkillMetric,
    RegistrationOTP,
    Team,
    TeamInvitation,
    TeamMembership,
    TeamRole,
    TrainingSession,
    TrainingSessionConfirmation,
    User,
    VerificationStatus,
)
from .permissions import (
    can_player_make_payments,
    can_player_update_own_emergency_contact,
    is_player_parent_managed,
)
from .tokens import generate_auth_token, verify_auth_token


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    EMAIL_HOST_USER="sender@example.com",
    EMAIL_HOST_PASSWORD="secret",
    REGISTRATION_OTP_MINUTES=15,
)
class RegisterEndpointTests(TestCase):
    def test_register_sends_verification_code_without_creating_user(self):
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

        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.count(), 0)
        self.assertIn("verification code", response.json()["message"].lower())

        pending = RegistrationOTP.objects.get(email="player@example.com")
        self.assertEqual(pending.first_name, "Ronnie")
        self.assertEqual(pending.last_name, "Saba")
        self.assertTrue(check_password("StrongPassword123!", pending.password_hash))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("signup verification code", mail.outbox[0].subject.lower())

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

    def test_register_verify_creates_user_and_signs_them_in(self):
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

        self.assertEqual(response.status_code, 200)
        otp = mail.outbox[0].body.split("is: ", 1)[1].split("\n", 1)[0].strip()

        verify_response = self.client.post(
            reverse("core:register-verify"),
            data=json.dumps({"email": "player@example.com", "otp": otp}),
            content_type="application/json",
        )

        self.assertEqual(verify_response.status_code, 201)
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(RegistrationOTP.objects.count(), 0)

        user = User.objects.get(email="player@example.com")
        self.assertEqual(user.first_name, "Ronnie")
        self.assertEqual(user.last_name, "Saba")
        self.assertTrue(user.check_password("StrongPassword123!"))
        self.assertEqual(user.verification_status, VerificationStatus.VERIFIED)

        token = verify_response.json()["token"]
        payload = verify_auth_token(token)
        self.assertEqual(payload["user_id"], user.id)

    def test_register_verify_rejects_invalid_otp(self):
        self.client.post(
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

        response = self.client.post(
            reverse("core:register-verify"),
            data=json.dumps({"email": "player@example.com", "otp": "000000"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(User.objects.count(), 0)


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

    def test_login_allows_legacy_pending_user_now_that_director_approval_is_removed(self):
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

        self.assertEqual(response.status_code, 200)


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
        owned_club.short_name = "NUVC"
        owned_club.save(update_fields=["short_name"])
        coach_club = Club.objects.create_club(
            name="Spike Academy",
            director=User.objects.create_user(
                email="director@example.com",
                password="StrongPassword123!",
                first_name="Club",
                last_name="Director",
            ),
        )
        coach_club.short_name = "SA"
        coach_club.save(update_fields=["short_name"])
        player_club = Club.objects.create_club(
            name="Serve Stars",
            director=User.objects.create_user(
                email="director2@example.com",
                password="StrongPassword123!",
                first_name="Club",
                last_name="Director",
            ),
        )
        player_club.short_name = "SS"
        player_club.save(update_fields=["short_name"])
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
        self.assertEqual(payload["coached_teams"][0]["club_short_name"], coach_club.short_name)
        self.assertEqual(len(payload["player_teams"]), 1)
        self.assertEqual(payload["player_teams"][0]["id"], player_team.id)
        self.assertEqual(payload["player_teams"][0]["club_id"], player_club.id)
        self.assertEqual(payload["player_teams"][0]["club_short_name"], player_club.short_name)
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
                    "description": "Competitive indoor volleyball club.",
                    "city": "Beirut",
                    "country": "Lebanon",
                    "contact_email": "info@netup.com",
                    "contact_phone": "+961-70-123-456",
                    "address": "Ashrafieh Main Street",
                    "founded_year": 2018,
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

    def test_create_club_rejects_empty_name(self):
        user = User.objects.create_user(
            email="director@example.com",
            password="StrongPassword123!",
            first_name="Club",
            last_name="Director",
        )
        token = generate_auth_token(user)

        response = self.client.post(
            reverse("core:create-club"),
            data=json.dumps({"name": "   "}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("name", response.json().get("errors", {}))
        self.assertEqual(Club.objects.count(), 0)

    def test_create_club_requires_all_mandatory_fields_except_description_and_website(self):
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
                    "description": "Optional description only",
                    "website": "https://netup.example.com",
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            set(response.json().get("errors", {}).keys()),
            {
                "short_name",
                "contact_email",
                "contact_phone",
                "country",
                "city",
                "address",
                "founded_year",
            },
        )
        self.assertEqual(Club.objects.count(), 0)

    def test_create_club_rejects_duplicate_name(self):
        user = User.objects.create_user(
            email="director@example.com",
            password="StrongPassword123!",
            first_name="Club",
            last_name="Director",
        )
        other = User.objects.create_user(
            email="other@example.com",
            password="StrongPassword123!",
            first_name="Other",
            last_name="User",
        )
        Club.objects.create_club(name="Existing Club", director=other)
        token = generate_auth_token(user)

        response = self.client.post(
            reverse("core:create-club"),
            data=json.dumps({"name": "Existing Club"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("name", response.json().get("errors", {}))
        self.assertEqual(Club.objects.count(), 1)

    def test_me_endpoint_lists_owned_club_after_create_club(self):
        user = User.objects.create_user(
            email="director@example.com",
            password="StrongPassword123!",
            first_name="Club",
            last_name="Director",
        )
        token = generate_auth_token(user)

        create_response = self.client.post(
            reverse("core:create-club"),
            data=json.dumps({"name": "Fresh Club", "city": "Beirut"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(create_response.status_code, 201)

        me_response = self.client.get(
            reverse("core:me"),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(me_response.status_code, 200)
        payload = me_response.json()
        self.assertEqual(len(payload["owned_clubs"]), 1)
        self.assertEqual(payload["owned_clubs"][0]["name"], "Fresh Club")
        self.assertTrue(payload["is_director_or_staff"])


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
                    "home_venue": "Main Court",
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
                    "home_venue": "Arena 2",
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

    def test_create_team_requires_non_optional_fields(self):
        user = User.objects.create_user(
            email="director-required@example.com",
            password="StrongPassword123!",
            first_name="Club",
            last_name="Director",
        )
        club = Club.objects.create_club(name="Required Team Club", director=user)
        token = generate_auth_token(user)

        response = self.client.post(
            reverse("core:create-team", kwargs={"club_id": club.id}),
            data=json.dumps(
                {
                    "name": "U16 Girls",
                    "season": "2026",
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 400)
        errors = response.json().get("errors", {})
        self.assertIn("short_name", errors)
        self.assertIn("age_group", errors)
        self.assertIn("gender", errors)
        self.assertIn("home_venue", errors)


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


class TeamInvitationEndpointTests(TestCase):
    def test_director_can_invite_coach_role_and_accept_as_coach(self):
        director = User.objects.create_user(
            email="invite-director@example.com",
            password="StrongPassword123!",
        )
        invited = User.objects.create_user(
            email="invite-coach@example.com",
            password="StrongPassword123!",
        )
        club = Club.objects.create_club(name="Invite Club", director=director)
        team = Team.objects.create_team(club=club, name="Invite Team")
        director_token = generate_auth_token(director)

        response = self.client.post(
            reverse("core:invite-team-member", kwargs={"team_id": team.id}),
            data=json.dumps({"email": invited.email, "role": TeamRole.COACH}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {director_token}",
        )

        self.assertEqual(response.status_code, 201)
        invitation = TeamInvitation.objects.get(team=team, invited_email=invited.email)
        self.assertEqual(invitation.role, TeamRole.COACH)

        invited_token = generate_auth_token(invited)
        accept_response = self.client.post(
            reverse("core:respond-team-invitation", kwargs={"code": invitation.code}),
            data=json.dumps({"action": "accept"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {invited_token}",
        )

        self.assertEqual(accept_response.status_code, 200)
        self.assertTrue(
            TeamMembership.objects.active().filter(user=invited, team=team, role=TeamRole.COACH).exists()
        )

    def test_coach_can_only_invite_players(self):
        director = User.objects.create_user(
            email="invite-dir-2@example.com",
            password="StrongPassword123!",
        )
        coach = User.objects.create_user(
            email="invite-coach-2@example.com",
            password="StrongPassword123!",
        )
        club = Club.objects.create_club(name="Coach Invite Club", director=director)
        team = Team.objects.create_team(club=club, name="Coach Invite Team")
        TeamMembership.objects.add_member(user=coach, team=team, role=TeamRole.COACH)
        coach_token = generate_auth_token(coach)

        response = self.client.post(
            reverse("core:invite-team-member", kwargs={"team_id": team.id}),
            data=json.dumps({"email": "newcoach@example.com", "role": TeamRole.COACH}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {coach_token}",
        )

        self.assertEqual(response.status_code, 403)

    def test_team_invitation_rejects_director_role(self):
        director = User.objects.create_user(
            email="invite-dir-3@example.com",
            password="StrongPassword123!",
        )
        club = Club.objects.create_club(name="Director Role Club", director=director)
        team = Team.objects.create_team(club=club, name="Director Role Team")
        token = generate_auth_token(director)

        response = self.client.post(
            reverse("core:invite-team-member", kwargs={"team_id": team.id}),
            data=json.dumps({"email": "clubdirector@example.com", "role": "director"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("role", response.json().get("errors", {}))


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    EMAIL_HOST_USER="sender@example.com",
    EMAIL_HOST_PASSWORD="secret",
)
class PlayerParentInvitationEndpointTests(TestCase):
    def _fixture(self):
        director = User.objects.create_user(
            email="ppi-director@example.com",
            password="StrongPassword123!",
        )
        coach = User.objects.create_user(
            email="ppi-coach@example.com",
            password="StrongPassword123!",
        )
        player = User.objects.create_user(
            email="ppi-player@example.com",
            password="StrongPassword123!",
            first_name="Maya",
            last_name="Player",
            date_of_birth=date(2011, 5, 10),
        )
        parent = User.objects.create_user(
            email="ppi-parent@example.com",
            password="StrongPassword123!",
            first_name="Rana",
            last_name="Parent",
        )
        club = Club.objects.create_club(name="PPI Club", director=director)
        team = Team.objects.create_team(club=club, name="PPI Team")
        TeamMembership.objects.add_member(user=coach, team=team, role=TeamRole.COACH)
        TeamMembership.objects.add_member(user=player, team=team, role=TeamRole.PLAYER)
        return {
            "director": director,
            "coach": coach,
            "player": player,
            "parent": parent,
            "club": club,
            "team": team,
        }

    def test_player_parent_invitation_requires_only_one_approval_before_acceptance(self):
        fx = self._fixture()
        player_token = generate_auth_token(fx["player"])

        create_response = self.client.post(
            reverse("core:request-player-parent-invitation"),
            data=json.dumps({"email": fx["parent"].email}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {player_token}",
        )

        self.assertEqual(create_response.status_code, 201)
        invite = PlayerParentInvitation.objects.get(player=fx["player"], invited_email=fx["parent"].email)
        self.assertEqual(invite.status, PlayerParentInvitationStatus.PENDING_APPROVAL)

        coach_token = generate_auth_token(fx["coach"])
        coach_response = self.client.post(
            reverse("core:resolve-player-parent-invitation", kwargs={"invitation_id": invite.id}),
            data=json.dumps({"action": "approve"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {coach_token}",
        )
        self.assertEqual(coach_response.status_code, 200)
        invite.refresh_from_db()
        self.assertIsNotNone(invite.coach_approved_at)
        self.assertIsNone(invite.director_approved_at)
        self.assertEqual(invite.status, PlayerParentInvitationStatus.PENDING_PARENT_RESPONSE)
        self.assertEqual(len(mail.outbox), 1)

        detail_response = self.client.get(reverse("core:invitation-detail", kwargs={"code": invite.code}))
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.json()["invitation"]["kind"], "parent_link")

        parent_token = generate_auth_token(fx["parent"])
        accept_response = self.client.post(
            reverse("core:respond-team-invitation", kwargs={"code": invite.code}),
            data=json.dumps({"action": "accept"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {parent_token}",
        )
        self.assertEqual(accept_response.status_code, 200)
        invite.refresh_from_db()
        self.assertEqual(invite.status, PlayerParentInvitationStatus.ACCEPTED)
        self.assertTrue(
            ParentPlayerRelation.objects.approved().filter(parent=fx["parent"], player=fx["player"]).exists()
        )

    def test_player_parent_invitation_third_parent_is_rejected(self):
        fx = self._fixture()
        other_parent = User.objects.create_user(
            email="ppi-parent-2@example.com",
            password="StrongPassword123!",
        )
        ParentPlayerRelation.objects.link(
            parent=fx["parent"],
            player=fx["player"],
            approval_status=ParentLinkApprovalStatus.APPROVED,
        )
        PlayerParentInvitation.objects.create(
            player=fx["player"],
            requested_by=fx["player"],
            invited_parent=other_parent,
            invited_email=other_parent.email,
            status=PlayerParentInvitationStatus.PENDING_APPROVAL,
        )
        player_token = generate_auth_token(fx["player"])

        response = self.client.post(
            reverse("core:request-player-parent-invitation"),
            data=json.dumps({"email": "ppi-parent-3@example.com"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {player_token}",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.json().get("errors", {}))


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

    def test_payment_overview_empty_club_returns_stable_json_shape(self):
        director = User.objects.create_user(
            email="dir-empty-overview@example.com",
            password="StrongPassword123!",
        )
        club = Club.objects.create_club(name="Empty Overview Club", director=director)
        token = generate_auth_token(director)
        response = self.client.get(
            reverse("core:director-payment-overview", kwargs={"club_id": club.id}),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("club", data)
        self.assertIn("kpis", data)
        self.assertEqual(data["kpis"]["registration_player_count"], 0)
        self.assertEqual(data["kpis"]["outstanding_payer_count"], 0)
        self.assertIsNone(data["kpis"]["attendance_rate"])
        self.assertEqual(data["payments_overview"], [])
        self.assertEqual(data["family_summaries"], [])
        self.assertIn("roles_permission_matrix", data)
        self.assertIn("rows", data["roles_permission_matrix"])
        self.assertTrue(data["roles_permission_matrix"]["rows"])
        self.assertIn("club_summary", data)
        self.assertIn("attendance_trend_30d", data)
        self.assertIn("points", data["attendance_trend_30d"])
        self.assertEqual(len(data["attendance_trend_30d"]["points"]), 30)

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


class CoachTeamDashboardApiTests(TestCase):
    def test_coach_dashboard_includes_has_skill_metrics_flag(self):
        director = User.objects.create_user(
            email="dir-coach-dash@example.com",
            password="StrongPassword123!",
        )
        coach = User.objects.create_user(
            email="coach-dash-api@example.com",
            password="StrongPassword123!",
        )
        club = Club.objects.create_club(name="Coach Dash Club", director=director)
        team = Team.objects.create_team(club=club, name="Dash Team", season="2026")
        TeamMembership.objects.add_member(user=coach, team=team, role=TeamRole.COACH)
        token = generate_auth_token(coach)
        response = self.client.get(
            reverse("core:coach-team-dashboard", kwargs={"team_id": team.id}),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("has_skill_metrics", data)
        self.assertFalse(data["has_skill_metrics"])
        self.assertIn("kpis", data)
        self.assertIn("attendance_vs_performance", data)
        self.assertEqual(data["player_stats"], [])
        self.assertEqual(data["recent_feedback"], [])

    def test_coach_dashboard_includes_team_scoped_workspace_overview(self):
        director = User.objects.create_user(
            email="dir-coach-team-overview@example.com",
            password="StrongPassword123!",
        )
        coach = User.objects.create_user(
            email="coach-team-overview@example.com",
            password="StrongPassword123!",
        )
        player = User.objects.create_user(
            email="player-team-overview@example.com",
            password="StrongPassword123!",
            first_name="Ava",
            last_name="Player",
        )
        club = Club.objects.create_club(name="Coach Team Club", director=director)
        team = Team.objects.create_team(club=club, name="Falcons", season="2026")
        TeamMembership.objects.add_member(user=coach, team=team, role=TeamRole.COACH)
        TeamMembership.objects.add_member(user=player, team=team, role=TeamRole.PLAYER)

        yesterday = timezone.localdate() - timedelta(days=1)
        session = TrainingSession.objects.create(
            team=team,
            title="Team Practice",
            session_type=TrainingSession.SessionType.TRAINING,
            scheduled_date=yesterday,
            start_time=time(18, 0),
            end_time=time(19, 30),
            status=TrainingSession.Status.SCHEDULED,
            created_by=coach,
        )
        TrainingSessionConfirmation.objects.create(training_session=session, player=player)

        record = PlayerFeeRecord.objects.create(
            club=club,
            player=player,
            team=team,
            description="April Team Fee",
            amount_due=Decimal("120.00"),
            amount_paid=Decimal("60.00"),
            currency="USD",
            due_date=timezone.localdate(),
            billing_period_start=timezone.localdate().replace(day=1),
        )
        FeePaymentLedgerEntry.objects.create(fee_record=record, amount=Decimal("60.00"), note="partial")

        token = generate_auth_token(coach)
        response = self.client.get(
            reverse("core:coach-team-dashboard", kwargs={"team_id": team.id}),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("workspace_overview", data)
        overview = data["workspace_overview"]
        self.assertEqual(overview["kpis"]["registration_player_count"], 1)
        self.assertEqual(Decimal(overview["kpis"]["monthly_revenue"]), Decimal("60.00"))
        self.assertEqual(overview["kpis"]["outstanding_payer_count"], 1)
        self.assertEqual(len(overview["attendance_trend_30d"]["points"]), 30)
        self.assertEqual(overview["payments_overview"][0]["family_label"], "Ava Player")
        self.assertEqual(overview["team_summary"]["best_participating_team"]["team_name"], "Falcons")


class DirectorDashboardOverviewTests(TestCase):
    def test_overview_includes_trend_roles_club_summary_and_payments_overview(self):
        director = User.objects.create_user(
            email="dash-ext@example.com",
            password="StrongPassword123!",
        )
        club = Club.objects.create_club(name="Dash Ext Club", director=director)
        token = generate_auth_token(director)
        response = self.client.get(
            reverse("core:director-payment-overview", kwargs={"club_id": club.id}),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("attendance_trend_30d", data)
        self.assertEqual(len(data["attendance_trend_30d"]["points"]), 30)
        self.assertIn("roles_permission_matrix", data)
        self.assertEqual(len(data["roles_permission_matrix"]["rows"]), 3)
        self.assertIn("club_summary", data)
        self.assertIn("payments_overview", data)

    def test_attendance_trend_day_matches_closed_session_slots(self):
        director = User.objects.create_user(
            email="dash-trend@example.com",
            password="StrongPassword123!",
        )
        club = Club.objects.create_club(name="Trend Club", director=director)
        player = User.objects.create_user(
            email="trend-player@example.com",
            password="StrongPassword123!",
        )
        team = Team.objects.create_team(club=club, name="Trend Team", season="2026")
        TeamMembership.objects.add_member(user=player, team=team, role=TeamRole.PLAYER)
        past = timezone.localdate() - timedelta(days=2)
        session = TrainingSession.objects.create(
            team=team,
            title="Trend practice",
            session_type=TrainingSession.SessionType.TRAINING,
            scheduled_date=past,
            start_time=time(18, 0),
            end_time=time(19, 30),
            location="Gym",
        )
        TrainingSessionConfirmation.objects.create(
            training_session=session,
            player=player,
            confirmed_by=director,
        )
        token = generate_auth_token(director)
        response = self.client.get(
            reverse("core:director-payment-overview", kwargs={"club_id": club.id}),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        points = response.json()["attendance_trend_30d"]["points"]
        day = next(p for p in points if p["date"] == past.isoformat())
        self.assertEqual(day["closed_slots"], 1)
        self.assertEqual(day["attended_slots"], 1)
        self.assertEqual(day["rate_percent"], 100.0)

    def test_monthly_revenue_matches_ledger_and_payments_overview_columns(self):
        director = User.objects.create_user(
            email="dash-rev@example.com",
            password="StrongPassword123!",
        )
        club = Club.objects.create_club(name="Rev Club", director=director)
        player = User.objects.create_user(
            email="rev-player@example.com",
            password="StrongPassword123!",
            first_name="Rev",
            last_name="Player",
        )
        team = Team.objects.create_team(club=club, name="Rev Team", season="2026")
        TeamMembership.objects.add_member(user=player, team=team, role=TeamRole.PLAYER)
        rec = PlayerFeeRecord.objects.create(
            club=club,
            player=player,
            team=team,
            description="Fee",
            amount_due=Decimal("50.00"),
            amount_paid=Decimal("20.00"),
            due_date=timezone.localdate(),
        )
        FeePaymentLedgerEntry.objects.create(fee_record=rec, amount=Decimal("20.00"), note="t")
        token = generate_auth_token(director)
        response = self.client.get(
            reverse("core:director-payment-overview", kwargs={"club_id": club.id}),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(Decimal(data["kpis"]["monthly_revenue"]), Decimal("20.00"))
        row = next(r for r in data["payments_overview"] if r["player_id"] == player.id)
        self.assertEqual(Decimal(row["total_paid"]), Decimal("20.00"))
        self.assertEqual(Decimal(row["total_remaining"]), Decimal("30.00"))

    def test_club_summary_identifies_best_and_low_team(self):
        director = User.objects.create_user(
            email="dash-balance@example.com",
            password="StrongPassword123!",
        )
        club = Club.objects.create_club(name="Balance Club", director=director)
        good = User.objects.create_user(email="good-p@example.com", password="StrongPassword123!")
        bad = User.objects.create_user(email="bad-p@example.com", password="StrongPassword123!")
        team_high = Team.objects.create_team(club=club, name="High Att Team", season="2026")
        team_low = Team.objects.create_team(club=club, name="Low Att Team", season="2026")
        TeamMembership.objects.add_member(user=good, team=team_high, role=TeamRole.PLAYER)
        TeamMembership.objects.add_member(user=bad, team=team_low, role=TeamRole.PLAYER)
        past_base = timezone.localdate() - timedelta(days=10)
        for i in range(2):
            s = TrainingSession.objects.create(
                team=team_high,
                title=f"High {i}",
                session_type=TrainingSession.SessionType.TRAINING,
                scheduled_date=past_base - timedelta(days=i),
                start_time=time(18, 0),
                end_time=time(19, 0),
                location="A",
            )
            TrainingSessionConfirmation.objects.create(
                training_session=s,
                player=good,
                confirmed_by=director,
            )
        for j in range(4):
            TrainingSession.objects.create(
                team=team_low,
                title=f"Low {j}",
                session_type=TrainingSession.SessionType.TRAINING,
                scheduled_date=past_base - timedelta(days=j + 3),
                start_time=time(18, 0),
                end_time=time(19, 0),
                location="B",
            )
        token = generate_auth_token(director)
        response = self.client.get(
            reverse("core:director-payment-overview", kwargs={"club_id": club.id}),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        summary = response.json()["club_summary"]
        self.assertEqual(summary["best_participating_team"]["team_id"], team_high.id)
        self.assertEqual(summary["low_participation"]["team_id"], team_low.id)
        self.assertIn("Low Att Team", summary["low_participation"]["message"])

    def test_overview_empty_club_has_no_attendance_denominator(self):
        director = User.objects.create_user(
            email="dash-empty@example.com",
            password="StrongPassword123!",
        )
        club = Club.objects.create_club(name="Empty Dash Club", director=director)
        token = generate_auth_token(director)
        response = self.client.get(
            reverse("core:director-payment-overview", kwargs={"club_id": club.id}),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsNone(data["kpis"]["attendance_rate"])
        self.assertEqual(data["kpis"]["registration_player_count"], 0)
        self.assertEqual(data["kpis"]["outstanding_payer_count"], 0)
        self.assertFalse(any(p["closed_slots"] > 0 for p in data["attendance_trend_30d"]["points"]))
        self.assertIsNone(data["club_summary"]["best_participating_team"])
        self.assertIsNone(data["club_summary"]["low_participation"])

    def test_overview_rejects_non_director(self):
        director = User.objects.create_user(
            email="dash-denied-dir@example.com",
            password="StrongPassword123!",
        )
        club = Club.objects.create_club(name="Denied Dash Club", director=director)
        other = User.objects.create_user(email="dash-denied-other@example.com", password="StrongPassword123!")
        token = generate_auth_token(other)
        response = self.client.get(
            reverse("core:director-payment-overview", kwargs={"club_id": club.id}),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 403)


class DirectorUserDirectoryApiTests(TestCase):
    def test_directory_forbidden_for_user_without_director_or_coach_scope(self):
        u = User.objects.create_user(email="nodir@example.com", password="StrongPassword123!")
        token = generate_auth_token(u)
        response = self.client.get(
            reverse("core:directors-user-directory"),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 403)

    def test_directory_scopes_rows_to_directors_own_club(self):
        director = User.objects.create_user(
            email="dir-dirlist@example.com",
            password="StrongPassword123!",
        )
        club = Club.objects.create_club(name="Dir List Club", director=director)
        team = Team.objects.create_team(club=club, name="Dir List Team")
        target = User.objects.create_user(
            email="target-role@example.com",
            password="StrongPassword123!",
            first_name="Tar",
            last_name="Get",
            verification_status=VerificationStatus.VERIFIED,
        )
        TeamMembership.objects.add_member(user=target, team=team, role=TeamRole.PLAYER)
        parent = User.objects.create_user(
            email="club-parent@example.com",
            password="StrongPassword123!",
            verification_status=VerificationStatus.VERIFIED,
        )
        ParentPlayerRelation.objects.link(
            parent=parent,
            player=target,
            approval_status=ParentLinkApprovalStatus.APPROVED,
        )
        other_director = User.objects.create_user(
            email="other-director@example.com",
            password="StrongPassword123!",
        )
        other_club = Club.objects.create_club(name="Other Club", director=other_director)
        other_team = Team.objects.create_team(club=other_club, name="Other Team")
        outsider = User.objects.create_user(
            email="outsider@example.com",
            password="StrongPassword123!",
            verification_status=VerificationStatus.VERIFIED,
        )
        TeamMembership.objects.add_member(user=outsider, team=other_team, role=TeamRole.PLAYER)

        token = generate_auth_token(director)
        response = self.client.get(
            reverse("core:directors-user-directory"),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["scope"]["kind"], "club")
        ids = {row["id"] for row in data["users"]}
        self.assertIn(director.id, ids)
        self.assertIn(target.id, ids)
        self.assertIn(parent.id, ids)
        self.assertNotIn(outsider.id, ids)
        target_row = next(row for row in data["users"] if row["id"] == target.id)
        self.assertEqual(target_row["team_short_names"], [team.name])

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

    def test_directory_scopes_rows_to_coachs_own_team(self):
        director = User.objects.create_user(
            email="scope-dir@example.com",
            password="StrongPassword123!",
        )
        club = Club.objects.create_club(name="Scope Club", director=director)
        team_a = Team.objects.create_team(club=club, name="Team A")
        team_b = Team.objects.create_team(club=club, name="Team B")
        coach = User.objects.create_user(
            email="coach-scope@example.com",
            password="StrongPassword123!",
        )
        TeamMembership.objects.add_member(user=coach, team=team_a, role=TeamRole.COACH)
        player_a = User.objects.create_user(
            email="player-a@example.com",
            password="StrongPassword123!",
            verification_status=VerificationStatus.VERIFIED,
        )
        TeamMembership.objects.add_member(user=player_a, team=team_a, role=TeamRole.PLAYER)
        parent_a = User.objects.create_user(
            email="parent-a@example.com",
            password="StrongPassword123!",
            verification_status=VerificationStatus.VERIFIED,
        )
        ParentPlayerRelation.objects.link(
            parent=parent_a,
            player=player_a,
            approval_status=ParentLinkApprovalStatus.APPROVED,
        )
        player_b = User.objects.create_user(
            email="player-b@example.com",
            password="StrongPassword123!",
            verification_status=VerificationStatus.VERIFIED,
        )
        TeamMembership.objects.add_member(user=player_b, team=team_b, role=TeamRole.PLAYER)

        token = generate_auth_token(coach)
        response = self.client.get(
            reverse("core:directors-user-directory"),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["scope"]["kind"], "team")
        ids = {row["id"] for row in data["users"]}
        self.assertIn(coach.id, ids)
        self.assertIn(player_a.id, ids)
        self.assertIn(parent_a.id, ids)
        self.assertNotIn(player_b.id, ids)

    def test_directory_can_filter_director_scope_to_focused_team(self):
        director = User.objects.create_user(
            email="focused-dir@example.com",
            password="StrongPassword123!",
        )
        club = Club.objects.create_club(name="Focused Club", director=director)
        team_a = Team.objects.create_team(club=club, name="Focus A")
        team_b = Team.objects.create_team(club=club, name="Focus B")
        player_a = User.objects.create_user(
            email="focus-a@example.com",
            password="StrongPassword123!",
            verification_status=VerificationStatus.VERIFIED,
        )
        player_b = User.objects.create_user(
            email="focus-b@example.com",
            password="StrongPassword123!",
            verification_status=VerificationStatus.VERIFIED,
        )
        TeamMembership.objects.add_member(user=player_a, team=team_a, role=TeamRole.PLAYER)
        TeamMembership.objects.add_member(user=player_b, team=team_b, role=TeamRole.PLAYER)

        token = generate_auth_token(director)
        response = self.client.get(
            f'{reverse("core:directors-user-directory")}?team_id={team_a.id}',
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["scope"]["kind"], "team")
        self.assertEqual(data["scope"]["team_id"], team_a.id)
        ids = {row["id"] for row in data["users"]}
        self.assertIn(player_a.id, ids)
        self.assertNotIn(player_b.id, ids)
        player_row = next(row for row in data["users"] if row["id"] == player_a.id)
        self.assertEqual(player_row["team_short_names"], [team_a.name])

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

    def test_director_can_remove_player_from_team_via_directory_action(self):
        director = User.objects.create_user(
            email="dir-remove@example.com",
            password="StrongPassword123!",
        )
        club = Club.objects.create_club(name="Remove Club", director=director)
        team = Team.objects.create_team(club=club, name="Remove Team")
        player = User.objects.create_user(
            email="remove-player@example.com",
            password="StrongPassword123!",
            verification_status=VerificationStatus.VERIFIED,
        )
        TeamMembership.objects.add_member(user=player, team=team, role=TeamRole.PLAYER)

        token = generate_auth_token(director)
        response = self.client.post(
            reverse("core:directors-remove-player-from-team", kwargs={"user_id": player.id}),
            data=json.dumps({"team_id": team.id}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            TeamMembership.objects.active()
            .filter(user=player, team=team, role=TeamRole.PLAYER)
            .exists()
        )

    def test_coach_can_remove_player_from_directory_action_for_own_team(self):
        director = User.objects.create_user(
            email="dir-no-remove@example.com",
            password="StrongPassword123!",
        )
        club = Club.objects.create_club(name="Coach Remove Club", director=director)
        team = Team.objects.create_team(club=club, name="Coach Remove Team")
        coach = User.objects.create_user(
            email="coach-no-remove@example.com",
            password="StrongPassword123!",
        )
        player = User.objects.create_user(
            email="player-no-remove@example.com",
            password="StrongPassword123!",
            verification_status=VerificationStatus.VERIFIED,
        )
        TeamMembership.objects.add_member(user=coach, team=team, role=TeamRole.COACH)
        TeamMembership.objects.add_member(user=player, team=team, role=TeamRole.PLAYER)

        token = generate_auth_token(coach)
        response = self.client.post(
            reverse("core:directors-remove-player-from-team", kwargs={"user_id": player.id}),
            data=json.dumps({"team_id": team.id}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            TeamMembership.objects.active()
            .filter(user=player, team=team, role=TeamRole.PLAYER)
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


class ParentChildAttendanceHistoryTests(TestCase):
    """EP-23: parent-only attendance history derived from training sessions and confirmations."""

    def _setup_team_with_parent_child(self):
        director = User.objects.create_user(email="att-dir@example.com", password="StrongPassword123!")
        club = Club.objects.create_club(name="Att Club", director=director)
        team = Team.objects.create(club=club, name="Att Team")
        child = User.objects.create_user(
            email="att-child@example.com",
            password="StrongPassword123!",
            assigned_account_role=AssignedAccountRole.PLAYER,
        )
        parent = User.objects.create_user(
            email="att-par@example.com",
            password="StrongPassword123!",
            assigned_account_role=AssignedAccountRole.PARENT,
        )
        TeamMembership.objects.add_member(user=child, team=team, role=TeamRole.PLAYER)
        ParentPlayerRelation.objects.link(parent=parent, player=child, approval_status=ParentLinkApprovalStatus.APPROVED)
        return parent, child, team, club

    def test_requires_authentication(self):
        response = self.client.get(reverse("core:parent-child-attendance"))
        self.assertEqual(response.status_code, 401)

    def test_non_parent_forbidden(self):
        director = User.objects.create_user(email="att-np-dir@example.com", password="StrongPassword123!")
        Club.objects.create_club(name="Att NP Club", director=director)
        token = generate_auth_token(director)
        response = self.client.get(
            reverse("core:parent-child-attendance"),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 403)

    def test_parent_without_link_returns_empty_payload(self):
        parent = User.objects.create_user(
            email="att-nolink@example.com",
            password="StrongPassword123!",
            assigned_account_role=AssignedAccountRole.PARENT,
        )
        token = generate_auth_token(parent)
        response = self.client.get(
            reverse("core:parent-child-attendance"),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["records"], [])
        self.assertEqual(data["linked_children"], [])
        self.assertEqual(data.get("attendance_summaries", []), [])
        self.assertIn("message", data)

    def test_parent_sees_attendance_for_linked_child(self):
        parent, child, team, _club = self._setup_team_with_parent_child()
        today = timezone.localdate()
        past = today - timedelta(days=3)
        future = today + timedelta(days=3)
        session_past = TrainingSession.objects.create(
            team=team,
            title="Past practice",
            session_type=TrainingSession.SessionType.TRAINING,
            scheduled_date=past,
            start_time=time(18, 0),
            end_time=time(19, 30),
            location="Main gym",
        )
        session_future = TrainingSession.objects.create(
            team=team,
            title="Future match",
            session_type=TrainingSession.SessionType.MATCH,
            scheduled_date=future,
            start_time=time(10, 0),
            end_time=time(12, 0),
            opponent="Rivals",
        )
        TrainingSessionConfirmation.objects.create(
            training_session=session_past,
            player=child,
            confirmed_by=parent,
        )
        token = generate_auth_token(parent)
        response = self.client.get(
            reverse("core:parent-child-attendance"),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["records"]), 2)
        by_sid = {row["session_id"]: row for row in data["records"]}
        self.assertEqual(by_sid[session_past.id]["attendance_status"], "present")
        self.assertEqual(by_sid[session_past.id]["attendance_label"], "Present")
        self.assertEqual(by_sid[session_future.id]["attendance_status"], "pending")
        self.assertEqual(by_sid[session_future.id]["session_type"], "match")
        self.assertEqual(by_sid[session_future.id]["child"]["id"], child.id)
        summaries = data.get("attendance_summaries") or []
        self.assertEqual(len(summaries), 1)
        self.assertEqual(summaries[0]["child"]["id"], child.id)
        self.assertEqual(summaries[0]["team"]["id"], team.id)
        self.assertIn("metrics", summaries[0])
        self.assertEqual(summaries[0]["metrics"]["attended_sessions"], 1)
        self.assertEqual(summaries[0]["metrics"]["pending_sessions"], 1)

    def test_parent_does_not_see_unlinked_child_sessions(self):
        director = User.objects.create_user(email="att-idor-dir@example.com", password="StrongPassword123!")
        club = Club.objects.create_club(name="Att IDOR Club", director=director)
        team = Team.objects.create(club=club, name="Att IDOR Team")
        child_a = User.objects.create_user(
            email="att-child-a@example.com",
            password="StrongPassword123!",
            assigned_account_role=AssignedAccountRole.PLAYER,
        )
        child_b = User.objects.create_user(
            email="att-child-b@example.com",
            password="StrongPassword123!",
            assigned_account_role=AssignedAccountRole.PLAYER,
        )
        parent_a = User.objects.create_user(
            email="att-par-a@example.com",
            password="StrongPassword123!",
            assigned_account_role=AssignedAccountRole.PARENT,
        )
        TeamMembership.objects.add_member(user=child_a, team=team, role=TeamRole.PLAYER)
        TeamMembership.objects.add_member(user=child_b, team=team, role=TeamRole.PLAYER)
        ParentPlayerRelation.objects.link(parent=parent_a, player=child_a, approval_status=ParentLinkApprovalStatus.APPROVED)
        today = timezone.localdate()
        session = TrainingSession.objects.create(
            team=team,
            title="Team session",
            session_type=TrainingSession.SessionType.TRAINING,
            scheduled_date=today,
            start_time=time(18, 0),
            end_time=time(19, 30),
        )
        TrainingSessionConfirmation.objects.create(
            training_session=session,
            player=child_b,
            confirmed_by=parent_a,
        )
        token = generate_auth_token(parent_a)
        response = self.client.get(
            reverse("core:parent-child-attendance"),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        rows = response.json()["records"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["child"]["id"], child_a.id)
        self.assertEqual(rows[0]["attendance_status"], "pending")

    def test_empty_history_when_no_sessions(self):
        parent, child, _team, _club = self._setup_team_with_parent_child()
        token = generate_auth_token(parent)
        response = self.client.get(
            reverse("core:parent-child-attendance"),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["records"], [])
        summaries = body.get("attendance_summaries") or []
        self.assertEqual(len(summaries), 1)
        self.assertEqual(summaries[0]["metrics"]["sessions_in_date_range"], 0)


class PlayerAttendanceConfirmationTests(TestCase):
    """EP-24: player self-confirm for training sessions (assigned Player role, 14+)."""

    def _fixture_team_and_session(self, *, player_dob, player_assigned_role=AssignedAccountRole.PLAYER):
        director = User.objects.create_user(email="ep24-dir@example.com", password="StrongPassword123!")
        club = Club.objects.create_club(name="EP24 Club", director=director)
        team = Team.objects.create(club=club, name="EP24 Team")
        coach = User.objects.create_user(
            email="ep24-coach@example.com",
            password="StrongPassword123!",
            assigned_account_role=AssignedAccountRole.COACH,
        )
        TeamMembership.objects.add_member(user=coach, team=team, role=TeamRole.COACH)
        player = User.objects.create_user(
            email="ep24-player@example.com",
            password="StrongPassword123!",
            assigned_account_role=player_assigned_role,
            date_of_birth=player_dob,
        )
        TeamMembership.objects.add_member(user=player, team=team, role=TeamRole.PLAYER)
        other = User.objects.create_user(
            email="ep24-other@example.com",
            password="StrongPassword123!",
            assigned_account_role=AssignedAccountRole.PLAYER,
            date_of_birth=date(2006, 1, 1),
        )
        TeamMembership.objects.add_member(user=other, team=team, role=TeamRole.PLAYER)
        today = timezone.localdate()
        session = TrainingSession.objects.create(
            team=team,
            title="Practice",
            session_type=TrainingSession.SessionType.TRAINING,
            scheduled_date=today + timedelta(days=1),
            start_time=time(18, 0),
            end_time=time(19, 30),
        )
        return team, session, player, other, coach

    def test_authenticated_player_can_confirm_valid_session(self):
        _team, session, player, _other, _coach = self._fixture_team_and_session(player_dob=date(2008, 5, 1))
        token = generate_auth_token(player)
        response = self.client.post(
            reverse("core:confirm-training-session", kwargs={"session_id": session.id}),
            data=json.dumps({}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("session", data)
        mine = next(
            row
            for row in data["session"]["player_confirmations"]
            if row["player_id"] == player.id
        )
        self.assertTrue(mine["is_confirmed"])

    def test_player_can_update_existing_confirmation(self):
        _team, session, player, _other, _coach = self._fixture_team_and_session(player_dob=date(2007, 1, 1))
        TrainingSessionConfirmation.objects.create(
            training_session=session,
            player=player,
            confirmed_by=player,
        )
        token = generate_auth_token(player)
        response = self.client.post(
            reverse("core:confirm-training-session", kwargs={"session_id": session.id}),
            data=json.dumps({}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(TrainingSessionConfirmation.objects.filter(training_session=session, player=player).count(), 1)

    def test_player_cannot_confirm_for_teammate(self):
        _team, session, player, other, _coach = self._fixture_team_and_session(player_dob=date(2007, 1, 1))
        token = generate_auth_token(player)
        response = self.client.post(
            reverse("core:confirm-training-session", kwargs={"session_id": session.id}),
            data=json.dumps({"player_id": other.id}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 403)

    def test_unauthenticated_rejected(self):
        _team, session, _player, _other, _coach = self._fixture_team_and_session(player_dob=date(2007, 1, 1))
        response = self.client.post(
            reverse("core:confirm-training-session", kwargs={"session_id": session.id}),
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    def test_non_player_assigned_role_cannot_self_confirm_even_on_roster(self):
        """Coach-assigned account cannot self-confirm as a player (EP-24)."""
        _team, session, player, _other, _coach = self._fixture_team_and_session(
            player_dob=date(2006, 1, 1),
            player_assigned_role=AssignedAccountRole.COACH,
        )
        token = generate_auth_token(player)
        response = self.client.post(
            reverse("core:confirm-training-session", kwargs={"session_id": session.id}),
            data=json.dumps({}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 403)

    def test_invalid_session_returns_404(self):
        director = User.objects.create_user(email="ep24-idir@example.com", password="StrongPassword123!")
        club = Club.objects.create_club(name="EP24 Club X", director=director)
        team = Team.objects.create(club=club, name="EP24 Team X")
        player = User.objects.create_user(
            email="ep24-pl@example.com",
            password="StrongPassword123!",
            assigned_account_role=AssignedAccountRole.PLAYER,
            date_of_birth=date(2006, 1, 1),
        )
        TeamMembership.objects.add_member(user=player, team=team, role=TeamRole.PLAYER)
        token = generate_auth_token(player)
        response = self.client.post(
            reverse("core:confirm-training-session", kwargs={"session_id": 999999}),
            data=json.dumps({}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 404)

    def test_session_outside_player_scope_rejected(self):
        director = User.objects.create_user(email="ep24-idir2@example.com", password="StrongPassword123!")
        club = Club.objects.create_club(name="EP24 Club Y", director=director)
        team_a = Team.objects.create(club=club, name="Team A")
        team_b = Team.objects.create(club=club, name="Team B")
        player = User.objects.create_user(
            email="ep24-pl2@example.com",
            password="StrongPassword123!",
            assigned_account_role=AssignedAccountRole.PLAYER,
            date_of_birth=date(2006, 1, 1),
        )
        TeamMembership.objects.add_member(user=player, team=team_a, role=TeamRole.PLAYER)
        today = timezone.localdate()
        session_b = TrainingSession.objects.create(
            team=team_b,
            title="Other practice",
            session_type=TrainingSession.SessionType.TRAINING,
            scheduled_date=today + timedelta(days=1),
            start_time=time(18, 0),
            end_time=time(19, 30),
        )
        token = generate_auth_token(player)
        response = self.client.post(
            reverse("core:confirm-training-session", kwargs={"session_id": session_b.id}),
            data=json.dumps({}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 403)


class CoachTrainingSessionAttendanceTests(TestCase):
    """EP-25: coach/director session attendance planning endpoint."""

    def _fixture(self):
        director = User.objects.create_user(email="ep25-dir@example.com", password="StrongPassword123!")
        club = Club.objects.create_club(name="EP25 Club", director=director)
        team_a = Team.objects.create(club=club, name="EP25 Team A")
        team_b = Team.objects.create(club=club, name="EP25 Team B")
        coach = User.objects.create_user(
            email="ep25-coach@example.com",
            password="StrongPassword123!",
            assigned_account_role=AssignedAccountRole.COACH,
        )
        other_coach = User.objects.create_user(
            email="ep25-coach-b@example.com",
            password="StrongPassword123!",
            assigned_account_role=AssignedAccountRole.COACH,
        )
        player = User.objects.create_user(
            email="ep25-player@example.com",
            password="StrongPassword123!",
            assigned_account_role=AssignedAccountRole.PLAYER,
            date_of_birth=date(2007, 1, 1),
        )
        player_b = User.objects.create_user(
            email="ep25-player-b@example.com",
            password="StrongPassword123!",
            assigned_account_role=AssignedAccountRole.PLAYER,
            date_of_birth=date(2007, 2, 1),
        )
        parent = User.objects.create_user(
            email="ep25-parent@example.com",
            password="StrongPassword123!",
            assigned_account_role=AssignedAccountRole.PARENT,
        )
        TeamMembership.objects.add_member(user=coach, team=team_a, role=TeamRole.COACH)
        TeamMembership.objects.add_member(user=other_coach, team=team_b, role=TeamRole.COACH)
        TeamMembership.objects.add_member(user=player, team=team_a, role=TeamRole.PLAYER)
        TeamMembership.objects.add_member(user=player_b, team=team_a, role=TeamRole.PLAYER)
        ParentPlayerRelation.objects.link(parent=parent, player=player)
        today = timezone.localdate()
        session_future = TrainingSession.objects.create(
            team=team_a,
            title="Future practice",
            session_type=TrainingSession.SessionType.TRAINING,
            scheduled_date=today + timedelta(days=2),
            start_time=time(18, 0),
            end_time=time(19, 30),
        )
        session_past = TrainingSession.objects.create(
            team=team_a,
            title="Past practice",
            session_type=TrainingSession.SessionType.TRAINING,
            scheduled_date=today - timedelta(days=3),
            start_time=time(18, 0),
            end_time=time(19, 30),
        )
        PlayerProfile.objects.update_or_create(
            user=player,
            defaults={"jersey_number": 9, "primary_position": "Setter"},
        )
        return {
            "director": director,
            "club": club,
            "team_a": team_a,
            "team_b": team_b,
            "coach": coach,
            "other_coach": other_coach,
            "player": player,
            "player_b": player_b,
            "parent": parent,
            "session_future": session_future,
            "session_past": session_past,
        }

    def test_coach_can_view_attendance_for_own_team_session(self):
        fx = self._fixture()
        TrainingSessionConfirmation.objects.create(
            training_session=fx["session_future"],
            player=fx["player"],
            confirmed_by=fx["player"],
        )
        token = generate_auth_token(fx["coach"])
        response = self.client.get(
            reverse("core:coach-training-session-attendance", kwargs={"session_id": fx["session_future"].id}),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()["session"]
        self.assertEqual(body["team"]["id"], fx["team_a"].id)
        self.assertEqual(body["summary"]["roster_size"], 2)
        self.assertEqual(body["summary"]["present_count"], 1)
        self.assertEqual(body["summary"]["pending_count"], 1)
        self.assertEqual(body["summary"]["absent_count"], 0)
        by_id = {row["player_id"]: row for row in body["players"]}
        self.assertEqual(by_id[fx["player"].id]["attendance_status"], "present")
        self.assertEqual(by_id[fx["player_b"].id]["attendance_status"], "pending")
        self.assertEqual(by_id[fx["player"].id]["jersey_number"], 9)
        self.assertEqual(by_id[fx["player"].id]["primary_position"], "Setter")

    def test_roster_players_listed_when_some_not_confirmed(self):
        fx = self._fixture()
        token = generate_auth_token(fx["coach"])
        response = self.client.get(
            reverse("core:coach-training-session-attendance", kwargs={"session_id": fx["session_future"].id}),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        players = response.json()["session"]["players"]
        self.assertEqual(len(players), 2)
        self.assertTrue(all(not p["is_confirmed"] for p in players))
        self.assertEqual(response.json()["session"]["summary"]["pending_count"], 2)

    def test_other_team_coach_forbidden(self):
        fx = self._fixture()
        token = generate_auth_token(fx["other_coach"])
        response = self.client.get(
            reverse("core:coach-training-session-attendance", kwargs={"session_id": fx["session_future"].id}),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 403)

    def test_unauthenticated_rejected(self):
        fx = self._fixture()
        response = self.client.get(
            reverse("core:coach-training-session-attendance", kwargs={"session_id": fx["session_future"].id}),
        )
        self.assertEqual(response.status_code, 401)

    def test_player_forbidden(self):
        fx = self._fixture()
        token = generate_auth_token(fx["player"])
        response = self.client.get(
            reverse("core:coach-training-session-attendance", kwargs={"session_id": fx["session_future"].id}),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 403)

    def test_parent_forbidden_even_when_linked(self):
        fx = self._fixture()
        token = generate_auth_token(fx["parent"])
        response = self.client.get(
            reverse("core:coach-training-session-attendance", kwargs={"session_id": fx["session_future"].id}),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 403)

    def test_invalid_session_returns_404(self):
        fx = self._fixture()
        token = generate_auth_token(fx["coach"])
        response = self.client.get(
            reverse("core:coach-training-session-attendance", kwargs={"session_id": 999999}),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 404)

    def test_session_with_no_confirmations_past_dates_are_absent(self):
        fx = self._fixture()
        token = generate_auth_token(fx["coach"])
        response = self.client.get(
            reverse("core:coach-training-session-attendance", kwargs={"session_id": fx["session_past"].id}),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        summary = response.json()["session"]["summary"]
        self.assertEqual(summary["present_count"], 0)
        self.assertEqual(summary["absent_count"], 2)
        self.assertEqual(summary["pending_count"], 0)

    def test_director_can_view_without_coach_membership(self):
        fx = self._fixture()
        TeamMembership.objects.filter(user=fx["coach"], team=fx["team_a"]).delete()
        token = generate_auth_token(fx["director"])
        response = self.client.get(
            reverse("core:coach-training-session-attendance", kwargs={"session_id": fx["session_future"].id}),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["session"]["summary"]["roster_size"], 2)


class RemindUnconfirmedAttendanceTests(TestCase):
    """Targeted session reminders: only unconfirmed roster; no parents for past/cancelled."""

    def setUp(self):
        director = User.objects.create_user(email="rua-dir@example.com", password="StrongPassword123!")
        self.club = Club.objects.create_club(name="RUA Club", director=director)
        self.team = Team.objects.create(club=self.club, name="RUA Team")
        self.coach = User.objects.create_user(email="rua-coach@example.com", password="StrongPassword123!")
        TeamMembership.objects.add_member(user=self.coach, team=self.team, role=TeamRole.COACH)
        self.p1 = User.objects.create_user(
            email="rua-p1@example.com",
            password="StrongPassword123!",
            date_of_birth=date(2008, 1, 1),
        )
        self.p2 = User.objects.create_user(
            email="rua-p2@example.com",
            password="StrongPassword123!",
            date_of_birth=date(2008, 2, 1),
        )
        self.parent = User.objects.create_user(
            email="rua-par@example.com",
            password="StrongPassword123!",
            assigned_account_role=AssignedAccountRole.PARENT,
        )
        TeamMembership.objects.add_member(user=self.p1, team=self.team, role=TeamRole.PLAYER)
        TeamMembership.objects.add_member(user=self.p2, team=self.team, role=TeamRole.PLAYER)
        ParentPlayerRelation.objects.link(parent=self.parent, player=self.p1)
        ParentPlayerRelation.objects.link(parent=self.parent, player=self.p2)
        today = timezone.localdate()
        future = today + timedelta(days=5)
        past = today - timedelta(days=5)
        self.session_future = TrainingSession.objects.create(
            team=self.team,
            title="Future pr",
            session_type=TrainingSession.SessionType.TRAINING,
            scheduled_date=future,
            start_time=time(18, 0),
            end_time=time(19, 0),
        )
        self.session_past = TrainingSession.objects.create(
            team=self.team,
            title="Past pr",
            session_type=TrainingSession.SessionType.TRAINING,
            scheduled_date=past,
            start_time=time(18, 0),
            end_time=time(19, 0),
        )
        self.session_cancel = TrainingSession.objects.create(
            team=self.team,
            title="Cancelled",
            session_type=TrainingSession.SessionType.TRAINING,
            scheduled_date=future,
            start_time=time(18, 0),
            end_time=time(19, 0),
            status=TrainingSession.Status.CANCELLED,
        )

    def test_players_only_unconfirmed(self):
        TrainingSessionConfirmation.objects.create(
            training_session=self.session_future,
            player=self.p1,
            confirmed_by=self.parent,
        )
        token = generate_auth_token(self.coach)
        url = reverse("core:remind-unconfirmed-training-session", kwargs={"session_id": self.session_future.id})
        response = self.client.post(
            url,
            data=json.dumps({"audience": "players"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["player_recipient_count"], 1)
        self.assertEqual(data["parent_recipient_count"], 0)
        self.assertEqual(Notification.objects.filter(recipient=self.p2).count(), 1)
        self.assertEqual(Notification.objects.filter(recipient=self.p1).count(), 0)

    def test_parents_only_future_linked_to_unconfirmed_player(self):
        TrainingSessionConfirmation.objects.create(
            training_session=self.session_future,
            player=self.p1,
            confirmed_by=self.parent,
        )
        token = generate_auth_token(self.coach)
        url = reverse("core:remind-unconfirmed-training-session", kwargs={"session_id": self.session_future.id})
        response = self.client.post(
            url,
            data=json.dumps({"audience": "parents"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["parent_recipient_count"], 1)
        self.assertEqual(Notification.objects.filter(recipient=self.parent).count(), 1)

    def test_parents_past_session_no_recipients(self):
        token = generate_auth_token(self.coach)
        url = reverse("core:remind-unconfirmed-training-session", kwargs={"session_id": self.session_past.id})
        response = self.client.post(
            url,
            data=json.dumps({"audience": "parents"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["recipient_count"], 0)

    def test_all_past_session_notifies_players_only_not_parents(self):
        token = generate_auth_token(self.coach)
        url = reverse("core:remind-unconfirmed-training-session", kwargs={"session_id": self.session_past.id})
        response = self.client.post(
            url,
            data=json.dumps({"audience": "all"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["player_recipient_count"], 2)
        self.assertEqual(response.json()["parent_recipient_count"], 0)

    def test_cancelled_session_rejected(self):
        token = generate_auth_token(self.coach)
        url = reverse("core:remind-unconfirmed-training-session", kwargs={"session_id": self.session_cancel.id})
        response = self.client.post(
            url,
            data=json.dumps({"audience": "players"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 400)

    def test_coach_attendance_includes_reminder_flags(self):
        token = generate_auth_token(self.coach)
        res_future = self.client.get(
            reverse("core:coach-training-session-attendance", kwargs={"session_id": self.session_future.id}),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(res_future.status_code, 200)
        sf = res_future.json()["session"]
        self.assertTrue(sf["remind_parents_allowed"])
        self.assertEqual(sf["unconfirmed_roster_count"], 2)
        res_past = self.client.get(
            reverse("core:coach-training-session-attendance", kwargs={"session_id": self.session_past.id}),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(res_past.status_code, 200)
        sp = res_past.json()["session"]
        self.assertFalse(sp["remind_parents_allowed"])


class CoachTeamAttendanceAnalyticsTests(TestCase):
    """EP-26: attendance rates over time for coaches / directors who can manage the team."""

    def _fixture_teams(self):
        director = User.objects.create_user(email="ep26-dir@example.com", password="StrongPassword123!")
        club = Club.objects.create_club(name="EP26 Club", director=director)
        team_a = Team.objects.create(club=club, name="EP26 Team A")
        team_b = Team.objects.create(club=club, name="EP26 Team B")
        coach = User.objects.create_user(
            email="ep26-coach@example.com",
            password="StrongPassword123!",
            assigned_account_role=AssignedAccountRole.COACH,
        )
        other_coach = User.objects.create_user(
            email="ep26-coach-b@example.com",
            password="StrongPassword123!",
            assigned_account_role=AssignedAccountRole.COACH,
        )
        player = User.objects.create_user(
            email="ep26-player@example.com",
            password="StrongPassword123!",
            assigned_account_role=AssignedAccountRole.PLAYER,
            date_of_birth=date(2007, 1, 1),
        )
        parent = User.objects.create_user(
            email="ep26-parent@example.com",
            password="StrongPassword123!",
            assigned_account_role=AssignedAccountRole.PARENT,
        )
        TeamMembership.objects.add_member(user=coach, team=team_a, role=TeamRole.COACH)
        TeamMembership.objects.add_member(user=other_coach, team=team_b, role=TeamRole.COACH)
        TeamMembership.objects.add_member(user=player, team=team_a, role=TeamRole.PLAYER)
        return {
            "director": director,
            "club": club,
            "team_a": team_a,
            "team_b": team_b,
            "coach": coach,
            "other_coach": other_coach,
            "player": player,
            "parent": parent,
        }

    def test_coach_can_view_analytics_for_own_team(self):
        fx = self._fixture_teams()
        today = timezone.localdate()
        TrainingSession.objects.create(
            team=fx["team_a"],
            title="Old",
            session_type=TrainingSession.SessionType.TRAINING,
            scheduled_date=today - timedelta(days=3),
            start_time=time(18, 0),
            end_time=time(19, 0),
        )
        token = generate_auth_token(fx["coach"])
        url = reverse("core:team-attendance-trends", kwargs={"team_id": fx["team_a"].id})
        response = self.client.get(
            url,
            {"start_date": (today - timedelta(days=30)).isoformat(), "end_date": today.isoformat()},
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["team"]["id"], fx["team_a"].id)
        self.assertIn("players", body)
        self.assertGreaterEqual(body["closed_sessions_in_scope"], 1)

    def test_other_team_coach_forbidden(self):
        fx = self._fixture_teams()
        today = timezone.localdate()
        TrainingSession.objects.create(
            team=fx["team_a"],
            title="A",
            session_type=TrainingSession.SessionType.TRAINING,
            scheduled_date=today - timedelta(days=1),
            start_time=time(18, 0),
            end_time=time(19, 0),
        )
        token = generate_auth_token(fx["other_coach"])
        url = reverse("core:team-attendance-trends", kwargs={"team_id": fx["team_a"].id})
        response = self.client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(response.status_code, 403)

    def test_unauthenticated_rejected(self):
        fx = self._fixture_teams()
        url = reverse("core:team-attendance-trends", kwargs={"team_id": fx["team_a"].id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 401)

    def test_player_forbidden(self):
        fx = self._fixture_teams()
        token = generate_auth_token(fx["player"])
        url = reverse("core:team-attendance-trends", kwargs={"team_id": fx["team_a"].id})
        response = self.client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(response.status_code, 403)

    def test_parent_forbidden(self):
        fx = self._fixture_teams()
        token = generate_auth_token(fx["parent"])
        url = reverse("core:team-attendance-trends", kwargs={"team_id": fx["team_a"].id})
        response = self.client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(response.status_code, 403)

    def test_director_can_view_without_coach_membership(self):
        fx = self._fixture_teams()
        today = timezone.localdate()
        TrainingSession.objects.create(
            team=fx["team_a"],
            title="P",
            session_type=TrainingSession.SessionType.TRAINING,
            scheduled_date=today - timedelta(days=2),
            start_time=time(18, 0),
            end_time=time(19, 0),
        )
        token = generate_auth_token(fx["director"])
        url = reverse("core:team-attendance-trends", kwargs={"team_id": fx["team_a"].id})
        response = self.client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(response.status_code, 200)

    def test_attendance_percentages_correct(self):
        fx = self._fixture_teams()
        today = timezone.localdate()
        s1 = TrainingSession.objects.create(
            team=fx["team_a"],
            title="S1",
            session_type=TrainingSession.SessionType.TRAINING,
            scheduled_date=today - timedelta(days=10),
            start_time=time(18, 0),
            end_time=time(19, 0),
        )
        s2 = TrainingSession.objects.create(
            team=fx["team_a"],
            title="S2",
            session_type=TrainingSession.SessionType.TRAINING,
            scheduled_date=today - timedelta(days=5),
            start_time=time(18, 0),
            end_time=time(19, 0),
        )
        TrainingSessionConfirmation.objects.create(
            training_session=s1,
            player=fx["player"],
            confirmed_by=fx["player"],
        )
        token = generate_auth_token(fx["coach"])
        url = reverse("core:team-attendance-trends", kwargs={"team_id": fx["team_a"].id})
        response = self.client.get(
            url,
            {
                "start_date": (today - timedelta(days=30)).isoformat(),
                "end_date": today.isoformat(),
            },
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        players = response.json()["players"]
        row = next(p for p in players if p["player_id"] == fx["player"].id)
        self.assertEqual(row["sessions_counted_for_rate"], 2)
        self.assertEqual(row["attended_sessions"], 1)
        self.assertEqual(row["absent_sessions"], 1)
        self.assertEqual(row["attendance_rate_percent"], 50.0)

    def test_empty_closed_sessions_handled(self):
        fx = self._fixture_teams()
        today = timezone.localdate()
        TrainingSession.objects.create(
            team=fx["team_a"],
            title="Future only",
            session_type=TrainingSession.SessionType.TRAINING,
            scheduled_date=today + timedelta(days=1),
            start_time=time(18, 0),
            end_time=time(19, 0),
        )
        token = generate_auth_token(fx["coach"])
        url = reverse("core:team-attendance-trends", kwargs={"team_id": fx["team_a"].id})
        response = self.client.get(
            url,
            {
                "start_date": today.isoformat(),
                "end_date": (today + timedelta(days=7)).isoformat(),
            },
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["closed_sessions_in_scope"], 0)
        row = next(p for p in body["players"] if p["player_id"] == fx["player"].id)
        self.assertIsNone(row["attendance_rate_percent"])
        self.assertEqual(row["pending_sessions"], 1)

    def test_pending_future_excluded_from_rate_denominator(self):
        fx = self._fixture_teams()
        today = timezone.localdate()
        past = TrainingSession.objects.create(
            team=fx["team_a"],
            title="Past",
            session_type=TrainingSession.SessionType.TRAINING,
            scheduled_date=today - timedelta(days=4),
            start_time=time(18, 0),
            end_time=time(19, 0),
        )
        TrainingSession.objects.create(
            team=fx["team_a"],
            title="Future",
            session_type=TrainingSession.SessionType.TRAINING,
            scheduled_date=today + timedelta(days=3),
            start_time=time(18, 0),
            end_time=time(19, 0),
        )
        TrainingSessionConfirmation.objects.create(
            training_session=past,
            player=fx["player"],
            confirmed_by=fx["player"],
        )
        token = generate_auth_token(fx["coach"])
        url = reverse("core:team-attendance-trends", kwargs={"team_id": fx["team_a"].id})
        response = self.client.get(
            url,
            {
                "start_date": (today - timedelta(days=30)).isoformat(),
                "end_date": (today + timedelta(days=30)).isoformat(),
            },
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        row = next(p for p in response.json()["players"] if p["player_id"] == fx["player"].id)
        self.assertEqual(row["sessions_counted_for_rate"], 1)
        self.assertEqual(row["attended_sessions"], 1)
        self.assertEqual(row["absent_sessions"], 0)
        self.assertEqual(row["attendance_rate_percent"], 100.0)
        self.assertEqual(row["pending_sessions"], 1)

    def test_date_range_filters_sessions(self):
        fx = self._fixture_teams()
        today = timezone.localdate()
        inside = TrainingSession.objects.create(
            team=fx["team_a"],
            title="Inside",
            session_type=TrainingSession.SessionType.TRAINING,
            scheduled_date=today - timedelta(days=5),
            start_time=time(18, 0),
            end_time=time(19, 0),
        )
        TrainingSession.objects.create(
            team=fx["team_a"],
            title="Outside",
            session_type=TrainingSession.SessionType.TRAINING,
            scheduled_date=today - timedelta(days=40),
            start_time=time(18, 0),
            end_time=time(19, 0),
        )
        TrainingSessionConfirmation.objects.create(
            training_session=inside,
            player=fx["player"],
            confirmed_by=fx["player"],
        )
        token = generate_auth_token(fx["coach"])
        url = reverse("core:team-attendance-trends", kwargs={"team_id": fx["team_a"].id})
        response = self.client.get(
            url,
            {
                "start_date": (today - timedelta(days=14)).isoformat(),
                "end_date": today.isoformat(),
            },
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["closed_sessions_in_scope"], 1)

    def test_last_n_sessions_limits_closed_set(self):
        fx = self._fixture_teams()
        today = timezone.localdate()
        for off in (20, 15, 10):
            TrainingSession.objects.create(
                team=fx["team_a"],
                title=f"T{off}",
                session_type=TrainingSession.SessionType.TRAINING,
                scheduled_date=today - timedelta(days=off),
                start_time=time(18, 0),
                end_time=time(19, 0),
            )
        token = generate_auth_token(fx["coach"])
        url = reverse("core:team-attendance-trends", kwargs={"team_id": fx["team_a"].id})
        response = self.client.get(
            url,
            {
                "start_date": (today - timedelta(days=60)).isoformat(),
                "end_date": today.isoformat(),
                "last_n_sessions": "2",
            },
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["closed_sessions_in_scope"], 2)

    def test_invalid_start_date_400(self):
        fx = self._fixture_teams()
        token = generate_auth_token(fx["coach"])
        url = reverse("core:team-attendance-trends", kwargs={"team_id": fx["team_a"].id})
        response = self.client.get(url, {"start_date": "not-a-date"}, HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(response.status_code, 400)


class AttendanceSummaryEndpointTests(TestCase):
    """EP-27: compact team summary and per-player summary APIs."""

    def _base(self):
        director = User.objects.create_user(email="ep27-dir@example.com", password="StrongPassword123!")
        club = Club.objects.create_club(name="EP27 Club", director=director)
        team = Team.objects.create(club=club, name="EP27 Team")
        coach = User.objects.create_user(
            email="ep27-coach@example.com",
            password="StrongPassword123!",
            assigned_account_role=AssignedAccountRole.COACH,
        )
        player = User.objects.create_user(
            email="ep27-player@example.com",
            password="StrongPassword123!",
            assigned_account_role=AssignedAccountRole.PLAYER,
            date_of_birth=date(2006, 1, 1),
        )
        other_player = User.objects.create_user(
            email="ep27-other@example.com",
            password="StrongPassword123!",
            assigned_account_role=AssignedAccountRole.PLAYER,
            date_of_birth=date(2006, 1, 1),
        )
        parent = User.objects.create_user(
            email="ep27-par@example.com",
            password="StrongPassword123!",
            assigned_account_role=AssignedAccountRole.PARENT,
        )
        TeamMembership.objects.add_member(user=coach, team=team, role=TeamRole.COACH)
        TeamMembership.objects.add_member(user=player, team=team, role=TeamRole.PLAYER)
        TeamMembership.objects.add_member(user=other_player, team=team, role=TeamRole.PLAYER)
        ParentPlayerRelation.objects.link(parent=parent, player=player, approval_status=ParentLinkApprovalStatus.APPROVED)
        return director, club, team, coach, player, other_player, parent

    def test_team_summary_requires_manage_role(self):
        _, _, team, _, player, _, _ = self._base()
        today = timezone.localdate()
        TrainingSession.objects.create(
            team=team,
            title="P",
            session_type=TrainingSession.SessionType.TRAINING,
            scheduled_date=today - timedelta(days=1),
            start_time=time(18, 0),
            end_time=time(19, 0),
        )
        token = generate_auth_token(player)
        url = reverse("core:team-attendance-summary", kwargs={"team_id": team.id})
        response = self.client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(response.status_code, 403)

    def test_team_summary_coach_sees_roll_up(self):
        _, _, team, coach, player, _, _ = self._base()
        today = timezone.localdate()
        s = TrainingSession.objects.create(
            team=team,
            title="P",
            session_type=TrainingSession.SessionType.TRAINING,
            scheduled_date=today - timedelta(days=2),
            start_time=time(18, 0),
            end_time=time(19, 0),
        )
        TrainingSessionConfirmation.objects.create(training_session=s, player=player, confirmed_by=coach)
        token = generate_auth_token(coach)
        url = reverse("core:team-attendance-summary", kwargs={"team_id": team.id})
        response = self.client.get(
            url,
            {
                "start_date": (today - timedelta(days=14)).isoformat(),
                "end_date": today.isoformat(),
            },
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["closed_roster_slots_total"], 2)
        self.assertEqual(body["closed_roster_slots_present"], 1)
        self.assertEqual(body["closed_roster_slots_absent"], 1)

    def test_player_summary_self(self):
        _, _, team, _, player, _, _ = self._base()
        today = timezone.localdate()
        s = TrainingSession.objects.create(
            team=team,
            title="P",
            session_type=TrainingSession.SessionType.TRAINING,
            scheduled_date=today - timedelta(days=1),
            start_time=time(18, 0),
            end_time=time(19, 0),
        )
        TrainingSessionConfirmation.objects.create(training_session=s, player=player, confirmed_by=player)
        token = generate_auth_token(player)
        url = reverse("core:player-team-attendance-summary", kwargs={"team_id": team.id, "player_id": player.id})
        response = self.client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["player"]["attendance_rate_percent"], 100.0)

    def test_player_summary_parent_of_player(self):
        _, _, team, _, player, _, parent = self._base()
        today = timezone.localdate()
        s = TrainingSession.objects.create(
            team=team,
            title="P",
            session_type=TrainingSession.SessionType.TRAINING,
            scheduled_date=today - timedelta(days=1),
            start_time=time(18, 0),
            end_time=time(19, 0),
        )
        TrainingSessionConfirmation.objects.create(training_session=s, player=player, confirmed_by=parent)
        token = generate_auth_token(parent)
        url = reverse("core:player-team-attendance-summary", kwargs={"team_id": team.id, "player_id": player.id})
        response = self.client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["player"]["attendance_rate_percent"], 100.0)

    def test_player_summary_wrong_player_forbidden(self):
        _, _, team, _, player, other_player, _ = self._base()
        token = generate_auth_token(other_player)
        url = reverse("core:player-team-attendance-summary", kwargs={"team_id": team.id, "player_id": player.id})
        response = self.client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(response.status_code, 403)

    def test_player_not_on_roster_404(self):
        _, _, team, coach, _, _, _ = self._base()
        stranger = User.objects.create_user(
            email="ep27-stranger@example.com",
            password="StrongPassword123!",
            assigned_account_role=AssignedAccountRole.PLAYER,
        )
        token = generate_auth_token(coach)
        url = reverse("core:player-team-attendance-summary", kwargs={"team_id": team.id, "player_id": stranger.id})
        response = self.client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(response.status_code, 404)

    def test_analytics_and_compact_summary_share_team_average(self):
        _, _, team, coach, player, _other, _ = self._base()
        today = timezone.localdate()
        s = TrainingSession.objects.create(
            team=team,
            title="P",
            session_type=TrainingSession.SessionType.TRAINING,
            scheduled_date=today - timedelta(days=2),
            start_time=time(18, 0),
            end_time=time(19, 0),
        )
        TrainingSessionConfirmation.objects.create(training_session=s, player=player, confirmed_by=coach)
        token = generate_auth_token(coach)
        turl = reverse("core:team-attendance-trends", kwargs={"team_id": team.id})
        surl = reverse("core:team-attendance-summary", kwargs={"team_id": team.id})
        q = {
            "start_date": (today - timedelta(days=14)).isoformat(),
            "end_date": today.isoformat(),
        }
        a = self.client.get(turl, q, HTTP_AUTHORIZATION=f"Bearer {token}").json()
        c = self.client.get(surl, q, HTTP_AUTHORIZATION=f"Bearer {token}").json()
        self.assertEqual(
            a["team_average_attendance_rate_percent"],
            c["team_average_attendance_rate_percent"],
        )

    def test_cancelled_sessions_excluded_from_closed_slot_totals(self):
        from apps.core.attendance_summary import prepare_team_attendance_scope, team_closed_player_slot_totals

        _, _, team, _, _player, _other, _ = self._base()
        today = timezone.localdate()
        TrainingSession.objects.create(
            team=team,
            title="C",
            session_type=TrainingSession.SessionType.TRAINING,
            scheduled_date=today - timedelta(days=1),
            start_time=time(18, 0),
            end_time=time(19, 0),
            status=TrainingSession.Status.CANCELLED,
        )
        scope = prepare_team_attendance_scope(
            team,
            start_date=today - timedelta(days=7),
            end_date=today,
            last_n_sessions=None,
        )
        attended, closed = team_closed_player_slot_totals(scope)
        self.assertEqual(closed, 0)
        self.assertEqual(attended, 0)


class AttendanceIncompleteReminderTests(TestCase):
    """EP-28: coach notifications when roster confirmations are incomplete after a session ends."""

    def _fixture(self, *, include_other_team_coach=False):
        director = User.objects.create_user(email="ep28-dir@example.com", password="StrongPassword123!")
        club = Club.objects.create_club(name="EP28 Club", director=director)
        team = Team.objects.create(club=club, name="EP28 Team")
        coach = User.objects.create_user(
            email="ep28-coach@example.com",
            password="StrongPassword123!",
            assigned_account_role=AssignedAccountRole.COACH,
        )
        player_a = User.objects.create_user(
            email="ep28-pa@example.com",
            password="StrongPassword123!",
            assigned_account_role=AssignedAccountRole.PLAYER,
            date_of_birth=date(2008, 1, 1),
        )
        player_b = User.objects.create_user(
            email="ep28-pb@example.com",
            password="StrongPassword123!",
            assigned_account_role=AssignedAccountRole.PLAYER,
            date_of_birth=date(2009, 2, 1),
        )
        TeamMembership.objects.add_member(user=coach, team=team, role=TeamRole.COACH)
        TeamMembership.objects.add_member(user=player_a, team=team, role=TeamRole.PLAYER)
        TeamMembership.objects.add_member(user=player_b, team=team, role=TeamRole.PLAYER)
        other_coach = None
        if include_other_team_coach:
            team_b = Team.objects.create(club=club, name="EP28 Other")
            other_coach = User.objects.create_user(
                email="ep28-othercoach@example.com",
                password="StrongPassword123!",
                assigned_account_role=AssignedAccountRole.COACH,
            )
            TeamMembership.objects.add_member(user=other_coach, team=team_b, role=TeamRole.COACH)

        today = timezone.localdate()
        past = today - timedelta(days=5)
        session_incomplete = TrainingSession.objects.create(
            team=team,
            title="Past incomplete",
            session_type=TrainingSession.SessionType.TRAINING,
            scheduled_date=past,
            start_time=time(17, 0),
            end_time=time(18, 0),
        )
        session_complete = TrainingSession.objects.create(
            team=team,
            title="Past complete",
            session_type=TrainingSession.SessionType.TRAINING,
            scheduled_date=past - timedelta(days=1),
            start_time=time(17, 0),
            end_time=time(18, 0),
        )
        TrainingSessionConfirmation.objects.create(
            training_session=session_complete,
            player=player_a,
            confirmed_by=coach,
        )
        TrainingSessionConfirmation.objects.create(
            training_session=session_complete,
            player=player_b,
            confirmed_by=coach,
        )
        TrainingSessionConfirmation.objects.create(
            training_session=session_incomplete,
            player=player_a,
            confirmed_by=coach,
        )

        future = today + timedelta(days=3)
        session_future = TrainingSession.objects.create(
            team=team,
            title="Future",
            session_type=TrainingSession.SessionType.TRAINING,
            scheduled_date=future,
            start_time=time(17, 0),
            end_time=time(18, 0),
        )

        cancelled = TrainingSession.objects.create(
            team=team,
            title="Cancelled past",
            session_type=TrainingSession.SessionType.TRAINING,
            scheduled_date=past - timedelta(days=3),
            start_time=time(17, 0),
            end_time=time(18, 0),
            status=TrainingSession.Status.CANCELLED,
        )

        return {
            "director": director,
            "club": club,
            "team": team,
            "coach": coach,
            "player_a": player_a,
            "player_b": player_b,
            "session_incomplete": session_incomplete,
            "session_complete": session_complete,
            "session_future": session_future,
            "session_cancelled": cancelled,
            "other_coach": other_coach,
        }

    def test_incomplete_past_session_creates_reminder_for_coach(self):
        fx = self._fixture()
        n = sweep_incomplete_attendance_reminders()
        self.assertGreaterEqual(n, 1)
        notif = Notification.objects.get(
            recipient=fx["coach"],
            category=Notification.Category.ATTENDANCE_INCOMPLETE,
            training_session=fx["session_incomplete"],
        )
        self.assertFalse(notif.is_read)
        self.assertIn("1 roster player", notif.message.lower())

    def test_complete_past_session_no_reminder(self):
        fx = self._fixture()
        sweep_incomplete_attendance_reminders()
        self.assertFalse(
            Notification.objects.filter(training_session=fx["session_complete"]).exists()
        )

    def test_future_session_no_reminder(self):
        fx = self._fixture()
        sweep_incomplete_attendance_reminders()
        self.assertFalse(
            Notification.objects.filter(training_session=fx["session_future"]).exists()
        )

    def test_duplicate_sweep_does_not_duplicate_rows(self):
        fx = self._fixture()
        sweep_incomplete_attendance_reminders()
        sweep_incomplete_attendance_reminders()
        c = Notification.objects.filter(
            recipient=fx["coach"],
            category=Notification.Category.ATTENDANCE_INCOMPLETE,
            training_session=fx["session_incomplete"],
        ).count()
        self.assertEqual(c, 1)

    def test_reminder_cleared_when_attendance_completes(self):
        fx = self._fixture()
        sweep_incomplete_attendance_reminders()
        self.assertTrue(
            Notification.objects.filter(training_session=fx["session_incomplete"]).exists()
        )
        TrainingSessionConfirmation.objects.create(
            training_session=fx["session_incomplete"],
            player=fx["player_b"],
            confirmed_by=fx["coach"],
        )
        sync_incomplete_attendance_notifications_for_session_id(fx["session_incomplete"].id)
        self.assertFalse(
            Notification.objects.filter(training_session=fx["session_incomplete"]).exists()
        )

    def test_cancelled_session_no_reminder(self):
        fx = self._fixture()
        sweep_incomplete_attendance_reminders()
        self.assertFalse(
            Notification.objects.filter(training_session=fx["session_cancelled"]).exists()
        )

    def test_other_team_coach_does_not_receive_reminder(self):
        fx = self._fixture(include_other_team_coach=True)
        self.assertIsNotNone(fx["other_coach"])
        sweep_incomplete_attendance_reminders()
        self.assertFalse(
            Notification.objects.filter(recipient=fx["other_coach"]).exists()
        )

    def test_notification_list_includes_coach_attendance_path(self):
        fx = self._fixture()
        sweep_incomplete_attendance_reminders()
        token = generate_auth_token(fx["coach"])
        response = self.client.get(
            reverse("core:notifications"),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        items = response.json()["items"]
        match = [i for i in items if i.get("training_session_id") == fx["session_incomplete"].id]
        self.assertEqual(len(match), 1)
        self.assertEqual(
            match[0]["coach_attendance_path"],
            f"/coach/attendance?team={fx['team'].id}&session={fx['session_incomplete'].id}",
        )

    def test_player_does_not_see_coach_reminder(self):
        fx = self._fixture()
        sweep_incomplete_attendance_reminders()
        token = generate_auth_token(fx["player_a"])
        response = self.client.get(
            reverse("core:notifications"),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        ids = [i.get("training_session_id") for i in response.json()["items"]]
        self.assertNotIn(fx["session_incomplete"].id, ids)


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


class MemberHubDashboardTests(TestCase):
    """GET /api/me/member-dashboard/ aggregated parent/player home payload."""

    def _fixture(self):
        director = User.objects.create_user(email="md-dir@example.com", password="StrongPassword123!")
        club = Club.objects.create_club(name="MD Club", director=director)
        team = Team.objects.create(club=club, name="MD Team")
        coach = User.objects.create_user(
            email="md-coach@example.com",
            password="StrongPassword123!",
            first_name="Casey",
            last_name="Coach",
        )
        TeamMembership.objects.add_member(user=coach, team=team, role=TeamRole.COACH)
        player = User.objects.create_user(
            email="md-player@example.com",
            password="StrongPassword123!",
            first_name="Max",
            last_name="Demo",
            date_of_birth=date(2010, 3, 10),
        )
        TeamMembership.objects.add_member(user=player, team=team, role=TeamRole.PLAYER)
        parent = User.objects.create_user(
            email="md-parent@example.com",
            password="StrongPassword123!",
            first_name="Pat",
            last_name="Demo",
        )
        ParentPlayerRelation.objects.link(parent=parent, player=player, approval_status=ParentLinkApprovalStatus.APPROVED)
        other_child = User.objects.create_user(
            email="md-otherchild@example.com",
            password="StrongPassword123!",
            first_name="Other",
            last_name="Kid",
        )
        TeamMembership.objects.add_member(user=other_child, team=team, role=TeamRole.PLAYER)
        ParentPlayerRelation.objects.link(parent=parent, player=other_child, approval_status=ParentLinkApprovalStatus.APPROVED)

        today = timezone.localdate()
        session = TrainingSession.objects.create(
            team=team,
            title="Next practice",
            session_type=TrainingSession.SessionType.TRAINING,
            scheduled_date=today + timedelta(days=2),
            start_time=time(18, 0),
            end_time=time(19, 30),
            location="Gym A",
        )
        PlayerFeeRecord.objects.create(
            club=club,
            player=player,
            team=team,
            description="Dues",
            amount_due=Decimal("100.00"),
            amount_paid=Decimal("40.00"),
            currency="USD",
            due_date=today + timedelta(days=7),
            billing_period_start=today.replace(day=1),
        )
        mon = today - timedelta(days=today.weekday())
        PlayerWeeklySkillMetric.objects.create(
            player=player,
            team=team,
            week_start=mon - timedelta(weeks=1),
            attack=Decimal("60.00"),
            defense=Decimal("65.00"),
            serve=Decimal("70.00"),
        )
        PlayerWeeklySkillMetric.objects.create(
            player=player,
            team=team,
            week_start=mon,
            attack=Decimal("62.00"),
            defense=Decimal("66.00"),
            serve=Decimal("72.00"),
        )
        return {
            "player": player,
            "parent": parent,
            "other_child": other_child,
            "team": team,
            "coach": coach,
            "session": session,
        }

    def test_requires_authentication(self):
        response = self.client.get(reverse("core:member-hub-dashboard"))
        self.assertEqual(response.status_code, 401)

    def test_player_sees_own_data(self):
        fx = self._fixture()
        token = generate_auth_token(fx["player"])
        response = self.client.get(reverse("core:member-hub-dashboard"), HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["focus_player"]["id"], fx["player"].id)
        self.assertEqual(data["profile"]["display_name"], "Max Demo")
        self.assertEqual(data["profile"]["team"]["name"], "MD Team")
        self.assertIn("Casey Coach", data["profile"]["coach_display"])
        self.assertAlmostEqual(data["payment"]["amount_due"], 60.0)
        self.assertEqual(data["payment"]["overall_status"], "pending")
        self.assertEqual(data["club_summary"]["session_id"], fx["session"].id)
        self.assertTrue(data["progress"]["has_weekly_metrics"])
        self.assertEqual(len(data["progress"]["weeks"]), 2)
        self.assertAlmostEqual(data["progress"]["summary"]["serve"], 72.0)
        self.assertTrue(data["parent_access"]["can_manage"])
        self.assertTrue(data["parent_access"]["minor_locked"])
        self.assertEqual(len(data["parent_access"]["linked_parents"]), 1)

    def test_parent_sees_linked_child_default_first_id(self):
        fx = self._fixture()
        token = generate_auth_token(fx["parent"])
        response = self.client.get(reverse("core:member-hub-dashboard"), HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["available_children"]), 2)
        self.assertEqual(data["focus_player"]["id"], min(fx["player"].id, fx["other_child"].id))

    def test_parent_for_player_id_second_child(self):
        fx = self._fixture()
        token = generate_auth_token(fx["parent"])
        url = reverse("core:member-hub-dashboard") + f"?for_player_id={fx['other_child'].id}"
        response = self.client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["focus_player"]["id"], fx["other_child"].id)

    def test_parent_cannot_view_unrelated_player(self):
        fx = self._fixture()
        stranger = User.objects.create_user(email="md-stranger@example.com", password="StrongPassword123!")
        token = generate_auth_token(fx["parent"])
        url = reverse("core:member-hub-dashboard") + f"?for_player_id={stranger.id}"
        response = self.client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(response.status_code, 403)

    def test_non_player_for_self_id_returns_400(self):
        fx = self._fixture()
        token = generate_auth_token(fx["parent"])
        url = reverse("core:member-hub-dashboard") + f"?for_player_id={fx['parent'].id}"
        response = self.client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(response.status_code, 400)

    def test_member_without_roster_or_family_has_empty_focus(self):
        lone = User.objects.create_user(email="md-lone@example.com", password="StrongPassword123!")
        token = generate_auth_token(lone)
        response = self.client.get(reverse("core:member-hub-dashboard"), HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["focus_player"])

    def test_progress_empty_when_no_weekly_rows(self):
        director = User.objects.create_user(email="md-p2@example.com", password="StrongPassword123!")
        club = Club.objects.create_club(name="MD Club 2", director=director)
        team = Team.objects.create(club=club, name="MD Team 2")
        player = User.objects.create_user(email="md-player2@example.com", password="StrongPassword123!")
        TeamMembership.objects.add_member(user=player, team=team, role=TeamRole.PLAYER)
        token = generate_auth_token(player)
        response = self.client.get(reverse("core:member-hub-dashboard"), HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["progress"]["has_weekly_metrics"])
        self.assertEqual(body["progress"]["weeks"], [])


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    EMAIL_HOST_USER="sender@example.com",
    EMAIL_HOST_PASSWORD="secret",
    CONTACT_NOTIFICATION_EMAIL="staff-notify@example.com",
)
class ContactSubmitApiTests(TestCase):
    def test_contact_submit_creates_row_and_returns_201(self):
        self.assertEqual(ContactSubmission.objects.count(), 0)
        response = self.client.post(
            reverse("core:contact-submit"),
            data=json.dumps(
                {
                    "name": "Sam Volley",
                    "email": "sam@example.com",
                    "role": "coach",
                    "message": "We need a demo next week.",
                    "phone": "+1 555 0100",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertIn("id", body)
        self.assertIn("message", body)
        self.assertEqual(ContactSubmission.objects.count(), 1)
        row = ContactSubmission.objects.get()
        self.assertEqual(row.name, "Sam Volley")
        self.assertEqual(row.email, "sam@example.com")
        self.assertEqual(row.role, ContactSubmission.ContactRole.COACH)
        self.assertEqual(row.message, "We need a demo next week.")
        self.assertEqual(row.phone, "+1 555 0100")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["staff-notify@example.com"])
        self.assertIn("Sam Volley", mail.outbox[0].subject)
        self.assertIn("We need a demo next week.", mail.outbox[0].body)
        self.assertIn("sam@example.com", mail.outbox[0].body)

    def test_contact_submit_optional_phone_blank(self):
        response = self.client.post(
            reverse("core:contact-submit"),
            data=json.dumps(
                {
                    "name": "Pat",
                    "email": "pat@example.com",
                    "role": "parent",
                    "message": "Hello",
                    "phone": "",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(ContactSubmission.objects.get().phone, "")
        self.assertEqual(len(mail.outbox), 1)

    def test_contact_submit_validation_errors(self):
        response = self.client.post(
            reverse("core:contact-submit"),
            data=json.dumps(
                {
                    "name": "",
                    "email": "not-an-email",
                    "role": "invalid-role",
                    "message": "",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        errors = response.json().get("errors", {})
        self.assertIn("name", errors)
        self.assertIn("email", errors)
        self.assertIn("role", errors)
        self.assertIn("message", errors)
        self.assertEqual(ContactSubmission.objects.count(), 0)

    def test_contact_submit_rejects_invalid_json(self):
        response = self.client.post(
            reverse("core:contact-submit"),
            data="{",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_contact_submit_rejects_phone_too_long(self):
        response = self.client.post(
            reverse("core:contact-submit"),
            data=json.dumps(
                {
                    "name": "Pat",
                    "email": "pat@example.com",
                    "role": "player",
                    "message": "Hi",
                    "phone": "x" * 41,
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("phone", response.json().get("errors", {}))
        self.assertEqual(ContactSubmission.objects.count(), 0)
