from datetime import date, datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.core.models import (
    Club,
    ClubMembership,
    MatchPlayerStat,
    ParentPlayerRelation,
    PlayerProfile,
    Team,
    TeamMembership,
    TeamRole,
    Tournament,
    TournamentFixture,
    TournamentPool,
    TrainingSession,
    VerificationStatus,
)
from apps.core.views import _reconcile_tournament_bracket

User = get_user_model()
SEED_PASSWORD = "test123"

CLUB_NAME = "Spring Club QA"
TOURNAMENT_NAME = "Spring Cup 2026"

TEAM_NAMES = (
    "AUB Falcons",
    "AUB Storm",
    "Titan Smashers",
    "Viper Spikes",
    "Tiger Blockers",
    "Panther Setters",
    "Wolf Diggers",
    "Hawk Servers",
)

POOL_A_TEAMS = TEAM_NAMES[:4]
POOL_B_TEAMS = TEAM_NAMES[4:]

PERSONAS = {
    # Director
    "tayma": {"first": "Tayma", "last": "Director", "dob": date(1988, 7, 14)},
    # Coaches
    "lyn": {"first": "Lyn", "last": "Coach", "dob": date(1993, 3, 18)},
    "farouk": {"first": "Farouk", "last": "Coach", "dob": date(1992, 11, 30)},
    "coach_rana": {"first": "Rana", "last": "Coach", "dob": date(1994, 1, 10)},
    "coach_hadi": {"first": "Hadi", "last": "Coach", "dob": date(1991, 8, 8)},
    # Parents
    "parent_maya": {"first": "Maya", "last": "Parent", "dob": date(1987, 9, 2)},
    "parent_nour": {"first": "Nour", "last": "Parent", "dob": date(1986, 5, 21)},
}

PLAYER_ALIASES = (
    "karma",
    "nay",
    "racha",
    "aida",
    "omar",
    "zeina",
    "jad",
    "lea",
    "sara",
    "ali",
    "mira",
    "sam",
    "rita",
    "ziad",
    "tina",
    "karim",
    "joelle",
    "fadi",
    "yara",
    "elie",
    "lana",
    "hassan",
    "nadine",
    "maher",
)

ROSTERS = {
    "AUB Falcons": ("karma", "aida", "jad", "lea", "sara", "ali"),
    "AUB Storm": ("nay", "mira", "sam", "rita", "ziad", "karim"),
    "Titan Smashers": ("racha", "joelle", "fadi", "yara", "elie", "lana"),
    "Viper Spikes": ("omar", "zeina", "tina", "hassan", "nadine", "maher"),
    "Tiger Blockers": ("karma", "nay", "aida", "sara", "sam", "yara"),
    "Panther Setters": ("racha", "jad", "lea", "rita", "karim", "elie"),
    "Wolf Diggers": ("omar", "zeina", "mira", "fadi", "hassan", "lana"),
    "Hawk Servers": ("ali", "ziad", "tina", "joelle", "nadine", "maher"),
}

TEAM_COACH = {
    "AUB Falcons": "lyn",
    "AUB Storm": "lyn",
    "Titan Smashers": "coach_rana",
    "Viper Spikes": "coach_rana",
    "Tiger Blockers": "farouk",
    "Panther Setters": "farouk",
    "Wolf Diggers": "coach_hadi",
    "Hawk Servers": "coach_hadi",
}

CAPTAIN_BY_TEAM = {
    "AUB Falcons": "karma",
    "AUB Storm": "nay",
    "Titan Smashers": "racha",
    "Viper Spikes": "omar",
    "Tiger Blockers": "karma",
    "Panther Setters": "racha",
    "Wolf Diggers": "omar",
    "Hawk Servers": "ali",
}


class Command(BaseCommand):
    help = "Seed a realistic end-to-end tournament dataset with clear RBAC personas."

    def handle(self, *args, **options):
        with transaction.atomic():
            users = self._seed_users()
            club = self._seed_club(users["tayma"])
            teams = self._seed_teams(club)
            self._seed_memberships(users, club, teams)
            self._seed_player_profiles(users)
            self._seed_parent_links(users)
            tournament = self._seed_hybrid_tournament(users["tayma"], club, teams, users)

        self.stdout.write(self.style.SUCCESS("Tournament seed completed successfully."))
        self.stdout.write(self.style.SUCCESS(f"Club: {club.name}"))
        self.stdout.write(self.style.SUCCESS(f"Tournament: {tournament.name}"))
        self.stdout.write(self.style.SUCCESS(f"Common password: {SEED_PASSWORD}"))
        self.stdout.write(self.style.SUCCESS("Use these personas for testing:"))
        self.stdout.write("  - Director: tayma@seed.local")
        self.stdout.write("  - Coach (Pool A teams): lyn@seed.local")
        self.stdout.write("  - Coach (Pool B teams): farouk@seed.local")
        self.stdout.write("  - Parent: parent_maya@seed.local (linked to karma + nay)")
        self.stdout.write("  - Parent: parent_nour@seed.local (linked to racha + omar)")
        self.stdout.write("  - Players: karma@seed.local, nay@seed.local, racha@seed.local, omar@seed.local")

    def _seed_users(self):
        users = {}

        all_people = dict(PERSONAS)
        for idx, alias in enumerate(PLAYER_ALIASES):
            all_people.setdefault(
                alias,
                {
                    "first": alias.capitalize(),
                    "last": "Player",
                    "dob": date(2008, ((idx % 11) + 1), ((idx % 25) + 1)),
                },
            )

        for alias, row in all_people.items():
            user, _ = User.objects.get_or_create(
                email=f"{alias}@seed.local",
                defaults={
                    "first_name": row["first"],
                    "last_name": row["last"],
                    "date_of_birth": row["dob"],
                    "verification_status": VerificationStatus.VERIFIED,
                },
            )
            user.first_name = row["first"]
            user.last_name = row["last"]
            user.date_of_birth = row["dob"]
            user.verification_status = VerificationStatus.VERIFIED
            user.set_password(SEED_PASSWORD)
            user.save(
                update_fields=["first_name", "last_name", "date_of_birth", "verification_status", "password"]
            )
            users[alias] = user
        return users

    def _seed_club(self, director):
        club = Club.objects.filter(name=CLUB_NAME).first()
        if club is None:
            club = Club.objects.create_club(
                name=CLUB_NAME,
                director=director,
                short_name="SCQ",
                description="High-fidelity tournament QA sandbox.",
                city="Beirut",
                country="Lebanon",
            )
        else:
            club.short_name = "SCQ"
            club.description = "High-fidelity tournament QA sandbox."
            club.city = "Beirut"
            club.country = "Lebanon"
            club.save(update_fields=["short_name", "description", "city", "country"])
            ClubMembership.objects.assign_director(user=director, club=club)
        return club

    def _seed_teams(self, club):
        teams = {}
        for idx, team_name in enumerate(TEAM_NAMES):
            team, _ = Team.objects.get_or_create(
                club=club,
                name=team_name,
                defaults={
                    "season": "2025-26",
                    "age_group": f"U{16 + (idx % 4)}",
                    "gender": Team.Gender.MIXED,
                    "status": Team.Status.ACTIVE,
                    "home_venue": f"{team_name.split()[0]} Main Court",
                    "description": "Seeded tournament team.",
                },
            )
            team.season = "2025-26"
            team.age_group = f"U{16 + (idx % 4)}"
            team.gender = Team.Gender.MIXED
            team.status = Team.Status.ACTIVE
            team.home_venue = f"{team_name.split()[0]} Main Court"
            team.description = "Seeded tournament team."
            team.save(
                update_fields=["season", "age_group", "gender", "status", "home_venue", "description"]
            )
            teams[team_name] = team
        return teams

    def _seed_memberships(self, users, club, teams):
        ClubMembership.objects.assign_director(user=users["tayma"], club=club)

        for team_name, team in teams.items():
            coach_alias = TEAM_COACH[team_name]
            TeamMembership.objects.add_member(user=users[coach_alias], team=team, role=TeamRole.COACH)

            for player_alias in ROSTERS[team_name]:
                TeamMembership.objects.add_member(
                    user=users[player_alias],
                    team=team,
                    role=TeamRole.PLAYER,
                    is_captain=(player_alias == CAPTAIN_BY_TEAM[team_name]),
                )

    def _seed_player_profiles(self, users):
        positions = ("Setter", "Outside Hitter", "Middle Blocker", "Opposite", "Libero")
        for idx, alias in enumerate(PLAYER_ALIASES):
            PlayerProfile.objects.update_or_create(
                user=users[alias],
                defaults={
                    "jersey_number": (idx % 18) + 1,
                    "primary_position": positions[idx % len(positions)],
                    "notes": "Tournament QA seeded profile.",
                },
            )

    def _seed_parent_links(self, users):
        for child_alias in ("karma", "nay"):
            ParentPlayerRelation.objects.link(
                parent=users["parent_maya"],
                player=users[child_alias],
                is_legal_guardian=True,
            )
        for child_alias in ("racha", "omar"):
            ParentPlayerRelation.objects.link(
                parent=users["parent_nour"],
                player=users[child_alias],
                is_legal_guardian=True,
            )

    def _seed_hybrid_tournament(self, creator, club, teams, users):
        Tournament.objects.filter(club=club, name=TOURNAMENT_NAME).delete()
        tournament = Tournament.objects.create(
            club=club,
            created_by=creator,
            name=TOURNAMENT_NAME,
            tournament_type=Tournament.TournamentType.HYBRID,
            number_of_teams=8,
            pool_count=2,
            teams_per_pool=4,
            teams_qualifying_per_pool=2,
            match_duration_minutes=90,
            scoring_format="Best of 3 to 25",
            start_date=timezone.localdate() - timedelta(days=3),
            start_time=time(18, 0),
            venue="Spring Club Arena",
            status=Tournament.Status.GENERATED,
        )
        tournament.teams.set([teams[name] for name in TEAM_NAMES])

        pool_a = TournamentPool.objects.create(tournament=tournament, name="Pool A", pool_order=1)
        pool_b = TournamentPool.objects.create(tournament=tournament, name="Pool B", pool_order=2)

        rounds_a = self._round_robin([teams[name] for name in POOL_A_TEAMS])
        rounds_b = self._round_robin([teams[name] for name in POOL_B_TEAMS])

        self._create_pool_fixtures_and_results(
            tournament=tournament,
            pool=pool_a,
            rounds=rounds_a,
            round_offset_days=0,
            users=users,
        )
        self._create_pool_fixtures_and_results(
            tournament=tournament,
            pool=pool_b,
            rounds=rounds_b,
            round_offset_days=0,
            users=users,
        )

        # Pre-create hybrid bracket placeholders. Reconciliation will seed teams and sessions.
        TournamentFixture.objects.create(
            tournament=tournament,
            pool=None,
            training_session=None,
            stage_type=TournamentFixture.StageType.BRACKET,
            round_number=4,
            round_label="Semi-finals",
            fixture_order=1,
            placeholder_home_label="Seed 1",
            placeholder_away_label="Seed 4",
            scheduled_date=tournament.start_date + timedelta(days=3),
            start_time=tournament.start_time,
        )
        TournamentFixture.objects.create(
            tournament=tournament,
            pool=None,
            training_session=None,
            stage_type=TournamentFixture.StageType.BRACKET,
            round_number=4,
            round_label="Semi-finals",
            fixture_order=2,
            placeholder_home_label="Seed 2",
            placeholder_away_label="Seed 3",
            scheduled_date=tournament.start_date + timedelta(days=3),
            start_time=tournament.start_time,
        )
        TournamentFixture.objects.create(
            tournament=tournament,
            pool=None,
            training_session=None,
            stage_type=TournamentFixture.StageType.BRACKET,
            round_number=5,
            round_label="Final",
            fixture_order=1,
            placeholder_home_label="Winner of Semi-finals Match 1",
            placeholder_away_label="Winner of Semi-finals Match 2",
            scheduled_date=tournament.start_date + timedelta(days=4),
            start_time=tournament.start_time,
        )

        # Seed bracket teams from completed pool stage and ensure bracket sessions exist.
        _reconcile_tournament_bracket(tournament)
        return tournament

    def _round_robin(self, teams):
        rotation = list(teams)
        if len(rotation) % 2 == 1:
            rotation.append(None)
        rounds = []
        for round_idx in range(len(rotation) - 1):
            pairings = []
            half = len(rotation) // 2
            for idx in range(half):
                left = rotation[idx]
                right = rotation[-(idx + 1)]
                if left is None or right is None:
                    continue
                if round_idx % 2 == 1:
                    left, right = right, left
                pairings.append((left, right))
            rounds.append(pairings)
            rotation = [rotation[0], rotation[-1], *rotation[1:-1]]
        return rounds

    def _create_pool_fixtures_and_results(self, tournament, pool, rounds, round_offset_days, users):
        for round_index, pairings in enumerate(rounds, start=1):
            round_date = tournament.start_date + timedelta(days=round_offset_days + round_index - 1)
            for fixture_order, (home_team, away_team) in enumerate(pairings, start=1):
                coach_alias = TEAM_COACH[home_team.name]
                created_by = users[coach_alias]
                session = TrainingSession.objects.create(
                    team=home_team,
                    title=f"{tournament.name}: {home_team.name} vs {away_team.name}",
                    session_type=TrainingSession.SessionType.MATCH,
                    scheduled_date=round_date,
                    start_time=tournament.start_time,
                    end_time=(datetime.combine(date.today(), tournament.start_time) + timedelta(minutes=90)).time(),
                    location=tournament.venue,
                    opponent=away_team.name,
                    opponent_team=away_team,
                    match_type=TrainingSession.MatchType.TOURNAMENT,
                    match_request_status=TrainingSession.MatchRequestStatus.ACCEPTED,
                    notes=f"Tournament: {tournament.name} | Round: Pool Round {round_index} | Pool: {pool.name}",
                    notify_players=False,
                    notify_parents=False,
                    status=TrainingSession.Status.SCHEDULED,
                    created_by=created_by,
                )

                home_score = 0
                away_score = 0
                for idx, player_alias in enumerate(ROSTERS[home_team.name], start=1):
                    stat = self._stat_line(round_index, fixture_order, idx, home_bias=1)
                    home_score += stat["points_scored"]
                    MatchPlayerStat.objects.create(
                        training_session=session,
                        player=users[player_alias],
                        updated_by=created_by,
                        **stat,
                    )
                for idx, player_alias in enumerate(ROSTERS[away_team.name], start=1):
                    stat = self._stat_line(round_index, fixture_order, idx, home_bias=0)
                    away_score += stat["points_scored"]
                    MatchPlayerStat.objects.create(
                        training_session=session,
                        player=users[player_alias],
                        updated_by=users[TEAM_COACH[away_team.name]],
                        **stat,
                    )

                if home_score == away_score:
                    # Avoid draws so bracket winner logic is deterministic in tests.
                    bump_alias = ROSTERS[home_team.name][0]
                    row = MatchPlayerStat.objects.get(training_session=session, player=users[bump_alias])
                    row.points_scored += 1
                    row.save(update_fields=["points_scored", "updated_at"])
                    home_score += 1

                session.match_ended_at = timezone.make_aware(
                    datetime.combine(round_date, tournament.start_time)
                ) + timedelta(minutes=95)
                session.save(update_fields=["match_ended_at", "updated_at"])

                TournamentFixture.objects.create(
                    tournament=tournament,
                    pool=pool,
                    training_session=session,
                    stage_type=TournamentFixture.StageType.POOL,
                    round_number=round_index,
                    round_label=f"Pool Round {round_index}",
                    fixture_order=fixture_order,
                    home_team=home_team,
                    away_team=away_team,
                    scheduled_date=round_date,
                    start_time=tournament.start_time,
                )

    def _stat_line(self, round_index, fixture_order, player_idx, *, home_bias):
        base = round_index * 3 + fixture_order + player_idx
        return {
            "points_scored": 6 + (base % 7) + (1 if home_bias else 0),
            "aces": base % 3,
            "blocks": base % 2,
            "assists": 2 + (base % 5),
            "errors": base % 2,
            "digs": 3 + (base % 4),
        }
from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.core.models import (
    Club,
    ClubMembership,
    MatchPlayerStat,
    Notification,
    ParentPlayerRelation,
    PlayerProfile,
    Team,
    TeamMembership,
    TeamRole,
    TeamScheduleEntry,
    Tournament,
    TrainingSession,
    TrainingSessionConfirmation,
    VerificationStatus,
)

User = get_user_model()
SEED_PASSWORD = "test123"
PEOPLE = ("tayma", "karma", "lyn", "nay", "racha", "farouk")
CLUBS = ("AUB", "CPF", "NAHDA", "RIYADI")


class Command(BaseCommand):
    help = "Seed QA data with realistic clubs, teams, sessions, and tournament."

    def add_arguments(self, parser):
        parser.add_argument("--with-tournament", action="store_true")

    def handle(self, *args, **options):
        with transaction.atomic():
            people = self._users()
            clubs = self._clubs(people["tayma"])
            teams = self._teams(clubs)
            self._memberships(people, clubs, teams)
            self._profiles_and_links(people)
            sessions = self._sessions(people, teams)
            self._confirmations_and_stats(people, sessions)
            self._notifications(people, teams, sessions)
            if options["with_tournament"]:
                self._tournament(people["tayma"], clubs["AUB"], teams)
        self.stdout.write(self.style.SUCCESS("QA seed completed."))
        self.stdout.write(self.style.SUCCESS("Users: tayma, karma, lyn, nay, racha, farouk"))
        self.stdout.write(self.style.SUCCESS("Clubs: AUB, CPF, NAHDA, RIYADI"))
        self.stdout.write(self.style.SUCCESS(f"Password: {SEED_PASSWORD}"))

    def _users(self):
        people = {}
        for name in PEOPLE:
            user, _ = User.objects.get_or_create(
                email=f"{name}@qa.seed.local",
                defaults={"first_name": name.capitalize(), "last_name": "QA", "date_of_birth": date(2008, 1, 1), "verification_status": VerificationStatus.VERIFIED},
            )
            user.first_name = name.capitalize()
            user.last_name = "QA"
            user.verification_status = VerificationStatus.VERIFIED
            user.set_password(SEED_PASSWORD)
            user.save(update_fields=["first_name", "last_name", "verification_status", "password"])
            people[name] = user
        return people

    def _clubs(self, director):
        clubs = {}
        for i, name in enumerate(CLUBS):
            club = Club.objects.filter(name=name).first() or Club.objects.create_club(name=name, director=director)
            club.short_name = name
            club.description = f"{name} volleyball QA club"
            club.city = "Beirut"
            club.country = "Lebanon"
            club.default_monthly_player_fee = Decimal(str(70 + i * 10))
            club.save()
            ClubMembership.objects.assign_director(user=director, club=club)
            clubs[name] = club
        return clubs

    def _teams(self, clubs):
        teams = {}
        for i, club in enumerate(CLUBS):
            team, _ = Team.objects.get_or_create(club=clubs[club], name=f"{club} First Team")
            team.season = "2025-26"
            team.age_group = f"U{17 + i}"
            team.gender = Team.Gender.MIXED
            team.status = Team.Status.ACTIVE
            team.home_venue = f"{club} Arena"
            team.save()
            teams[club] = team
        return teams

    def _memberships(self, people, clubs, teams):
        for club in clubs.values():
            ClubMembership.objects.assign_director(user=people["tayma"], club=club)
        TeamMembership.objects.add_member(user=people["lyn"], team=teams["AUB"], role=TeamRole.COACH)
        TeamMembership.objects.add_member(user=people["farouk"], team=teams["CPF"], role=TeamRole.COACH)
        TeamMembership.objects.add_member(user=people["lyn"], team=teams["NAHDA"], role=TeamRole.COACH)
        TeamMembership.objects.add_member(user=people["farouk"], team=teams["RIYADI"], role=TeamRole.COACH)
        TeamMembership.objects.add_member(user=people["karma"], team=teams["AUB"], role=TeamRole.PLAYER, is_captain=True)
        TeamMembership.objects.add_member(user=people["karma"], team=teams["CPF"], role=TeamRole.PLAYER)
        TeamMembership.objects.add_member(user=people["nay"], team=teams["NAHDA"], role=TeamRole.PLAYER)
        TeamMembership.objects.add_member(user=people["racha"], team=teams["RIYADI"], role=TeamRole.PLAYER, is_captain=True)

    def _profiles_and_links(self, people):
        PlayerProfile.objects.update_or_create(user=people["karma"], defaults={"jersey_number": 7, "primary_position": "Setter"})
        PlayerProfile.objects.update_or_create(user=people["nay"], defaults={"jersey_number": 11, "primary_position": "Libero"})
        PlayerProfile.objects.update_or_create(user=people["racha"], defaults={"jersey_number": 4, "primary_position": "Outside Hitter"})
        for player in ("karma", "nay", "racha"):
            ParentPlayerRelation.objects.link(parent=people["tayma"], player=people[player], is_legal_guardian=True)

    def _sessions(self, people, teams):
        today = timezone.localdate()
        data = {}
        for i, club in enumerate(CLUBS):
            coach = people["lyn"] if club in ("AUB", "NAHDA") else people["farouk"]
            team = teams[club]
            TeamScheduleEntry.objects.update_or_create(team=team, activity_name="Technical Training", weekday=i + 1, defaults={"start_time": time(18, 0), "end_time": time(19, 30), "location": team.home_venue, "created_by": coach})
            past, _ = TrainingSession.objects.get_or_create(team=team, title=f"{club} Training", scheduled_date=today - timedelta(days=7 + i), defaults={"session_type": TrainingSession.SessionType.TRAINING, "start_time": time(18, 0), "end_time": time(19, 30), "location": team.home_venue, "created_by": coach})
            upcoming, _ = TrainingSession.objects.get_or_create(team=team, title=f"{club} League Match", scheduled_date=today + timedelta(days=4 + i), defaults={"session_type": TrainingSession.SessionType.MATCH, "start_time": time(19, 0), "end_time": time(21, 0), "location": team.home_venue, "opponent": "City Rivals", "match_type": TrainingSession.MatchType.LEAGUE, "created_by": coach})
            players = [m.user for m in TeamMembership.objects.filter(team=team, role=TeamRole.PLAYER, is_active=True)]
            data[club] = {"coach": coach, "players": players, "past": past, "match": upcoming}
        return data

    def _confirmations_and_stats(self, people, sessions):
        for club in CLUBS:
            payload = sessions[club]
            for i, player in enumerate(payload["players"], start=1):
                TrainingSessionConfirmation.objects.update_or_create(training_session=payload["past"], player=player, defaults={"confirmed_by": people["tayma"] if i == 1 else player})
                MatchPlayerStat.objects.update_or_create(training_session=payload["match"], player=player, defaults={"points_scored": 8 + 2 * i, "aces": i, "blocks": i, "assists": i + 2, "errors": i % 2, "digs": i + 4, "updated_by": payload["coach"]})

    def _notifications(self, people, teams, sessions):
        for club in CLUBS:
            team = teams[club]
            payload = sessions[club]
            Notification.objects.get_or_create(recipient=payload["coach"], team=team, category=Notification.Category.SESSION, title=f"{club} reminder", message="Review attendance and schedule.")
            Notification.objects.get_or_create(recipient=people["tayma"], team=team, training_session=payload["past"], category=Notification.Category.ATTENDANCE_INCOMPLETE, title=f"{club} follow-up", message="Some confirmations are missing.", created_by=payload["coach"])

    def _tournament(self, creator, club, teams):
        tournament, _ = Tournament.objects.get_or_create(
            club=club,
            name="QA Hybrid Tournament",
            defaults={"created_by": creator, "tournament_type": Tournament.TournamentType.HYBRID, "number_of_teams": len(teams), "pool_count": 2, "teams_per_pool": 2, "teams_qualifying_per_pool": 1, "match_duration_minutes": 90, "scoring_format": "Best of 5 to 25", "start_date": timezone.localdate() + timedelta(days=7), "venue": "Beirut Central Arena"},
        )
        tournament.teams.set(list(teams.values()))
from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.core.models import (
    CoachFeedbackStatus,
    Club,
    ClubMembership,
    DirectorPaymentAuditLog,
    FeePaymentLedgerEntry,
    MatchPlayerStat,
    Notification,
    ParentPlayerRelation,
    PaymentSchedule,
    PlayerFeeRecord,
    PlayerProfile,
    PlayerWeeklySkillMetric,
    Team,
    TeamCoachFeedback,
    TeamMembership,
    TeamRole,
    TeamRosterPlayerStat,
    TeamScheduleEntry,
    TeamSkillCategory,
    TeamSkillDashboardMetric,
    Tournament,
    TrainingSession,
    TrainingSessionConfirmation,
    VerificationStatus,
)

User = get_user_model()
SEED_PASSWORD = "test123"
PEOPLE = ("tayma", "karma", "lyn", "nay", "racha", "farouk")
CLUBS = ("AUB", "CPF", "NAHDA", "RIYADI")
TEAM_NAMES = {"AUB": "AUB Spikers", "CPF": "CPF Chargers", "NAHDA": "NAHDA Eagles", "RIYADI": "RIYADI Warriors"}


class Command(BaseCommand):
    help = "Seed realistic QA data for clubs, teams, sessions, dashboard, fees, and tournament testing."

    def add_arguments(self, parser):
        parser.add_argument("--with-tournament", action="store_true")

    def handle(self, *args, **options):
        with transaction.atomic():
            people = self._seed_people()
            clubs = self._seed_clubs(people["tayma"])
            teams = self._seed_teams(clubs)
            self._seed_memberships(people, clubs, teams)
            self._seed_profiles_and_parent_links(people)
            sessions = self._seed_schedule_and_sessions(people, teams)
            self._seed_confirmations_and_stats(people, sessions)
            self._seed_dashboard_rows(people, teams)
            self._seed_progress_rows(people, teams)
            self._seed_fees_and_audit(people, clubs, teams)
            self._seed_notifications(people, teams, sessions)
            tournament = self._seed_tournament(people["tayma"], clubs["AUB"], teams) if options["with_tournament"] else None

        self.stdout.write(self.style.SUCCESS("QA seed completed successfully."))
        self.stdout.write(self.style.SUCCESS(f"Clubs: {', '.join(CLUBS)}"))
        self.stdout.write(self.style.SUCCESS("Users: tayma, karma, lyn, nay, racha, farouk"))
        self.stdout.write(self.style.SUCCESS(f"Password for all seeded users: {SEED_PASSWORD}"))
        if tournament:
            self.stdout.write(self.style.SUCCESS(f"Tournament: {tournament.name} (id={tournament.id})"))

    def _seed_people(self):
        role_dob = {"tayma": date(1988, 7, 14), "lyn": date(1994, 3, 18), "farouk": date(1992, 11, 30)}
        people = {}
        for name in PEOPLE:
            user, _ = User.objects.get_or_create(
                email=f"{name}@qa.seed.local",
                defaults={
                    "first_name": name.capitalize(),
                    "last_name": "QA",
                    "date_of_birth": role_dob.get(name, date(2008, 9, 12)),
                    "verification_status": VerificationStatus.VERIFIED,
                },
            )
            user.first_name = name.capitalize()
            user.last_name = "QA"
            user.verification_status = VerificationStatus.VERIFIED
            user.set_password(SEED_PASSWORD)
            user.save(update_fields=["first_name", "last_name", "verification_status", "password"])
            people[name] = user
        return people

    def _seed_clubs(self, director):
        clubs = {}
        for idx, name in enumerate(CLUBS):
            club = Club.objects.filter(name=name).first()
            if club is None:
                club = Club.objects.create_club(name=name, director=director)
            club.short_name = name
            club.description = f"{name} volleyball QA club"
            club.city = "Beirut"
            club.country = "Lebanon"
            club.founded_year = 1990 + idx
            club.default_monthly_player_fee = Decimal(str(70 + (idx * 5)))
            club.save()
            ClubMembership.objects.assign_director(user=director, club=club)
            clubs[name] = club
        return clubs

    def _seed_teams(self, clubs):
        teams = {}
        for idx, club_name in enumerate(CLUBS):
            team, _ = Team.objects.get_or_create(club=clubs[club_name], name=TEAM_NAMES[club_name])
            team.season = "2025-26"
            team.age_group = f"U{17 + idx}"
            team.gender = Team.Gender.MIXED
            team.status = Team.Status.ACTIVE
            team.home_venue = f"{club_name} Arena"
            team.description = f"{club_name} first roster for QA."
            team.save()
            teams[club_name] = team
        return teams

    def _seed_memberships(self, people, clubs, teams):
        for club in clubs.values():
            ClubMembership.objects.assign_director(user=people["tayma"], club=club)
        TeamMembership.objects.add_member(user=people["lyn"], team=teams["AUB"], role=TeamRole.COACH)
        TeamMembership.objects.add_member(user=people["lyn"], team=teams["NAHDA"], role=TeamRole.COACH)
        TeamMembership.objects.add_member(user=people["farouk"], team=teams["CPF"], role=TeamRole.COACH)
        TeamMembership.objects.add_member(user=people["farouk"], team=teams["RIYADI"], role=TeamRole.COACH)
        TeamMembership.objects.add_member(user=people["karma"], team=teams["AUB"], role=TeamRole.PLAYER, is_captain=True)
        TeamMembership.objects.add_member(user=people["karma"], team=teams["CPF"], role=TeamRole.PLAYER)
        TeamMembership.objects.add_member(user=people["nay"], team=teams["NAHDA"], role=TeamRole.PLAYER)
        TeamMembership.objects.add_member(user=people["nay"], team=teams["RIYADI"], role=TeamRole.PLAYER)
        TeamMembership.objects.add_member(user=people["racha"], team=teams["CPF"], role=TeamRole.PLAYER)
        TeamMembership.objects.add_member(user=people["racha"], team=teams["RIYADI"], role=TeamRole.PLAYER, is_captain=True)

    def _seed_profiles_and_parent_links(self, people):
        PlayerProfile.objects.update_or_create(user=people["karma"], defaults={"jersey_number": 7, "primary_position": "Setter"})
        PlayerProfile.objects.update_or_create(user=people["nay"], defaults={"jersey_number": 11, "primary_position": "Libero"})
        PlayerProfile.objects.update_or_create(user=people["racha"], defaults={"jersey_number": 4, "primary_position": "Outside Hitter"})
        for child in ("karma", "nay", "racha"):
            ParentPlayerRelation.objects.link(parent=people["tayma"], player=people[child], is_legal_guardian=True)

    def _players_for(self, people, club_name):
        return {"AUB": [people["karma"], people["racha"]], "CPF": [people["karma"], people["racha"]], "NAHDA": [people["nay"], people["karma"]], "RIYADI": [people["nay"], people["racha"]]}[club_name]

    def _seed_schedule_and_sessions(self, people, teams):
        today = timezone.localdate()
        sessions = {}
        for idx, club_name in enumerate(CLUBS):
            team = teams[club_name]
            coach = people["lyn"] if club_name in ("AUB", "NAHDA") else people["farouk"]
            TeamScheduleEntry.objects.update_or_create(
                team=team, activity_name="Technical Training", weekday=(idx + 1),
                defaults={"start_time": time(18, 0), "end_time": time(19, 30), "location": team.home_venue, "created_by": coach},
            )
            past, _ = TrainingSession.objects.get_or_create(
                team=team, title=f"{club_name} Ball Control", scheduled_date=today - timedelta(days=9 + idx),
                defaults={"session_type": TrainingSession.SessionType.TRAINING, "start_time": time(18, 0), "end_time": time(19, 30), "location": team.home_venue, "created_by": coach},
            )
            now, _ = TrainingSession.objects.get_or_create(
                team=team, title=f"{club_name} Practice Today", scheduled_date=today,
                defaults={"session_type": TrainingSession.SessionType.TRAINING, "start_time": time(18, 30), "end_time": time(20, 0), "location": team.home_venue, "created_by": coach},
            )
            match, _ = TrainingSession.objects.get_or_create(
                team=team, title=f"{club_name} League Match", scheduled_date=today + timedelta(days=4 + idx),
                defaults={"session_type": TrainingSession.SessionType.MATCH, "start_time": time(19, 0), "end_time": time(21, 0), "location": team.home_venue, "opponent": "City Rivals", "match_type": TrainingSession.MatchType.LEAGUE, "created_by": coach},
            )
            sessions[club_name] = {"coach": coach, "players": self._players_for(people, club_name), "past": past, "now": now, "match": match}
        return sessions

    def _seed_confirmations_and_stats(self, people, sessions):
        for club_name in CLUBS:
            payload = sessions[club_name]
            for i, player in enumerate(payload["players"], start=1):
                TrainingSessionConfirmation.objects.update_or_create(training_session=payload["now"], player=player, defaults={"confirmed_by": player})
                if i % 2 == 1:
                    TrainingSessionConfirmation.objects.update_or_create(training_session=payload["past"], player=player, defaults={"confirmed_by": people["tayma"]})
                MatchPlayerStat.objects.update_or_create(
                    training_session=payload["match"], player=player,
                    defaults={"points_scored": 8 + i * 2, "aces": i, "blocks": i, "assists": 3 + i, "errors": i % 2, "digs": 5 + i, "updated_by": payload["coach"]},
                )

    def _seed_dashboard_rows(self, people, teams):
        rows = [(TeamSkillCategory.ATTACK, Decimal("78.00"), Decimal("74.00")), (TeamSkillCategory.DEFENSE, Decimal("82.00"), Decimal("79.00")), (TeamSkillCategory.SERVE, Decimal("75.00"), Decimal("77.00")), (TeamSkillCategory.BLOCK, Decimal("69.00"), Decimal("72.00"))]
        for club_name in CLUBS:
            team = teams[club_name]
            coach = people["lyn"] if club_name in ("AUB", "NAHDA") else people["farouk"]
            players = self._players_for(people, club_name)
            for skill, attendance, performance in rows:
                TeamSkillDashboardMetric.objects.update_or_create(team=team, skill_category=skill, defaults={"attendance_rate": attendance, "average_performance": performance})
            for i, player in enumerate(players, start=1):
                TeamRosterPlayerStat.objects.update_or_create(team=team, player=player, defaults={"spikes": 6 + i, "blocks": 1 + i, "serve_percentage": Decimal(str(70 + i * 4)), "prior_serve_percentage": Decimal(str(66 + i * 3))})
                TeamCoachFeedback.objects.update_or_create(team=team, player=player, coach=coach, body=f"{player.first_name} should improve transition timing and communication.", defaults={"status": CoachFeedbackStatus.PENDING if i % 2 == 0 else CoachFeedbackStatus.ADDRESSED})

    def _seed_progress_rows(self, people, teams):
        monday = timezone.localdate() - timedelta(days=timezone.localdate().weekday()) - timedelta(weeks=5)
        for club_name in CLUBS:
            team = teams[club_name]
            for p, player in enumerate(self._players_for(people, club_name), start=1):
                for week in range(6):
                    PlayerWeeklySkillMetric.objects.update_or_create(
                        player=player, team=team, week_start=monday + timedelta(weeks=week),
                        defaults={"attack": Decimal(str(60 + p * 3 + week * 2)), "defense": Decimal(str(62 + p * 2 + week * 2)), "serve": Decimal(str(58 + p * 4 + week))},
                    )

    def _seed_fees_and_audit(self, people, clubs, teams):
        month_start = date(timezone.localdate().year, timezone.localdate().month, 1)
        for club_name in CLUBS:
            club = clubs[club_name]
            team = teams[club_name]
            schedule, _ = PaymentSchedule.objects.update_or_create(
                club=club, team=team, player=None, description=f"{club_name} monthly team dues",
                defaults={"scope": PaymentSchedule.Scope.TEAM, "frequency": PaymentSchedule.Frequency.MONTHLY, "amount": Decimal("85.00"), "currency": "USD", "start_date": month_start, "is_active": True, "created_by": people["tayma"]},
            )
            for i, player in enumerate(self._players_for(people, club_name), start=1):
                due = Decimal("85.00") + Decimal(str(i * 5))
                paid = due if i == 1 else (due / Decimal("2"))
                fee, _ = PlayerFeeRecord.objects.update_or_create(
                    club=club, player=player, team=team, billing_period_start=month_start,
                    defaults={"schedule": schedule, "description": f"{club_name} dues for {team.name}", "amount_due": due, "amount_paid": paid, "currency": "USD", "due_date": month_start + timedelta(days=10 + i), "schedule_occurrence_key": f"{schedule.id}:{player.id}:{month_start.isoformat()}"},
                )
                FeePaymentLedgerEntry.objects.filter(fee_record=fee).delete()
                FeePaymentLedgerEntry.objects.create(fee_record=fee, amount=paid, note="QA seed payment")
                DirectorPaymentAuditLog.objects.get_or_create(club=club, actor=people["tayma"], action=DirectorPaymentAuditLog.Action.FEE_CREATED, detail=f"QA seed fee created for {player.email}", fee_record=fee)
                DirectorPaymentAuditLog.objects.get_or_create(club=club, actor=people["tayma"], action=DirectorPaymentAuditLog.Action.PAYMENT_RECORDED, detail=f"QA seed payment recorded for {player.email}", fee_record=fee)

    def _seed_notifications(self, people, teams, sessions):
        for club_name in CLUBS:
            team = teams[club_name]
            payload = sessions[club_name]
            Notification.objects.get_or_create(recipient=payload["coach"], team=team, training_session=payload["now"], category=Notification.Category.SESSION, title=f"{club_name} session reminder", message="Please verify attendance before session start.", created_by=people["tayma"])
            Notification.objects.get_or_create(recipient=people["tayma"], team=team, training_session=payload["now"], category=Notification.Category.ATTENDANCE_INCOMPLETE, title=f"{club_name} attendance follow-up", message="Some confirmations are still pending.", created_by=payload["coach"])
            for player in payload["players"]:
                Notification.objects.get_or_create(recipient=player, team=team, category=Notification.Category.MANUAL, title=f"{club_name} dashboard updated", message="Your sessions, fees, and progress are refreshed.", created_by=payload["coach"])

    def _seed_tournament(self, creator, club, teams):
        tournament, _ = Tournament.objects.get_or_create(
            club=club, name="QA Hybrid Tournament",
            defaults={"created_by": creator, "tournament_type": Tournament.TournamentType.HYBRID, "number_of_teams": len(teams), "pool_count": 2, "teams_per_pool": 2, "teams_qualifying_per_pool": 1, "match_duration_minutes": 90, "scoring_format": "Best of 5 to 25", "start_date": timezone.localdate() + timedelta(days=7), "venue": "Beirut Central Arena"},
        )
        tournament.status = Tournament.Status.GENERATED
        tournament.save(update_fields=["status"])
        tournament.teams.set(list(teams.values()))
        return tournament

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.core.models import (
    CoachFeedbackStatus,
    Club,
    ClubMembership,
    DirectorPaymentAuditLog,
    FeePaymentLedgerEntry,
    MatchPlayerStat,
    Notification,
    ParentPlayerRelation,
    PaymentSchedule,
    PlayerFeeRecord,
    PlayerProfile,
    PlayerWeeklySkillMetric,
    Team,
    TeamCoachFeedback,
    TeamMembership,
    TeamRole,
    TeamRosterPlayerStat,
    TeamScheduleEntry,
    TeamSkillCategory,
    TeamSkillDashboardMetric,
    Tournament,
    TrainingSession,
    TrainingSessionConfirmation,
    VerificationStatus,
)

User = get_user_model()
SEED_PASSWORD = "test123"
PEOPLE = ("tayma", "karma", "lyn", "nay", "racha", "farouk")
CLUBS = ("AUB", "CPF", "NAHDA", "RIYADI")
TEAM_NAMES = {"AUB": "AUB Spikers", "CPF": "CPF Chargers", "NAHDA": "NAHDA Eagles", "RIYADI": "RIYADI Warriors"}


class Command(BaseCommand):
    help = "Seed realistic QA data for clubs, teams, sessions, dashboard, fees, and tournament testing."

    def add_arguments(self, parser):
        parser.add_argument("--with-tournament", action="store_true")

    def handle(self, *args, **options):
        with transaction.atomic():
            people = self._seed_people()
            clubs = self._seed_clubs(people["tayma"])
            teams = self._seed_teams(clubs)
            self._seed_memberships(people, clubs, teams)
            self._seed_profiles_and_parent_links(people)
            sessions = self._seed_schedule_and_sessions(people, teams)
            self._seed_confirmations_and_stats(people, sessions)
            self._seed_dashboard_rows(people, teams)
            self._seed_progress_rows(people, teams)
            self._seed_fees_and_audit(people, clubs, teams)
            self._seed_notifications(people, teams, sessions)
            tournament = self._seed_tournament(people["tayma"], clubs["AUB"], teams) if options["with_tournament"] else None

        self.stdout.write(self.style.SUCCESS("QA seed completed successfully."))
        self.stdout.write(self.style.SUCCESS(f"Clubs: {', '.join(CLUBS)}"))
        self.stdout.write(self.style.SUCCESS("Users: tayma, karma, lyn, nay, racha, farouk"))
        self.stdout.write(self.style.SUCCESS(f"Password for all seeded users: {SEED_PASSWORD}"))
        if tournament:
            self.stdout.write(self.style.SUCCESS(f"Tournament: {tournament.name} (id={tournament.id})"))

    def _seed_people(self):
        role_dob = {"tayma": date(1988, 7, 14), "lyn": date(1994, 3, 18), "farouk": date(1992, 11, 30)}
        people = {}
        for name in PEOPLE:
            user, _ = User.objects.get_or_create(
                email=f"{name}@qa.seed.local",
                defaults={
                    "first_name": name.capitalize(),
                    "last_name": "QA",
                    "date_of_birth": role_dob.get(name, date(2008, 9, 12)),
                    "verification_status": VerificationStatus.VERIFIED,
                },
            )
            user.first_name = name.capitalize()
            user.last_name = "QA"
            user.verification_status = VerificationStatus.VERIFIED
            user.set_password(SEED_PASSWORD)
            user.save(update_fields=["first_name", "last_name", "verification_status", "password"])
            people[name] = user
        return people

    def _seed_clubs(self, director):
        clubs = {}
        for idx, name in enumerate(CLUBS):
            club = Club.objects.filter(name=name).first()
            if club is None:
                club = Club.objects.create_club(name=name, director=director)
            club.short_name = name
            club.description = f"{name} volleyball QA club"
            club.city = "Beirut"
            club.country = "Lebanon"
            club.founded_year = 1990 + idx
            club.default_monthly_player_fee = Decimal(str(70 + (idx * 5)))
            club.save()
            ClubMembership.objects.assign_director(user=director, club=club)
            clubs[name] = club
        return clubs

    def _seed_teams(self, clubs):
        teams = {}
        for idx, club_name in enumerate(CLUBS):
            team, _ = Team.objects.get_or_create(club=clubs[club_name], name=TEAM_NAMES[club_name])
            team.season = "2025-26"
            team.age_group = f"U{17 + idx}"
            team.gender = Team.Gender.MIXED
            team.status = Team.Status.ACTIVE
            team.home_venue = f"{club_name} Arena"
            team.description = f"{club_name} first roster for QA."
            team.save()
            teams[club_name] = team
        return teams

    def _seed_memberships(self, people, clubs, teams):
        for club in clubs.values():
            ClubMembership.objects.assign_director(user=people["tayma"], club=club)
        TeamMembership.objects.add_member(user=people["lyn"], team=teams["AUB"], role=TeamRole.COACH)
        TeamMembership.objects.add_member(user=people["lyn"], team=teams["NAHDA"], role=TeamRole.COACH)
        TeamMembership.objects.add_member(user=people["farouk"], team=teams["CPF"], role=TeamRole.COACH)
        TeamMembership.objects.add_member(user=people["farouk"], team=teams["RIYADI"], role=TeamRole.COACH)
        TeamMembership.objects.add_member(user=people["karma"], team=teams["AUB"], role=TeamRole.PLAYER, is_captain=True)
        TeamMembership.objects.add_member(user=people["karma"], team=teams["CPF"], role=TeamRole.PLAYER)
        TeamMembership.objects.add_member(user=people["nay"], team=teams["NAHDA"], role=TeamRole.PLAYER)
        TeamMembership.objects.add_member(user=people["nay"], team=teams["RIYADI"], role=TeamRole.PLAYER)
        TeamMembership.objects.add_member(user=people["racha"], team=teams["CPF"], role=TeamRole.PLAYER)
        TeamMembership.objects.add_member(user=people["racha"], team=teams["RIYADI"], role=TeamRole.PLAYER, is_captain=True)

    def _seed_profiles_and_parent_links(self, people):
        PlayerProfile.objects.update_or_create(user=people["karma"], defaults={"jersey_number": 7, "primary_position": "Setter"})
        PlayerProfile.objects.update_or_create(user=people["nay"], defaults={"jersey_number": 11, "primary_position": "Libero"})
        PlayerProfile.objects.update_or_create(user=people["racha"], defaults={"jersey_number": 4, "primary_position": "Outside Hitter"})
        for child in ("karma", "nay", "racha"):
            ParentPlayerRelation.objects.link(parent=people["tayma"], player=people[child], is_legal_guardian=True)

    def _players_for(self, people, club_name):
        return {
            "AUB": [people["karma"], people["racha"]],
            "CPF": [people["karma"], people["racha"]],
            "NAHDA": [people["nay"], people["karma"]],
            "RIYADI": [people["nay"], people["racha"]],
        }[club_name]

    def _seed_schedule_and_sessions(self, people, teams):
        today = timezone.localdate()
        sessions = {}
        for idx, club_name in enumerate(CLUBS):
            team = teams[club_name]
            coach = people["lyn"] if club_name in ("AUB", "NAHDA") else people["farouk"]
            TeamScheduleEntry.objects.update_or_create(
                team=team, activity_name="Technical Training", weekday=(idx + 1),
                defaults={"start_time": time(18, 0), "end_time": time(19, 30), "location": team.home_venue, "created_by": coach},
            )
            past, _ = TrainingSession.objects.get_or_create(team=team, title=f"{club_name} Ball Control", scheduled_date=today - timedelta(days=9 + idx),
                defaults={"session_type": TrainingSession.SessionType.TRAINING, "start_time": time(18, 0), "end_time": time(19, 30), "location": team.home_venue, "created_by": coach})
            now, _ = TrainingSession.objects.get_or_create(team=team, title=f"{club_name} Practice Today", scheduled_date=today,
                defaults={"session_type": TrainingSession.SessionType.TRAINING, "start_time": time(18, 30), "end_time": time(20, 0), "location": team.home_venue, "created_by": coach})
            match, _ = TrainingSession.objects.get_or_create(team=team, title=f"{club_name} League Match", scheduled_date=today + timedelta(days=4 + idx),
                defaults={"session_type": TrainingSession.SessionType.MATCH, "start_time": time(19, 0), "end_time": time(21, 0), "location": team.home_venue, "opponent": "City Rivals", "match_type": TrainingSession.MatchType.LEAGUE, "created_by": coach})
            sessions[club_name] = {"coach": coach, "players": self._players_for(people, club_name), "past": past, "now": now, "match": match}
        return sessions

    def _seed_confirmations_and_stats(self, people, sessions):
        for club_name in CLUBS:
            payload = sessions[club_name]
            for i, player in enumerate(payload["players"], start=1):
                TrainingSessionConfirmation.objects.update_or_create(training_session=payload["now"], player=player, defaults={"confirmed_by": player})
                if i % 2 == 1:
                    TrainingSessionConfirmation.objects.update_or_create(training_session=payload["past"], player=player, defaults={"confirmed_by": people["tayma"]})
                MatchPlayerStat.objects.update_or_create(
                    training_session=payload["match"], player=player,
                    defaults={"points_scored": 8 + i * 2, "aces": i, "blocks": i, "assists": 3 + i, "errors": i % 2, "digs": 5 + i, "updated_by": payload["coach"]},
                )

    def _seed_dashboard_rows(self, people, teams):
        skill_defaults = [
            (TeamSkillCategory.ATTACK, Decimal("78.00"), Decimal("74.00")),
            (TeamSkillCategory.DEFENSE, Decimal("82.00"), Decimal("79.00")),
            (TeamSkillCategory.SERVE, Decimal("75.00"), Decimal("77.00")),
            (TeamSkillCategory.BLOCK, Decimal("69.00"), Decimal("72.00")),
        ]
        for club_name in CLUBS:
            team = teams[club_name]
            coach = people["lyn"] if club_name in ("AUB", "NAHDA") else people["farouk"]
            players = self._players_for(people, club_name)
            for skill, attendance, performance in skill_defaults:
                TeamSkillDashboardMetric.objects.update_or_create(team=team, skill_category=skill, defaults={"attendance_rate": attendance, "average_performance": performance})
            for i, player in enumerate(players, start=1):
                TeamRosterPlayerStat.objects.update_or_create(team=team, player=player, defaults={"spikes": 6 + i, "blocks": 1 + i, "serve_percentage": Decimal(str(70 + i * 4)), "prior_serve_percentage": Decimal(str(66 + i * 3))})
                TeamCoachFeedback.objects.update_or_create(
                    team=team, player=player, coach=coach,
                    body=f"{player.first_name} should improve transition timing and communication.",
                    defaults={"status": CoachFeedbackStatus.PENDING if i % 2 == 0 else CoachFeedbackStatus.ADDRESSED},
                )

    def _seed_progress_rows(self, people, teams):
        today = timezone.localdate()
        monday = today - timedelta(days=today.weekday()) - timedelta(weeks=5)
        for club_name in CLUBS:
            team = teams[club_name]
            for p, player in enumerate(self._players_for(people, club_name), start=1):
                for week in range(6):
                    PlayerWeeklySkillMetric.objects.update_or_create(
                        player=player, team=team, week_start=monday + timedelta(weeks=week),
                        defaults={"attack": Decimal(str(60 + p * 3 + week * 2)), "defense": Decimal(str(62 + p * 2 + week * 2)), "serve": Decimal(str(58 + p * 4 + week))},
                    )

    def _seed_fees_and_audit(self, people, clubs, teams):
        month_start = date(timezone.localdate().year, timezone.localdate().month, 1)
        for club_name in CLUBS:
            club = clubs[club_name]
            team = teams[club_name]
            schedule, _ = PaymentSchedule.objects.update_or_create(
                club=club, team=team, player=None, description=f"{club_name} monthly team dues",
                defaults={"scope": PaymentSchedule.Scope.TEAM, "frequency": PaymentSchedule.Frequency.MONTHLY, "amount": Decimal("85.00"), "currency": "USD", "start_date": month_start, "is_active": True, "created_by": people["tayma"]},
            )
            for i, player in enumerate(self._players_for(people, club_name), start=1):
                due = Decimal("85.00") + Decimal(str(i * 5))
                paid = due if i == 1 else (due / Decimal("2"))
                fee, _ = PlayerFeeRecord.objects.update_or_create(
                    club=club, player=player, team=team, billing_period_start=month_start,
                    defaults={"schedule": schedule, "description": f"{club_name} dues for {team.name}", "amount_due": due, "amount_paid": paid, "currency": "USD", "due_date": month_start + timedelta(days=10 + i), "schedule_occurrence_key": f"{schedule.id}:{player.id}:{month_start.isoformat()}"},
                )
                FeePaymentLedgerEntry.objects.filter(fee_record=fee).delete()
                FeePaymentLedgerEntry.objects.create(fee_record=fee, amount=paid, note="QA seed payment")
                DirectorPaymentAuditLog.objects.get_or_create(club=club, actor=people["tayma"], action=DirectorPaymentAuditLog.Action.FEE_CREATED, detail=f"QA seed fee created for {player.email}", fee_record=fee)
                DirectorPaymentAuditLog.objects.get_or_create(club=club, actor=people["tayma"], action=DirectorPaymentAuditLog.Action.PAYMENT_RECORDED, detail=f"QA seed payment recorded for {player.email}", fee_record=fee)

    def _seed_notifications(self, people, teams, sessions):
        for club_name in CLUBS:
            team = teams[club_name]
            payload = sessions[club_name]
            Notification.objects.get_or_create(recipient=payload["coach"], team=team, training_session=payload["now"], category=Notification.Category.SESSION, title=f"{club_name} session reminder", message="Please verify attendance before session start.", created_by=people["tayma"])
            Notification.objects.get_or_create(recipient=people["tayma"], team=team, training_session=payload["now"], category=Notification.Category.ATTENDANCE_INCOMPLETE, title=f"{club_name} attendance follow-up", message="Some confirmations are still pending.", created_by=payload["coach"])
            for player in payload["players"]:
                Notification.objects.get_or_create(recipient=player, team=team, category=Notification.Category.MANUAL, title=f"{club_name} dashboard updated", message="Your sessions, fees, and progress are refreshed.", created_by=payload["coach"])

    def _seed_tournament(self, creator, club, teams):
        tournament, _ = Tournament.objects.get_or_create(
            club=club, name="QA Hybrid Tournament",
            defaults={"created_by": creator, "tournament_type": Tournament.TournamentType.HYBRID, "number_of_teams": len(teams), "pool_count": 2, "teams_per_pool": 2, "teams_qualifying_per_pool": 1, "match_duration_minutes": 90, "scoring_format": "Best of 5 to 25", "start_date": timezone.localdate() + timedelta(days=7), "venue": "Beirut Central Arena"},
        )
        tournament.status = Tournament.Status.GENERATED
        tournament.save(update_fields=["status"])
        tournament.teams.set(list(teams.values()))
        return tournament
from datetime import date

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.core.models import (
    Club,
    ClubMembership,
    Team,
    TeamMembership,
    TeamRole,
    Tournament,
    VerificationStatus,
)

User = get_user_model()

SEED_PASSWORD = "test123"
SEED_CLUB_NAME = "Tournament Test Club"


class Command(BaseCommand):
    help = "Seed a clean tournament-testing dataset with requested names and teams."

    def add_arguments(self, parser):
        parser.add_argument(
            "--with-tournament",
            action="store_true",
            help="Also create one sample hybrid tournament using all four teams.",
        )

    def handle(self, *args, **options):
        with_tournament = options["with_tournament"]
        with transaction.atomic():
            people = self._seed_people()
            club = self._seed_club(people["tayma"])
            teams = self._seed_teams(club)
            self._seed_memberships(people, club, teams)

            tournament = None
            if with_tournament:
                tournament = self._seed_sample_tournament(club, people["tayma"], teams)

        self.stdout.write(self.style.SUCCESS("Tournament test seed completed."))
        self.stdout.write(
            self.style.SUCCESS(
                f"Club: {SEED_CLUB_NAME} | Teams: cpf, aub, nahda, riyadi | Password for all seeded users: {SEED_PASSWORD}"
            )
        )
        self.stdout.write(
            "Users: tayma, lyn, karma, nay, racha, farouk (emails end with @seed.local)."
        )
        if tournament is not None:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Sample tournament created: {tournament.name} (id={tournament.id}, type=hybrid)."
                )
            )
        else:
            self.stdout.write("No tournament was pre-created. Use the UI to create one and test scheduling generation.")

    def _ensure_user(self, *, name: str):
        email = f"{name.lower()}@seed.local"
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "first_name": name.capitalize(),
                "last_name": "Seed",
                "verification_status": VerificationStatus.VERIFIED,
                "date_of_birth": date(2000, 1, 1),
            },
        )
        if not created:
            user.first_name = name.capitalize()
            user.last_name = "Seed"
            user.verification_status = VerificationStatus.VERIFIED
            if user.date_of_birth is None:
                user.date_of_birth = date(2000, 1, 1)
            user.save(
                update_fields=[
                    "first_name",
                    "last_name",
                    "verification_status",
                    "date_of_birth",
                ]
            )
        user.set_password(SEED_PASSWORD)
        user.save(update_fields=["password"])
        return user

    def _seed_people(self):
        names = ("tayma", "lyn", "karma", "nay", "racha", "farouk")
        return {name: self._ensure_user(name=name) for name in names}

    def _seed_club(self, director):
        club = Club.objects.filter(name=SEED_CLUB_NAME).first()
        if club is None:
            club = Club.objects.create_club(
                name=SEED_CLUB_NAME,
                director=director,
                short_name="TTS",
                description="Sandbox club for tournament scheduling tests.",
                city="Beirut",
                country="Lebanon",
            )
        else:
            club.short_name = "TTS"
            club.description = "Sandbox club for tournament scheduling tests."
            club.city = "Beirut"
            club.country = "Lebanon"
            club.save(update_fields=["short_name", "description", "city", "country"])
            ClubMembership.objects.assign_director(user=director, club=club)
        return club

    def _seed_teams(self, club):
        team_names = ("cpf", "aub", "nahda", "riyadi")
        teams = {}
        for team_name in team_names:
            team, _ = Team.objects.get_or_create(
                club=club,
                name=team_name,
                defaults={
                    "description": "Seeded team for tournament tests.",
                    "season": "2025-26",
                    "age_group": "U18",
                    "gender": Team.Gender.MIXED,
                    "status": Team.Status.ACTIVE,
                    "home_venue": "Main Court",
                },
            )
            team.description = "Seeded team for tournament tests."
            team.season = "2025-26"
            team.age_group = "U18"
            team.gender = Team.Gender.MIXED
            team.status = Team.Status.ACTIVE
            team.home_venue = "Main Court"
            team.save(
                update_fields=["description", "season", "age_group", "gender", "status", "home_venue"]
            )
            teams[team_name] = team
        return teams

    def _seed_memberships(self, people, club, teams):
        ClubMembership.objects.assign_director(user=people["tayma"], club=club)

        TeamMembership.objects.add_member(user=people["lyn"], team=teams["cpf"], role=TeamRole.COACH)
        TeamMembership.objects.add_member(user=people["farouk"], team=teams["aub"], role=TeamRole.COACH)

        TeamMembership.objects.add_member(user=people["karma"], team=teams["cpf"], role=TeamRole.PLAYER)
        TeamMembership.objects.add_member(user=people["nay"], team=teams["nahda"], role=TeamRole.PLAYER)
        TeamMembership.objects.add_member(user=people["racha"], team=teams["riyadi"], role=TeamRole.PLAYER)

    def _seed_sample_tournament(self, club, creator, teams):
        active = Tournament.objects.filter(club=club, status=Tournament.Status.GENERATED).first()
        if active:
            return active

        tournament = Tournament.objects.create(
            club=club,
            created_by=creator,
            name="Seeded Hybrid Tournament",
            tournament_type=Tournament.TournamentType.HYBRID,
            number_of_teams=4,
            pool_count=2,
            teams_per_pool=2,
            teams_qualifying_per_pool=1,
            match_duration_minutes=90,
            scoring_format="Best of 3 to 25",
            start_date=date.today(),
            venue="Tournament Test Venue",
        )
        tournament.teams.set([teams["cpf"], teams["aub"], teams["nahda"], teams["riyadi"]])
        return tournament
