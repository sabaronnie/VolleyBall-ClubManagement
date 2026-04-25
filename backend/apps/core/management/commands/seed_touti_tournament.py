from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.core.models import (
    Club,
    ClubMembership,
    ParentLinkApprovalStatus,
    ParentPlayerRelation,
    Pool,
    Standing,
    Team,
    TeamMembership,
    TeamRole,
    Tournament,
    TournamentMatch,
    TournamentTeam,
    VerificationStatus,
)
from apps.core.tournament_views import _recalculate_pool_standings

User = get_user_model()


class Command(BaseCommand):
    help = "Seed an ongoing canonical tournament for touti with 4 teams."

    PASSWORD = "password123"
    DIRECTOR_EMAIL = "touti@test.com"
    PLAYER_EMAIL = "kuki@test.com"
    PARENT_EMAIL = "koukou@test.com"
    EXTRA_PLAYER_EMAIL = "kouki@test.com"

    CLUB_NAME = "Touti Volleyball Club"
    TOURNAMENT_NAME = "Touti Ongoing Cup"
    TEAM_NAMES = ["touti1", "touti2", "touti3", "touti4"]

    def handle(self, *args, **options):
        with transaction.atomic():
            users = self._seed_users()
            club = self._seed_club(users["director"])
            teams = self._seed_teams(club)
            self._seed_memberships(users, teams, club)
            tournament, pool = self._seed_tournament(users["director"], club, teams)
            self._seed_pool_matches(tournament, pool, teams)
            _recalculate_pool_standings(tournament, pool)
            self._validate_seed(tournament, pool, users["player"])

        self.stdout.write(self.style.SUCCESS("Seed completed successfully."))
        self.stdout.write(f"Director: {self.DIRECTOR_EMAIL} / {self.PASSWORD}")
        self.stdout.write(f"Player:   {self.PLAYER_EMAIL} / {self.PASSWORD}")
        self.stdout.write(f"Parent:   {self.PARENT_EMAIL} / {self.PASSWORD}")
        self.stdout.write(f"Extra:    {self.EXTRA_PLAYER_EMAIL} / {self.PASSWORD}")
        self.stdout.write(f"Club: {self.CLUB_NAME}")
        self.stdout.write(f"Tournament: {self.TOURNAMENT_NAME} (POOL_STAGE)")
        self.stdout.write("Teams: touti1, touti2, touti3, touti4")
        self.stdout.write("Matches: 6 pool matches (1 completed, 5 scheduled)")

    def _seed_users(self):
        rows = {
            "director": (self.DIRECTOR_EMAIL, "touti", "Director", date(1991, 1, 1)),
            "player": (self.PLAYER_EMAIL, "kuki", "Player", date(2010, 5, 10)),
            "parent": (self.PARENT_EMAIL, "koukou", "Parent", date(1987, 8, 20)),
            "extra": (self.EXTRA_PLAYER_EMAIL, "kouki", "Player", date(2011, 3, 15)),
        }
        users = {}
        for key, (email, first_name, last_name, dob) in rows.items():
            user, _ = User.objects.get_or_create(
                email=email,
                defaults={
                    "first_name": first_name,
                    "last_name": last_name,
                    "date_of_birth": dob,
                    "verification_status": VerificationStatus.VERIFIED,
                },
            )
            user.first_name = first_name
            user.last_name = last_name
            user.date_of_birth = dob
            user.verification_status = VerificationStatus.VERIFIED
            user.set_password(self.PASSWORD)
            user.save(
                update_fields=[
                    "first_name",
                    "last_name",
                    "date_of_birth",
                    "verification_status",
                    "password",
                ]
            )
            users[key] = user
        return users

    def _seed_club(self, director):
        club, _ = Club.objects.get_or_create(
            name=self.CLUB_NAME,
            defaults={
                "short_name": "TOUTI",
                "description": "Seeded ongoing tournament club.",
                "city": "Beirut",
                "country": "Lebanon",
            },
        )
        club.short_name = "TOUTI"
        club.description = "Seeded ongoing tournament club."
        club.city = "Beirut"
        club.country = "Lebanon"
        club.save(update_fields=["short_name", "description", "city", "country"])
        ClubMembership.objects.assign_director(user=director, club=club)
        return club

    def _seed_teams(self, club):
        teams = {}
        for team_name in self.TEAM_NAMES:
            team, _ = Team.objects.get_or_create(
                club=club,
                name=team_name,
                defaults={
                    "short_name": team_name.upper(),
                    "season": "2026",
                    "age_group": "U18",
                    "gender": Team.Gender.MIXED,
                    "status": Team.Status.ACTIVE,
                    "home_venue": "Main Sports Hall",
                    "notes": "Seeded team for touti tournament.",
                },
            )
            team.season = "2026"
            team.age_group = "U18"
            team.gender = Team.Gender.MIXED
            team.status = Team.Status.ACTIVE
            team.home_venue = "Main Sports Hall"
            team.notes = "Seeded team for touti tournament."
            team.save(update_fields=["season", "age_group", "gender", "status", "home_venue", "notes"])
            teams[team_name] = team
        return teams

    def _seed_memberships(self, users, teams, club):
        ClubMembership.objects.assign_director(user=users["director"], club=club)
        TeamMembership.objects.add_member(user=users["player"], team=teams["touti1"], role=TeamRole.PLAYER)
        TeamMembership.objects.add_member(user=users["extra"], team=teams["touti2"], role=TeamRole.PLAYER)

        ParentPlayerRelation.objects.link(
            parent=users["parent"],
            player=users["player"],
            is_legal_guardian=True,
            approval_status=ParentLinkApprovalStatus.APPROVED,
        )

    def _seed_tournament(self, director, club, teams):
        Tournament.objects.filter(club=club, name=self.TOURNAMENT_NAME).delete()
        start_date = timezone.localdate() - timedelta(days=14)
        tournament = Tournament.objects.create(
            club=club,
            created_by=director,
            name=self.TOURNAMENT_NAME,
            tournament_type=Tournament.TournamentType.POOL_AND_BRACKET,
            number_of_teams=4,
            pool_count=1,
            teams_per_pool=4,
            teams_qualifying_per_pool=2,
            match_duration_minutes=90,
            scoring_format="wins, head-to-head, point_difference, points_for, random",
            start_date=start_date,
            venue="Main Sports Hall",
            status=Tournament.Status.POOL_STAGE,
        )
        tournament.teams.set([teams[name] for name in self.TEAM_NAMES])

        pool = Pool.objects.create(tournament=tournament, name="Pool A")
        for seed, team_name in enumerate(self.TEAM_NAMES, start=1):
            TournamentTeam.objects.create(
                tournament=tournament,
                team=teams[team_name],
                seed=seed,
                pool=pool,
            )
            Standing.objects.get_or_create(tournament=tournament, pool=pool, team=teams[team_name])
        return tournament, pool

    def _seed_pool_matches(self, tournament, pool, teams):
        schedule = [
            ("touti1", "touti2", 2, 1),
            ("touti1", "touti3", None, None),
            ("touti1", "touti4", None, None),
            ("touti2", "touti3", None, None),
            ("touti2", "touti4", None, None),
            ("touti3", "touti4", None, None),
        ]
        now = timezone.now()
        for idx, (team_a_name, team_b_name, score_a, score_b) in enumerate(schedule, start=1):
            team_a = teams[team_a_name]
            team_b = teams[team_b_name]
            winner = None
            loser = None
            status = TournamentMatch.MatchStatus.SCHEDULED
            if score_a is not None and score_b is not None:
                status = TournamentMatch.MatchStatus.COMPLETED
                winner = team_a if score_a > score_b else team_b
                loser = team_b if winner == team_a else team_a

            TournamentMatch.objects.update_or_create(
                tournament=tournament,
                pool=pool,
                match_number=idx,
                defaults={
                    "team_a": team_a,
                    "team_b": team_b,
                    "team_a_score": score_a,
                    "team_b_score": score_b,
                    "winner_team": winner,
                    "loser_team": loser,
                    "scheduled_time": now + timedelta(days=idx),
                    "location": f"Court {(idx % 2) + 1}",
                    "status": status,
                },
            )

    def _validate_seed(self, tournament, pool, player):
        matches = list(TournamentMatch.objects.filter(tournament=tournament, pool=pool).order_by("match_number"))
        if len(matches) != 6:
            raise CommandError(f"Expected 6 pool matches, got {len(matches)}.")

        completed_count = sum(1 for m in matches if m.status == TournamentMatch.MatchStatus.COMPLETED)
        if completed_count != 1:
            raise CommandError(f"Expected 1 completed match, got {completed_count}.")

        signatures = set()
        for match in matches:
            if match.team_a_id == match.team_b_id:
                raise CommandError("Invalid seed: team plays itself.")
            sig = tuple(sorted((match.team_a_id, match.team_b_id)))
            if sig in signatures:
                raise CommandError("Invalid seed: duplicate matchup.")
            signatures.add(sig)

        player_team_ids = set(TeamMembership.objects.filter(user=player, role=TeamRole.PLAYER).values_list("team_id", flat=True))
        visible_count = TournamentMatch.objects.filter(tournament=tournament).filter(
            team_a_id__in=player_team_ids
        ).union(
            TournamentMatch.objects.filter(tournament=tournament).filter(team_b_id__in=player_team_ids)
        ).count()
        if visible_count < 1:
            raise CommandError("Player should have at least one visible tournament match.")
