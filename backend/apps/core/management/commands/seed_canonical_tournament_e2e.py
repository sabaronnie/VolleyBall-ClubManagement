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
from apps.core.tournament_views import _can_submit_result, _recalculate_pool_standings, _team_ids_for_user

User = get_user_model()


class Command(BaseCommand):
    help = "Seed canonical tournament E2E data for director/coach/player/parent role testing."

    PASSWORD = "password123"
    CLUB_NAME = "NetUp Volleyball Club"
    TOURNAMENT_NAME = "Mini Spring Cup 2026"
    TEAM_NAMES = [
        "Falcon Spikers",
        "Titan Smashers",
        "Tiger Blockers",
        "Panther Setters",
    ]
    TEST_USERS = [
        ("tayma@test.com", "Tayma", "Director", date(1990, 1, 10)),
        ("karma@test.com", "Karma", "Coach", date(1992, 5, 14)),
        ("nay@test.com", "Nay", "Player", date(2010, 3, 22)),
        ("lyn@test.com", "Lyn", "Parent", date(1988, 9, 8)),
    ]

    def handle(self, *args, **options):
        with transaction.atomic():
            users = self._seed_users()
            club = self._seed_club(users["tayma@test.com"])
            teams = self._seed_teams(club)
            self._seed_memberships(users, teams, club)
            tournament, pool = self._seed_tournament(users["tayma@test.com"], club, teams)
            matches = self._seed_pool_matches(tournament, pool, teams)
            _recalculate_pool_standings(tournament, pool)

            self._run_validations(users, tournament, pool, matches, teams)

        self._print_summary(users, tournament)

    def _seed_users(self):
        users = {}
        for email, first_name, last_name, dob in self.TEST_USERS:
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
            users[email] = user
        return users

    def _seed_club(self, director):
        club, _ = Club.objects.get_or_create(
            name=self.CLUB_NAME,
            defaults={
                "short_name": "NETUP",
                "description": "Canonical tournament E2E testing club.",
                "city": "Beirut",
                "country": "Lebanon",
            },
        )
        club.short_name = "NETUP"
        club.description = "Canonical tournament E2E testing club."
        club.city = "Beirut"
        club.country = "Lebanon"
        club.save(update_fields=["short_name", "description", "city", "country"])
        ClubMembership.objects.assign_director(user=director, club=club)
        return club

    def _seed_teams(self, club):
        teams = {}
        for index, team_name in enumerate(self.TEAM_NAMES, start=1):
            team, _ = Team.objects.get_or_create(
                club=club,
                name=team_name,
                defaults={
                    "short_name": "".join(part[0] for part in team_name.split()).upper(),
                    "season": "2026",
                    "age_group": "U18",
                    "gender": Team.Gender.MIXED,
                    "status": Team.Status.ACTIVE,
                    "home_venue": "Main Sports Hall",
                    "notes": "Seeded for canonical tournament testing.",
                },
            )
            team.season = "2026"
            team.age_group = "U18"
            team.gender = Team.Gender.MIXED
            team.status = Team.Status.ACTIVE
            team.home_venue = "Main Sports Hall"
            team.notes = "Seeded for canonical tournament testing."
            team.save(update_fields=["season", "age_group", "gender", "status", "home_venue", "notes"])
            teams[team_name] = team

            for dummy_idx in range(1, 4):
                dummy_email = f"{team_name.lower().replace(' ', '.')}.player{dummy_idx}@seed.local"
                player, _ = User.objects.get_or_create(
                    email=dummy_email,
                    defaults={
                        "first_name": f"{team_name.split()[0]}P{dummy_idx}",
                        "last_name": "Dummy",
                        "date_of_birth": date(2009, min(index + dummy_idx, 12), 10 + dummy_idx),
                        "verification_status": VerificationStatus.VERIFIED,
                    },
                )
                player.verification_status = VerificationStatus.VERIFIED
                player.set_password(self.PASSWORD)
                player.save(update_fields=["verification_status", "password"])
                TeamMembership.objects.add_member(user=player, team=team, role=TeamRole.PLAYER)
        return teams

    def _seed_memberships(self, users, teams, club):
        director = users["tayma@test.com"]
        coach = users["karma@test.com"]
        player = users["nay@test.com"]
        parent = users["lyn@test.com"]

        ClubMembership.objects.assign_director(user=director, club=club)
        TeamMembership.objects.add_member(user=coach, team=teams["Falcon Spikers"], role=TeamRole.COACH)
        TeamMembership.objects.add_member(user=player, team=teams["Falcon Spikers"], role=TeamRole.PLAYER)

        ParentPlayerRelation.objects.link(
            parent=parent,
            player=player,
            is_legal_guardian=True,
            approval_status=ParentLinkApprovalStatus.APPROVED,
        )

    def _seed_tournament(self, director, club, teams):
        Tournament.objects.filter(club=club, name=self.TOURNAMENT_NAME).delete()

        start_date = timezone.localdate() + timedelta(days=7)
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
        TournamentMatch.objects.filter(tournament=tournament).delete()

        schedule = [
            ("Falcon Spikers", "Titan Smashers", 2, 0),
            ("Falcon Spikers", "Tiger Blockers", None, None),
            ("Falcon Spikers", "Panther Setters", None, None),
            ("Titan Smashers", "Tiger Blockers", None, None),
            ("Titan Smashers", "Panther Setters", None, None),
            ("Tiger Blockers", "Panther Setters", None, None),
        ]

        now = timezone.now()
        seeded_matches = []
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

            match = TournamentMatch.objects.create(
                tournament=tournament,
                pool=pool,
                match_number=idx,
                team_a=team_a,
                team_b=team_b,
                team_a_score=score_a,
                team_b_score=score_b,
                winner_team=winner,
                loser_team=loser,
                scheduled_time=now + timedelta(days=idx),
                location=f"Court {(idx % 2) + 1}",
                status=status,
            )
            seeded_matches.append(match)
        return seeded_matches

    def _run_validations(self, users, tournament, pool, matches, teams):
        all_pool_matches = list(
            TournamentMatch.objects.filter(tournament=tournament, pool=pool).order_by("match_number", "id")
        )
        if len(all_pool_matches) != 6:
            raise CommandError(f"Validation failed: expected 6 pool matches, got {len(all_pool_matches)}.")

        matchup_signatures = set()
        for match in all_pool_matches:
            if match.team_a_id == match.team_b_id:
                raise CommandError("Validation failed: a team is scheduled against itself.")
            signature = tuple(sorted((match.team_a_id, match.team_b_id)))
            if signature in matchup_signatures:
                raise CommandError("Validation failed: duplicate matchup detected.")
            matchup_signatures.add(signature)

        completed = [m for m in all_pool_matches if m.status == TournamentMatch.MatchStatus.COMPLETED]
        if len(completed) != 1:
            raise CommandError("Validation failed: expected exactly one completed pool match.")

        completed_match = completed[0]
        if completed_match.team_a != teams["Falcon Spikers"] or completed_match.team_b != teams["Titan Smashers"]:
            raise CommandError("Validation failed: completed seeded matchup is not Falcon vs Titan.")
        if completed_match.team_a_score != 2 or completed_match.team_b_score != 0:
            raise CommandError("Validation failed: completed seeded score is not 2-0.")
        if completed_match.winner_team != teams["Falcon Spikers"]:
            raise CommandError("Validation failed: winner should be Falcon Spikers.")

        rows = {row.team.name: row for row in Standing.objects.filter(tournament=tournament, pool=pool).select_related("team")}
        if rows["Falcon Spikers"].wins != 1 or rows["Falcon Spikers"].losses != 0:
            raise CommandError("Validation failed: Falcon Spikers standing is incorrect.")
        if rows["Titan Smashers"].wins != 0 or rows["Titan Smashers"].losses != 1:
            raise CommandError("Validation failed: Titan Smashers standing is incorrect.")
        if rows["Tiger Blockers"].wins != 0 or rows["Tiger Blockers"].losses != 0:
            raise CommandError("Validation failed: Tiger Blockers standing is incorrect.")
        if rows["Panther Setters"].wins != 0 or rows["Panther Setters"].losses != 0:
            raise CommandError("Validation failed: Panther Setters standing is incorrect.")

        bracket_matches_exist = TournamentMatch.objects.filter(tournament=tournament, pool__isnull=True).exists()
        if bracket_matches_exist:
            raise CommandError("Validation failed: bracket matches should not exist yet.")

        has_incomplete_pool_matches = TournamentMatch.objects.filter(tournament=tournament, pool__isnull=False).exclude(
            status=TournamentMatch.MatchStatus.COMPLETED
        ).exists()
        if not has_incomplete_pool_matches:
            raise CommandError("Validation failed: expected bracket generation precondition to fail (pool not complete).")

        if completed_match.status == TournamentMatch.MatchStatus.COMPLETED:
            self.stdout.write(
                self.style.WARNING(
                    "Validation note: completed match is reschedule-blocked by API rule (status==completed)."
                )
            )

        director = users["tayma@test.com"]
        coach = users["karma@test.com"]
        player = users["nay@test.com"]
        parent = users["lyn@test.com"]

        coach_team_ids = _team_ids_for_user(coach)
        player_team_ids = _team_ids_for_user(player)
        parent_team_ids = _team_ids_for_user(parent)

        coach_visible = TournamentMatch.objects.filter(tournament=tournament).filter(
            team_a_id__in=coach_team_ids
        ) | TournamentMatch.objects.filter(tournament=tournament).filter(team_b_id__in=coach_team_ids)
        coach_visible = coach_visible.distinct().count()
        if coach_visible != 3:
            raise CommandError(f"Validation failed: coach should see 3 Falcon matches, got {coach_visible}.")

        player_visible = TournamentMatch.objects.filter(tournament=tournament).filter(
            team_a_id__in=player_team_ids
        ) | TournamentMatch.objects.filter(tournament=tournament).filter(team_b_id__in=player_team_ids)
        player_visible = player_visible.distinct().count()
        if player_visible != 3:
            raise CommandError(f"Validation failed: player should see 3 Falcon matches, got {player_visible}.")

        parent_visible = TournamentMatch.objects.filter(tournament=tournament).filter(
            team_a_id__in=parent_team_ids
        ) | TournamentMatch.objects.filter(tournament=tournament).filter(team_b_id__in=parent_team_ids)
        parent_visible = parent_visible.distinct().count()
        if parent_visible != 3:
            raise CommandError(f"Validation failed: parent should see 3 child-team matches, got {parent_visible}.")

        non_falcon_match = TournamentMatch.objects.filter(tournament=tournament).exclude(
            team_a=teams["Falcon Spikers"]
        ).exclude(team_b=teams["Falcon Spikers"]).first()
        if non_falcon_match and _can_submit_result(coach, non_falcon_match):
            raise CommandError("Validation failed: coach can submit result for non-Falcon match.")

        falcon_match = TournamentMatch.objects.filter(tournament=tournament).filter(
            team_a=teams["Falcon Spikers"]
        ).first()
        if falcon_match and not _can_submit_result(coach, falcon_match):
            raise CommandError("Validation failed: coach should be able to submit result for Falcon match.")

        if not Tournament.objects.filter(id=tournament.id, club__memberships__user=director).exists():
            raise CommandError("Validation failed: director scope is not configured.")

    def _print_summary(self, users, tournament):
        self.stdout.write(self.style.SUCCESS("\nCanonical tournament E2E seed completed.\n"))
        self.stdout.write(self.style.SUCCESS("Login credentials"))
        self.stdout.write(f"  Director: tayma@test.com / {self.PASSWORD}")
        self.stdout.write(f"  Coach:    karma@test.com / {self.PASSWORD}")
        self.stdout.write(f"  Player:   nay@test.com / {self.PASSWORD}")
        self.stdout.write(f"  Parent:   lyn@test.com / {self.PASSWORD}")

        self.stdout.write(self.style.SUCCESS("\nSeeded entities"))
        self.stdout.write(f"  Club: {self.CLUB_NAME}")
        self.stdout.write(f"  Tournament: {tournament.name}")
        self.stdout.write("  Format: POOL_AND_BRACKET")
        self.stdout.write("  Status: POOL_STAGE")
        self.stdout.write("  Pool: Pool A")
        self.stdout.write("  Pool matches: 6 (1 completed, 5 scheduled)")

        self.stdout.write(self.style.SUCCESS("\nManual API checklist"))
        self.stdout.write("  1) Director can reschedule scheduled match; completed match returns 400.")
        self.stdout.write("  2) Director completes remaining pool matches, then generates bracket.")
        self.stdout.write("  3) Coach sees Falcon matches only, cannot generate pools/bracket.")
        self.stdout.write("  4) Player/Parent see team-scoped matches, standings, bracket read-only.")
        self.stdout.write("  5) Continue bracket results until tournament reaches COMPLETED.")
