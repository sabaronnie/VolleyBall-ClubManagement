from datetime import date
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
    PlayerAccessPolicy,
    PlayerProfile,
    Team,
    TeamMembership,
    TeamRole,
    User,
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
