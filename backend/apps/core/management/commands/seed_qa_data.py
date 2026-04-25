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
PRIMARY_PEOPLE = ("tayma", "karma", "lyn", "nay", "racha", "farouk")
CLUB_NAMES = ("AUB", "CPF", "NAHDA", "RIYADI")

TEAM_BLUEPRINTS = (
    {"club": "AUB", "name": "AUB Falcons", "age_group": "U19", "home_venue": "AUB Main Court", "coach_alias": "lyn", "captain_alias": "karma"},
    {"club": "AUB", "name": "AUB Waves", "age_group": "U17", "home_venue": "AUB Training Hall", "coach_alias": "coach_aub_2", "captain_alias": "aida"},
    {"club": "AUB", "name": "AUB Storm", "age_group": "U18", "home_venue": "AUB East Court", "coach_alias": "lyn", "captain_alias": "rana"},
    {"club": "AUB", "name": "AUB Panthers", "age_group": "U16", "home_venue": "AUB West Court", "coach_alias": "coach_aub_2", "captain_alias": "maya"},
    {"club": "CPF", "name": "CPF Titans", "age_group": "U20", "home_venue": "CPF Sports Arena", "coach_alias": "farouk", "captain_alias": "racha"},
    {"club": "CPF", "name": "CPF Chargers", "age_group": "U18", "home_venue": "CPF Practice Court", "coach_alias": "coach_cpf_2", "captain_alias": "nour"},
    {"club": "CPF", "name": "CPF Blazers", "age_group": "U19", "home_venue": "CPF Arena B", "coach_alias": "farouk", "captain_alias": "tina"},
    {"club": "CPF", "name": "CPF Lightning", "age_group": "U17", "home_venue": "CPF Court C", "coach_alias": "coach_cpf_2", "captain_alias": "karim"},
    {"club": "NAHDA", "name": "NAHDA Eagles", "age_group": "U18", "home_venue": "Nahda Arena", "coach_alias": "coach_nahda_1", "captain_alias": "nay"},
    {"club": "NAHDA", "name": "NAHDA Rockets", "age_group": "U16", "home_venue": "Nahda Development Hall", "coach_alias": "coach_nahda_2", "captain_alias": "zeina"},
    {"club": "NAHDA", "name": "NAHDA Phoenix", "age_group": "U17", "home_venue": "Nahda Court B", "coach_alias": "coach_nahda_1", "captain_alias": "joelle"},
    {"club": "NAHDA", "name": "NAHDA Wolves", "age_group": "U15", "home_venue": "Nahda Court C", "coach_alias": "coach_nahda_2", "captain_alias": "sara"},
    {"club": "RIYADI", "name": "RIYADI Warriors", "age_group": "U19", "home_venue": "Riyadi Arena", "coach_alias": "coach_riyadi_1", "captain_alias": "fadi"},
    {"club": "RIYADI", "name": "RIYADI Storm", "age_group": "U17", "home_venue": "Riyadi Secondary Court", "coach_alias": "coach_riyadi_2", "captain_alias": "hadi"},
    {"club": "RIYADI", "name": "RIYADI Hawks", "age_group": "U18", "home_venue": "Riyadi Court B", "coach_alias": "coach_riyadi_1", "captain_alias": "omar"},
    {"club": "RIYADI", "name": "RIYADI Falcons", "age_group": "U16", "home_venue": "Riyadi Court C", "coach_alias": "coach_riyadi_2", "captain_alias": "ali"},
)

PLAYER_ALIASES = (
    "karma",
    "nay",
    "racha",
    "aida",
    "nour",
    "zeina",
    "fadi",
    "hadi",
    "rana",
    "maya",
    "jad",
    "yara",
    "omar",
    "sara",
    "ali",
    "lea",
    "tina",
    "karim",
    "joelle",
    "elie",
    "sam",
    "rita",
    "mira",
    "ziad",
)

COACH_ALIASES = (
    "lyn",
    "farouk",
    "coach_aub_2",
    "coach_cpf_2",
    "coach_nahda_1",
    "coach_nahda_2",
    "coach_riyadi_1",
    "coach_riyadi_2",
)

TEAM_ROSTERS = {
    "AUB Falcons": ("karma", "nay", "aida", "rana", "jad", "ali", "lea", "sam"),
    "AUB Waves": ("aida", "maya", "yara", "sara", "joelle", "elie", "rita", "mira"),
    "AUB Storm": ("rana", "maya", "jad", "sara", "ali", "karim", "mira", "ziad"),
    "AUB Panthers": ("maya", "aida", "lea", "rita", "joelle", "sam", "yara", "elie"),
    "CPF Titans": ("racha", "nour", "fadi", "hadi", "karim", "omar", "zeina", "ziad"),
    "CPF Chargers": ("nour", "tina", "maya", "ali", "lea", "sam", "rita", "yara"),
    "CPF Blazers": ("tina", "nour", "karim", "hadi", "fadi", "omar", "mira", "zeina"),
    "CPF Lightning": ("karim", "tina", "yara", "sara", "rita", "lea", "jad", "ali"),
    "NAHDA Eagles": ("nay", "aida", "hadi", "sara", "mira", "zeina", "jad", "joelle"),
    "NAHDA Rockets": ("zeina", "maya", "tina", "rana", "lea", "eliE".lower(), "omar", "karim"),
    "NAHDA Phoenix": ("joelle", "nay", "aida", "mira", "jad", "rita", "yara", "sam"),
    "NAHDA Wolves": ("sara", "joelle", "maya", "zeina", "rana", "lea", "karim", "elie"),
    "RIYADI Warriors": ("fadi", "racha", "hadi", "omar", "ali", "ziad", "karim", "sam"),
    "RIYADI Storm": ("hadi", "yara", "sara", "tina", "mira", "rita", "joelle", "elie"),
    "RIYADI Hawks": ("omar", "fadi", "ali", "ziad", "karim", "nay", "racha", "sam"),
    "RIYADI Falcons": ("ali", "hadi", "yara", "sara", "rita", "lea", "mira", "elie"),
}

PLAYER_POSITIONS = ("Setter", "Outside Hitter", "Middle Blocker", "Opposite", "Libero")


class Command(BaseCommand):
    help = "Seed a max realistic QA dataset focused on tournament testing."

    def add_arguments(self, parser):
        parser.add_argument("--with-tournament", action="store_true", help="Create tournament with all seeded teams.")

    def handle(self, *args, **options):
        with transaction.atomic():
            users = self._seed_users()
            clubs = self._seed_clubs(users["tayma"])
            teams = self._seed_teams(clubs)
            self._seed_memberships(users, clubs, teams)
            self._seed_profiles(users)
            self._seed_parent_links(users)
            sessions = self._seed_schedules_and_sessions(users, teams)
            self._seed_confirmations_and_match_stats(users, sessions)
            self._seed_notifications(users, sessions)
            tournament = None
            if options["with_tournament"]:
                tournament = self._seed_tournament(users["tayma"], clubs["AUB"], teams)

        self.stdout.write(self.style.SUCCESS("Max QA seed completed successfully."))
        self.stdout.write(self.style.SUCCESS("Core users: tayma, karma, lyn, nay, racha, farouk"))
        self.stdout.write(self.style.SUCCESS("Clubs: AUB, CPF, NAHDA, RIYADI"))
        self.stdout.write(self.style.SUCCESS(f"Teams seeded: {len(teams)} | Password: {SEED_PASSWORD}"))
        if tournament:
            self.stdout.write(self.style.SUCCESS(f"Tournament seeded: {tournament.name}"))

    def _seed_users(self):
        users = {}
        base_birth = date(2008, 2, 14)

        all_aliases = list(dict.fromkeys(PRIMARY_PEOPLE + PLAYER_ALIASES + COACH_ALIASES))
        for idx, alias in enumerate(all_aliases):
            first_name = alias.replace("_", " ").title().split()[0]
            role_year = 1992 if alias.startswith("coach_") or alias in ("lyn", "farouk") else 2008
            birth_date = date(role_year, ((idx % 11) + 1), ((idx % 25) + 1))
            if alias == "tayma":
                birth_date = date(1988, 7, 14)
            user, _ = User.objects.get_or_create(
                email=f"{alias}@qa.seed.local",
                defaults={
                    "first_name": first_name,
                    "last_name": "QA",
                    "date_of_birth": birth_date or base_birth,
                    "verification_status": VerificationStatus.VERIFIED,
                },
            )
            user.first_name = first_name
            user.last_name = "QA"
            user.date_of_birth = birth_date
            user.verification_status = VerificationStatus.VERIFIED
            user.set_password(SEED_PASSWORD)
            user.save(
                update_fields=["first_name", "last_name", "date_of_birth", "verification_status", "password"]
            )
            users[alias] = user
        return users

    def _seed_clubs(self, director):
        clubs = {}
        for idx, name in enumerate(CLUB_NAMES):
            club = Club.objects.filter(name=name).first()
            if club is None:
                club = Club.objects.create_club(name=name, director=director)
            club.short_name = name
            club.description = f"{name} volleyball club seeded for realistic QA."
            club.city = "Beirut"
            club.country = "Lebanon"
            club.default_monthly_player_fee = Decimal(str(75 + idx * 10))
            club.save()
            ClubMembership.objects.assign_director(user=director, club=club)
            clubs[name] = club
        return clubs

    def _seed_teams(self, clubs):
        teams = {}
        for blueprint in TEAM_BLUEPRINTS:
            team, _ = Team.objects.get_or_create(club=clubs[blueprint["club"]], name=blueprint["name"])
            team.season = "2025-26"
            team.age_group = blueprint["age_group"]
            team.gender = Team.Gender.MIXED
            team.status = Team.Status.ACTIVE
            team.home_venue = blueprint["home_venue"]
            team.description = f"{blueprint['name']} seeded for tournament stress testing."
            team.short_name = blueprint["club"]
            team.save()
            teams[blueprint["name"]] = team
        return teams

    def _seed_memberships(self, users, clubs, teams):
        for club in clubs.values():
            ClubMembership.objects.assign_director(user=users["tayma"], club=club)

        for blueprint in TEAM_BLUEPRINTS:
            team_name = blueprint["name"]
            team = teams[team_name]
            coach = users[blueprint["coach_alias"]]
            TeamMembership.objects.add_member(user=coach, team=team, role=TeamRole.COACH)

            captain_alias = blueprint["captain_alias"]
            for alias in TEAM_ROSTERS[team_name]:
                TeamMembership.objects.add_member(
                    user=users[alias],
                    team=team,
                    role=TeamRole.PLAYER,
                    is_captain=(alias == captain_alias),
                )

    def _seed_profiles(self, users):
        player_aliases = [alias for alias in PLAYER_ALIASES if alias in users]
        for idx, alias in enumerate(player_aliases):
            PlayerProfile.objects.update_or_create(
                user=users[alias],
                defaults={
                    "jersey_number": (idx % 18) + 1,
                    "primary_position": PLAYER_POSITIONS[idx % len(PLAYER_POSITIONS)],
                    "notes": "QA seeded player profile.",
                },
            )

    def _seed_parent_links(self, users):
        for child in ("karma", "nay", "racha", "aida", "nour"):
            ParentPlayerRelation.objects.link(
                parent=users["tayma"],
                player=users[child],
                is_legal_guardian=True,
            )

    def _seed_schedules_and_sessions(self, users, teams):
        sessions = {}
        today = timezone.localdate()
        team_names = list(teams.keys())

        for idx, team_name in enumerate(team_names):
            team = teams[team_name]
            coach_membership = TeamMembership.objects.filter(team=team, role=TeamRole.COACH, is_active=True).first()
            coach = coach_membership.user if coach_membership else users["lyn"]

            TeamScheduleEntry.objects.update_or_create(
                team=team,
                activity_name="Technical Training",
                weekday=(idx % 5),
                defaults={
                    "start_time": time(18, 0),
                    "end_time": time(19, 30),
                    "location": team.home_venue,
                    "created_by": coach,
                },
            )
            TeamScheduleEntry.objects.update_or_create(
                team=team,
                activity_name="Physical Conditioning",
                weekday=((idx + 2) % 6),
                defaults={
                    "start_time": time(17, 30),
                    "end_time": time(18, 45),
                    "location": f"{team.home_venue} Gym",
                    "created_by": coach,
                },
            )

            past_training, _ = TrainingSession.objects.get_or_create(
                team=team,
                title=f"{team.name} Tactical Session",
                scheduled_date=today - timedelta(days=7 + idx),
                defaults={
                    "session_type": TrainingSession.SessionType.TRAINING,
                    "start_time": time(18, 0),
                    "end_time": time(19, 30),
                    "location": team.home_venue,
                    "created_by": coach,
                },
            )

            opponent_team = teams[team_names[(idx + 1) % len(team_names)]]
            match_day = today + timedelta(days=5 + idx)
            league_match, _ = TrainingSession.objects.get_or_create(
                team=team,
                title=f"{team.name} vs {opponent_team.name}",
                scheduled_date=match_day,
                defaults={
                    "session_type": TrainingSession.SessionType.MATCH,
                    "start_time": time(19, 0),
                    "end_time": time(21, 0),
                    "location": team.home_venue,
                    "opponent": opponent_team.name,
                    "opponent_team": opponent_team,
                    "match_type": TrainingSession.MatchType.LEAGUE,
                    "created_by": coach,
                },
            )

            player_ids = list(
                TeamMembership.objects.filter(team=team, role=TeamRole.PLAYER, is_active=True).values_list("user_id", flat=True)
            )
            sessions[team_name] = {
                "team": team,
                "coach": coach,
                "past_training": past_training,
                "league_match": league_match,
                "player_ids": player_ids,
            }
        return sessions

    def _seed_confirmations_and_match_stats(self, users, sessions):
        for payload in sessions.values():
            for idx, player_id in enumerate(payload["player_ids"], start=1):
                player = User.objects.get(pk=player_id)
                TrainingSessionConfirmation.objects.update_or_create(
                    training_session=payload["past_training"],
                    player=player,
                    defaults={"confirmed_by": users["tayma"] if idx % 3 == 0 else player},
                )
                MatchPlayerStat.objects.update_or_create(
                    training_session=payload["league_match"],
                    player=player,
                    defaults={
                        "points_scored": 6 + idx * 2,
                        "aces": idx % 4,
                        "blocks": idx % 5,
                        "assists": 2 + (idx % 6),
                        "errors": idx % 3,
                        "digs": 3 + (idx % 7),
                        "updated_by": payload["coach"],
                    },
                )

    def _seed_notifications(self, users, sessions):
        for team_name, payload in sessions.items():
            Notification.objects.get_or_create(
                recipient=payload["coach"],
                team=payload["team"],
                training_session=payload["past_training"],
                category=Notification.Category.SESSION,
                title=f"{team_name} attendance check",
                message="Review confirmations and follow up on missing players.",
            )
            Notification.objects.get_or_create(
                recipient=users["tayma"],
                team=payload["team"],
                training_session=payload["past_training"],
                category=Notification.Category.ATTENDANCE_INCOMPLETE,
                title=f"{team_name} attendance follow-up",
                message="One or more players still need attendance verification.",
                created_by=payload["coach"],
            )

    def _seed_tournament(self, creator, club, teams):
        team_list = [team for team in teams.values() if team.club_id == club.id]
        tournament, _ = Tournament.objects.get_or_create(
            club=club,
            name="QA Championship 2025",
            defaults={
                "created_by": creator,
                "tournament_type": Tournament.TournamentType.HYBRID,
                "number_of_teams": len(team_list),
                "pool_count": 2,
                "teams_per_pool": len(team_list) // 2,
                "teams_qualifying_per_pool": 2,
                "match_duration_minutes": 90,
                "scoring_format": "Best of 5 to 25",
                "start_date": timezone.localdate() + timedelta(days=10),
                "venue": "Beirut Central Arena",
            },
        )
        tournament.status = Tournament.Status.GENERATED
        tournament.number_of_teams = len(team_list)
        tournament.pool_count = 2
        tournament.teams_per_pool = len(team_list) // 2
        tournament.teams_qualifying_per_pool = 2
        tournament.save(
            update_fields=[
                "status",
                "number_of_teams",
                "pool_count",
                "teams_per_pool",
                "teams_qualifying_per_pool",
            ]
        )
        tournament.teams.set(team_list)
        return tournament
