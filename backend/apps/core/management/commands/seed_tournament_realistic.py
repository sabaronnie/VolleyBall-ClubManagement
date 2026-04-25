from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.core.models import (
    Club,
    ClubMembership,
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

User = get_user_model()
SEED_PASSWORD = "test123"


class Command(BaseCommand):
    help = "Seed realistic tournament data for Spring Cup 2026 flow and RBAC checks."

    def handle(self, *args, **options):
        with transaction.atomic():
            director = self._upsert_user("director.seed@local.test", "Lana", "Director", date(1988, 1, 1))
            coach_a = self._upsert_user("coach.a@local.test", "Rami", "Coach", date(1991, 2, 2))
            coach_b = self._upsert_user("coach.b@local.test", "Maya", "Coach", date(1992, 3, 3))
            parent_a = self._upsert_user("parent.a@local.test", "Nora", "Parent", date(1986, 4, 4))
            parent_b = self._upsert_user("parent.b@local.test", "Omar", "Parent", date(1985, 5, 5))

            club, _ = Club.objects.get_or_create(name="Spring Club QA", defaults={"short_name": "SCQ", "city": "Beirut"})
            ClubMembership.objects.assign_director(user=director, club=club)

            team_names = [
                "Falcon Spikers",
                "Titan Smashers",
                "Eagle Aces",
                "Viper Spikes",
                "Tiger Blockers",
                "Panther Setters",
                "Wolf Diggers",
                "Hawk Servers",
            ]
            teams = {}
            for idx, name in enumerate(team_names):
                team, _ = Team.objects.get_or_create(club=club, name=name)
                team.status = Team.Status.ACTIVE
                team.season = "2025-26"
                team.home_venue = f"Court {idx + 1}"
                team.save(update_fields=["status", "season", "home_venue"])
                teams[name] = team

            for idx in range(16):
                player = self._upsert_user(
                    f"player{idx + 1}@local.test",
                    f"Player{idx + 1}",
                    "Seed",
                    date(2009, (idx % 12) + 1, (idx % 27) + 1),
                )
                team = teams[team_names[idx % len(team_names)]]
                TeamMembership.objects.add_member(user=player, team=team, role=TeamRole.PLAYER)
                if idx in {0, 1}:
                    ParentPlayerRelation.objects.link(parent=parent_a, player=player, is_legal_guardian=True)
                if idx in {2, 3}:
                    ParentPlayerRelation.objects.link(parent=parent_b, player=player, is_legal_guardian=True)

            TeamMembership.objects.add_member(user=coach_a, team=teams["Falcon Spikers"], role=TeamRole.COACH)
            TeamMembership.objects.add_member(user=coach_a, team=teams["Titan Smashers"], role=TeamRole.COACH)
            TeamMembership.objects.add_member(user=coach_b, team=teams["Tiger Blockers"], role=TeamRole.COACH)
            TeamMembership.objects.add_member(user=coach_b, team=teams["Panther Setters"], role=TeamRole.COACH)

            TournamentMatch.objects.filter(tournament__name="Spring Cup 2026", tournament__club=club).delete()
            Standing.objects.filter(tournament__name="Spring Cup 2026", tournament__club=club).delete()
            TournamentTeam.objects.filter(tournament__name="Spring Cup 2026", tournament__club=club).delete()
            Pool.objects.filter(tournament__name="Spring Cup 2026", tournament__club=club).delete()
            Tournament.objects.filter(name="Spring Cup 2026", club=club).delete()

            tournament = Tournament.objects.create(
                club=club,
                created_by=director,
                name="Spring Cup 2026",
                venue="Spring Arena",
                start_date=timezone.localdate() - timedelta(days=2),
                tournament_type=Tournament.TournamentType.POOL_AND_BRACKET,
                status=Tournament.Status.POOL_STAGE,
                number_of_teams=8,
                pool_count=2,
                teams_per_pool=4,
                teams_qualifying_per_pool=2,
                scoring_format="wins, head-to-head, point_difference, points_for, random",
            )
            tournament.teams.set(list(teams.values()))

            pool_a = Pool.objects.create(tournament=tournament, name="Pool A")
            pool_b = Pool.objects.create(tournament=tournament, name="Pool B")
            pool_a_names = ["Falcon Spikers", "Titan Smashers", "Eagle Aces", "Viper Spikes"]
            pool_b_names = ["Tiger Blockers", "Panther Setters", "Wolf Diggers", "Hawk Servers"]
            all_seeded = pool_a_names + pool_b_names
            for seed, name in enumerate(all_seeded, start=1):
                TournamentTeam.objects.create(
                    tournament=tournament,
                    team=teams[name],
                    seed=seed,
                    pool=pool_a if name in pool_a_names else pool_b,
                )
            for name in pool_a_names:
                Standing.objects.get_or_create(tournament=tournament, pool=pool_a, team=teams[name])
            for name in pool_b_names:
                Standing.objects.get_or_create(tournament=tournament, pool=pool_b, team=teams[name])

            def add_match(pool, number, a, b, score_a=None, score_b=None):
                status = TournamentMatch.MatchStatus.SCHEDULED
                winner = None
                loser = None
                if score_a is not None and score_b is not None:
                    status = TournamentMatch.MatchStatus.COMPLETED
                    winner = teams[a] if score_a > score_b else teams[b]
                    loser = teams[b] if score_a > score_b else teams[a]
                TournamentMatch.objects.create(
                    tournament=tournament,
                    pool=pool,
                    match_number=number,
                    team_a=teams[a],
                    team_b=teams[b],
                    team_a_score=score_a,
                    team_b_score=score_b,
                    winner_team=winner,
                    loser_team=loser,
                    scheduled_time=timezone.now() + timedelta(hours=number),
                    location=f"Court {(number % 3) + 1}",
                    status=status,
                )

            add_match(pool_a, 1, "Falcon Spikers", "Titan Smashers", 25, 21)
            add_match(pool_a, 2, "Eagle Aces", "Viper Spikes", 22, 25)
            add_match(pool_a, 3, "Falcon Spikers", "Eagle Aces")
            add_match(pool_a, 4, "Titan Smashers", "Viper Spikes")
            add_match(pool_b, 5, "Tiger Blockers", "Panther Setters", 25, 23)
            add_match(pool_b, 6, "Wolf Diggers", "Hawk Servers")
            add_match(pool_b, 7, "Tiger Blockers", "Wolf Diggers")
            add_match(pool_b, 8, "Panther Setters", "Hawk Servers")

        self.stdout.write(self.style.SUCCESS("Seed ready: Spring Cup 2026 in POOL_STAGE"))
        self.stdout.write(self.style.SUCCESS("Director: director.seed@local.test / test123"))
        self.stdout.write(self.style.SUCCESS("Coach: coach.a@local.test, coach.b@local.test"))
        self.stdout.write(self.style.SUCCESS("Parents: parent.a@local.test, parent.b@local.test"))

    def _upsert_user(self, email, first_name, last_name, dob):
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
        user.set_password(SEED_PASSWORD)
        user.save(update_fields=["first_name", "last_name", "date_of_birth", "verification_status", "password"])
        return user
