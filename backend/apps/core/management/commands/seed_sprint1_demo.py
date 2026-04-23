"""
Sprint 1 demo data (EP-26 / EP-27 / EP-28 + coach dashboard): clubs, teams, users (Tayma, Lyn, Karma,
Racha, Farouk, Nay), training and match sessions, mixed attendance, skill metrics, roster stats, and
coach feedback — all consumed by GET /api/teams/<id>/coach-dashboard/.

Run from backend/: python manage.py seed_sprint1_demo
Then (optional): python manage.py remind_incomplete_training_attendance

Default login password for most seeded accounts: Sprint1Demo123!
Exception: taymamerhebi@gmail.com uses password taymamerhebi (club director on all demo clubs).
Coach dashboard: log in as lyn.coach@sprint1.local, open Dashboard, select Riyadi U16 in the team
dropdown (or rely on default), data is read from the database only.

Director dashboard: log in as taymamerhebi@gmail.com, open Club dashboard — KPIs, 30-day attendance
trend, payments overview, and club summary are populated from fees, ledger entries, sessions, and
audit logs (see _seed_riyadi_fees_and_ledgers / _seed_nahda_low_attendance).
"""

from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.core.models import (
    Club,
    ContactSubmission,
    ClubMembership,
    CoachFeedbackStatus,
    DirectorPaymentAuditLog,
    FeePaymentLedgerEntry,
    Notification,
    ParentPlayerRelation,
    PlayerFeeRecord,
    PlayerProfile,
    PlayerWeeklySkillMetric,
    Team,
    TeamCoachFeedback,
    TeamMembership,
    TeamRole,
    TeamRosterPlayerStat,
    TeamSkillCategory,
    TeamSkillDashboardMetric,
    TrainingSession,
    TrainingSessionConfirmation,
    VerificationStatus,
)

User = get_user_model()

DEMO_PASSWORD = "Sprint1Demo123!"

CLUB_NAMES = ("Riyadi", "Nahda", "CPF", "AUB")
EECE430_PASSWORD = "test123"
EECE430_CLUB_NAME = "EECE430"


def _monday_of_week_containing(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _next_friday_on_or_after(today: date) -> date:
    """Calendar Friday strictly after `today` (if today is Friday, returns next week's Friday)."""
    days_ahead = (4 - today.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return today + timedelta(days=days_ahead)


class Command(BaseCommand):
    help = "Seed realistic clubs, teams, users, sessions, attendance, and coach dashboard rows for local testing."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Recreate training sessions, confirmations, and coach dashboard rows for Riyadi U16.",
        )
        parser.add_argument(
            "--with-contact-samples",
            action="store_true",
            help="Insert a few ContactSubmission rows for admin / API testing.",
        )

    def handle(self, *args, **options):
        force = options["force"]
        with_contact_samples = options["with_contact_samples"]
        self._seed_eece430_demo(force=force)
        return
        with transaction.atomic():
            director = self._ensure_user(
                email="demo.director@sprint1.local",
                first_name="Club",
                last_name="Director",
            )
            clubs = {}
            for name in CLUB_NAMES:
                club = Club.objects.filter(name=name).first()
                if club is None:
                    club = Club.objects.create_club(name=name, director=director)
                    self.stdout.write(self.style.SUCCESS(f"Created club {name} (id={club.id})"))
                clubs[name] = club

            tayma_director_gmail = self._ensure_user(
                email="taymamerhebi@gmail.com",
                first_name="Tayma",
                last_name="Merhebi",
                date_of_birth=date_from_year(1995),
                password="taymamerhebi",
            )
            for club in clubs.values():
                ClubMembership.objects.assign_director(user=tayma_director_gmail, club=club)
            self.stdout.write(
                self.style.SUCCESS(
                    "Added taymamerhebi@gmail.com as club director on Riyadi, Nahda, CPF, and AUB."
                )
            )

            tayma = self._ensure_user(
                email="tayma.parent@sprint1.local",
                first_name="Tayma",
                last_name="Merhebi",
                date_of_birth=date_from_year(1985),
            )
            lyn = self._ensure_user(
                email="lyn.coach@sprint1.local",
                first_name="Lyn",
                last_name="Coach",
                date_of_birth=date_from_year(1990),
            )
            karma = self._ensure_user(
                email="karma.player@sprint1.local",
                first_name="Karma",
                last_name="Player",
                date_of_birth=date_from_year(2012),
            )
            racha = self._ensure_user(
                email="racha.player@sprint1.local",
                first_name="Racha",
                last_name="Player",
                date_of_birth=date_from_year(2006),
            )
            nay = self._ensure_user(
                email="nay.player@sprint1.local",
                first_name="Nay",
                last_name="Player",
                date_of_birth=date_from_year(2008),
            )
            farouk = self._ensure_user(
                email="farouk.coach@sprint1.local",
                first_name="Farouk",
                last_name="Coach",
                date_of_birth=date_from_year(1988),
            )

            ParentPlayerRelation.objects.link(parent=tayma, player=karma)
            ParentPlayerRelation.objects.link(parent=tayma, player=racha)

            team_riyadi = self._ensure_team(clubs["Riyadi"], "Riyadi U16")
            team_cpf = self._ensure_team(clubs["CPF"], "CPF Juniors")
            team_nahda = self._ensure_team(clubs["Nahda"], "Nahda Development")
            self._ensure_team(clubs["AUB"], "AUB Academy")

            club_riyadi = clubs["Riyadi"]
            club_riyadi.default_monthly_player_fee = Decimal("50.00")
            club_riyadi.save(update_fields=["default_monthly_player_fee"])

            TeamMembership.objects.add_member(user=lyn, team=team_riyadi, role=TeamRole.COACH)
            TeamMembership.objects.add_member(user=farouk, team=team_cpf, role=TeamRole.COACH)
            for pl in (karma, racha, nay):
                TeamMembership.objects.add_member(user=pl, team=team_riyadi, role=TeamRole.PLAYER)

            PlayerProfile.objects.update_or_create(
                user=karma,
                defaults={"jersey_number": 7, "primary_position": "Libero"},
            )
            PlayerProfile.objects.update_or_create(
                user=racha,
                defaults={"jersey_number": 3, "primary_position": "Outside"},
            )
            PlayerProfile.objects.update_or_create(
                user=nay,
                defaults={"jersey_number": 11, "primary_position": "Middle"},
            )

            if force:
                TeamCoachFeedback.objects.filter(team=team_riyadi).delete()
                TeamRosterPlayerStat.objects.filter(team=team_riyadi).delete()
                TeamSkillDashboardMetric.objects.filter(team=team_riyadi).delete()
                PlayerWeeklySkillMetric.objects.filter(team=team_riyadi).delete()
                TrainingSessionConfirmation.objects.filter(training_session__team=team_riyadi).delete()
                TrainingSession.objects.filter(team=team_riyadi).delete()

            if not TrainingSession.objects.filter(team=team_riyadi).exists() or force:
                self._seed_riyadi_sessions_and_dashboard(team_riyadi, karma, racha, nay, tayma, lyn)
                self.stdout.write(
                    self.style.SUCCESS(
                        "Seeded Riyadi U16 sessions, attendance, skill metrics, roster stats, and feedback."
                    )
                )

            self._seed_player_weekly_skill_metrics(team_riyadi, karma, racha, nay)
            self._seed_demo_notifications(team_riyadi, tayma, karma, lyn)

            self._seed_riyadi_fees_and_ledgers(
                club_riyadi,
                team_riyadi,
                karma,
                racha,
                nay,
                tayma_director_gmail,
            )
            self._seed_nahda_low_attendance(team_nahda, karma)
            self.stdout.write(self.style.SUCCESS("Seeded director dashboard fees, ledger, Nahda sessions, and audit logs."))

        if with_contact_samples:
            self._seed_contact_samples()

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Log in as lyn.coach@sprint1.local / {DEMO_PASSWORD} (coach) or "
                f"tayma.parent@sprint1.local (parent of Karma and Racha) or "
                f"taymamerhebi@gmail.com / taymamerhebi (director). "
                f"Team id for Riyadi U16: {team_riyadi.id}."
            )
        )

    def _seed_eece430_demo(self, *, force: bool):
        with transaction.atomic():
            club = self._eece430_club()
            people = self._eece430_people()
            teams = self._eece430_teams(club, people)

            if force:
                self._eece430_clear_existing(club)
                teams = self._eece430_teams(club, people)

            self._eece430_seed_team_data(club, teams, people)

        self.stdout.write(
            self.style.SUCCESS(
                "Seed complete. Log in with any seeded email using password test123. "
                f"Director: laa103@mail.aub.edu. AUB Phoenix team id: {teams['phoenix'].id}."
            )
        )

    def _eece430_club(self):
        director = self._ensure_user(
            email="laa103@mail.aub.edu",
            first_name="Leen",
            last_name="Abdallah",
            date_of_birth=date_from_year(1997),
            password=EECE430_PASSWORD,
        )
        club = Club.objects.filter(name=EECE430_CLUB_NAME).first()
        if club is None:
            club = Club.objects.create_club(
                name=EECE430_CLUB_NAME,
                director=director,
                short_name="EECE430",
                description="University volleyball club demo for the EECE430 project.",
                contact_email="laa103@mail.aub.edu",
                contact_phone="+961 71 430 430",
                website="https://eece430.example.com",
                country="Lebanon",
                city="Beirut",
                address="Bliss Street, Beirut",
                founded_year=2024,
            )
        else:
            club.short_name = "EECE430"
            club.description = "University volleyball club demo for the EECE430 project."
            club.contact_email = "laa103@mail.aub.edu"
            club.contact_phone = "+961 71 430 430"
            club.website = "https://eece430.example.com"
            club.country = "Lebanon"
            club.city = "Beirut"
            club.address = "Bliss Street, Beirut"
            club.founded_year = 2024
            club.save(
                update_fields=[
                    "short_name",
                    "description",
                    "contact_email",
                    "contact_phone",
                    "website",
                    "country",
                    "city",
                    "address",
                    "founded_year",
                ]
            )
        club.default_monthly_player_fee = Decimal("85.00")
        club.save(update_fields=["default_monthly_player_fee"])
        ClubMembership.objects.assign_director(user=director, club=club)
        return club

    def _eece430_people(self):
        people = {
            "director": self._ensure_user(
                email="laa103@mail.aub.edu",
                first_name="Leen",
                last_name="Abdallah",
                date_of_birth=date_from_year(1997),
                password=EECE430_PASSWORD,
            ),
            "standalone": self._ensure_user(
                email="tarek_abdallah@cpf.edu.lb",
                first_name="Tarek",
                last_name="Abdallah",
                date_of_birth=date_from_year(2001),
                password=EECE430_PASSWORD,
            ),
            "coach_phoenix": self._ensure_user(
                email="jmc24@mail.aub.edu",
                first_name="Joseph",
                last_name="Chahine",
                date_of_birth=date_from_year(1998),
                password=EECE430_PASSWORD,
            ),
            "coach_cedars": self._ensure_user(
                email="karim.haddad@mail.aub.edu",
                first_name="Karim",
                last_name="Haddad",
                date_of_birth=date_from_year(1994),
                password=EECE430_PASSWORD,
            ),
            "coach_waves": self._ensure_user(
                email="rami.nassar@mail.aub.edu",
                first_name="Rami",
                last_name="Nassar",
                date_of_birth=date_from_year(1993),
                password=EECE430_PASSWORD,
            ),
            "tayma": self._ensure_user(
                email="tayma.merhebi@gmail.com",
                first_name="Tayma",
                last_name="Merhebi",
                date_of_birth=date(2008, 5, 14),
                password=EECE430_PASSWORD,
            ),
            "jad": self._ensure_user(
                email="jad.khoury@mail.aub.edu",
                first_name="Jad",
                last_name="Khoury",
                date_of_birth=date(2007, 2, 8),
                password=EECE430_PASSWORD,
            ),
            "maya": self._ensure_user(
                email="maya.elias@mail.aub.edu",
                first_name="Maya",
                last_name="Elias",
                date_of_birth=date(2010, 9, 18),
                password=EECE430_PASSWORD,
            ),
            "charbel": self._ensure_user(
                email="charbel.gerges@mail.aub.edu",
                first_name="Charbel",
                last_name="Gerges",
                date_of_birth=date(2009, 11, 2),
                password=EECE430_PASSWORD,
            ),
            "rana": self._ensure_user(
                email="rana.haddad@mail.aub.edu",
                first_name="Rana",
                last_name="Haddad",
                date_of_birth=date(2006, 7, 5),
                password=EECE430_PASSWORD,
            ),
            "elie": self._ensure_user(
                email="elie.tannous@mail.aub.edu",
                first_name="Elie",
                last_name="Tannous",
                date_of_birth=date(2008, 1, 22),
                password=EECE430_PASSWORD,
            ),
            "joelle": self._ensure_user(
                email="joelle.saad@mail.aub.edu",
                first_name="Joelle",
                last_name="Saad",
                date_of_birth=date(2009, 3, 12),
                password=EECE430_PASSWORD,
            ),
            "marc": self._ensure_user(
                email="marc.assaad@mail.aub.edu",
                first_name="Marc",
                last_name="Assaad",
                date_of_birth=date(2007, 8, 30),
                password=EECE430_PASSWORD,
            ),
            "nour": self._ensure_user(
                email="nour.maalouf@mail.aub.edu",
                first_name="Nour",
                last_name="Maalouf",
                date_of_birth=date(2011, 4, 9),
                password=EECE430_PASSWORD,
            ),
            "serge": self._ensure_user(
                email="serge.helou@mail.aub.edu",
                first_name="Serge",
                last_name="Helou",
                date_of_birth=date(2008, 12, 14),
                password=EECE430_PASSWORD,
            ),
            "yara": self._ensure_user(
                email="yara.mattar@mail.aub.edu",
                first_name="Yara",
                last_name="Mattar",
                date_of_birth=date(2009, 6, 1),
                password=EECE430_PASSWORD,
            ),
            "cynthia": self._ensure_user(
                email="cynthia.ayoub@mail.aub.edu",
                first_name="Cynthia",
                last_name="Ayoub",
                date_of_birth=date(2007, 10, 27),
                password=EECE430_PASSWORD,
            ),
            "fadi": self._ensure_user(
                email="fadi.azar@mail.aub.edu",
                first_name="Fadi",
                last_name="Azar",
                date_of_birth=date(2008, 4, 4),
                password=EECE430_PASSWORD,
            ),
            "nadine": self._ensure_user(
                email="nadine.bazzi@mail.aub.edu",
                first_name="Nadine",
                last_name="Bazzi",
                date_of_birth=date(2010, 1, 19),
                password=EECE430_PASSWORD,
            ),
            "walid": self._ensure_user(
                email="walid.sfeir@mail.aub.edu",
                first_name="Walid",
                last_name="Sfeir",
                date_of_birth=date(2007, 5, 11),
                password=EECE430_PASSWORD,
            ),
            "parent_mona": self._ensure_user(
                email="mona.merhebi@gmail.com",
                first_name="Mona",
                last_name="Merhebi",
                date_of_birth=date_from_year(1982),
                password=EECE430_PASSWORD,
            ),
            "parent_hassan": self._ensure_user(
                email="hassan.elias@gmail.com",
                first_name="Hassan",
                last_name="Elias",
                date_of_birth=date_from_year(1979),
                password=EECE430_PASSWORD,
            ),
            "parent_dania": self._ensure_user(
                email="dania.maalouf@gmail.com",
                first_name="Dania",
                last_name="Maalouf",
                date_of_birth=date_from_year(1984),
                password=EECE430_PASSWORD,
            ),
            "parent_samir": self._ensure_user(
                email="samir.bazzi@gmail.com",
                first_name="Samir",
                last_name="Bazzi",
                date_of_birth=date_from_year(1978),
                password=EECE430_PASSWORD,
            ),
        }
        ParentPlayerRelation.objects.link(parent=people["parent_mona"], player=people["tayma"])
        ParentPlayerRelation.objects.link(parent=people["parent_hassan"], player=people["maya"])
        ParentPlayerRelation.objects.link(parent=people["parent_dania"], player=people["nour"])
        ParentPlayerRelation.objects.link(parent=people["parent_samir"], player=people["nadine"])
        return people

    def _eece430_teams(self, club, people):
        teams = {
            "phoenix": self._eece430_team(club, "AUB Phoenix", "U18", "AUB Main Court"),
            "cedars": self._eece430_team(club, "Beirut Cedars", "U16", "AUB Practice Hall"),
            "waves": self._eece430_team(club, "Mount Lebanon Waves", "U17", "Charles Hostler Annex"),
        }
        roster_map = {
            "phoenix": [
                (people["coach_phoenix"], TeamRole.COACH),
                (people["tayma"], TeamRole.PLAYER),
                (people["jad"], TeamRole.PLAYER),
                (people["maya"], TeamRole.PLAYER),
                (people["charbel"], TeamRole.PLAYER),
                (people["rana"], TeamRole.PLAYER),
            ],
            "cedars": [
                (people["coach_cedars"], TeamRole.COACH),
                (people["elie"], TeamRole.PLAYER),
                (people["joelle"], TeamRole.PLAYER),
                (people["marc"], TeamRole.PLAYER),
                (people["nour"], TeamRole.PLAYER),
                (people["serge"], TeamRole.PLAYER),
            ],
            "waves": [
                (people["coach_waves"], TeamRole.COACH),
                (people["yara"], TeamRole.PLAYER),
                (people["cynthia"], TeamRole.PLAYER),
                (people["fadi"], TeamRole.PLAYER),
                (people["nadine"], TeamRole.PLAYER),
                (people["walid"], TeamRole.PLAYER),
            ],
        }
        for team_key, members in roster_map.items():
            for user, role in members:
                TeamMembership.objects.add_member(user=user, team=teams[team_key], role=role)
        self._eece430_profiles(people)
        return teams

    def _eece430_clear_existing(self, club):
        team_ids = list(club.teams.values_list("id", flat=True))
        TeamCoachFeedback.objects.filter(team_id__in=team_ids).delete()
        TeamRosterPlayerStat.objects.filter(team_id__in=team_ids).delete()
        TeamSkillDashboardMetric.objects.filter(team_id__in=team_ids).delete()
        PlayerWeeklySkillMetric.objects.filter(team_id__in=team_ids).delete()
        TrainingSessionConfirmation.objects.filter(training_session__team_id__in=team_ids).delete()
        Notification.objects.filter(team_id__in=team_ids).delete()
        TrainingSession.objects.filter(team_id__in=team_ids).delete()
        PlayerFeeRecord.objects.filter(club=club).delete()
        DirectorPaymentAuditLog.objects.filter(club=club).delete()

    def _eece430_team(self, club, name, age_group, home_venue):
        team, _ = Team.objects.get_or_create(
            club=club,
            name=name,
            defaults={
                "description": f"{name} seeded demo roster",
                "season": "2025-26",
                "age_group": age_group,
                "gender": Team.Gender.MIXED,
                "home_venue": home_venue,
                "status": Team.Status.ACTIVE,
            },
        )
        team.description = f"{name} seeded demo roster"
        team.season = "2025-26"
        team.age_group = age_group
        team.gender = Team.Gender.MIXED
        team.home_venue = home_venue
        team.status = Team.Status.ACTIVE
        team.save(
            update_fields=[
                "description",
                "season",
                "age_group",
                "gender",
                "home_venue",
                "status",
            ]
        )
        return team

    def _eece430_profiles(self, people):
        rows = [
            (people["tayma"], 4, "Setter"),
            (people["jad"], 8, "Outside"),
            (people["maya"], 2, "Libero"),
            (people["charbel"], 13, "Middle"),
            (people["rana"], 6, "Opposite"),
            (people["elie"], 10, "Setter"),
            (people["joelle"], 5, "Outside"),
            (people["marc"], 11, "Middle"),
            (people["nour"], 1, "Libero"),
            (people["serge"], 14, "Opposite"),
            (people["yara"], 7, "Outside"),
            (people["cynthia"], 9, "Setter"),
            (people["fadi"], 12, "Middle"),
            (people["nadine"], 3, "Libero"),
            (people["walid"], 15, "Opposite"),
        ]
        for player, jersey_number, primary_position in rows:
            PlayerProfile.objects.update_or_create(
                user=player,
                defaults={
                    "jersey_number": jersey_number,
                    "primary_position": primary_position,
                },
            )

    def _eece430_seed_team_data(self, club, teams, people):
        self._eece430_seed_phoenix(teams["phoenix"], people)
        self._eece430_seed_cedars(teams["cedars"], people)
        self._eece430_seed_waves(teams["waves"], people)
        self._eece430_seed_fees(club, teams, people)
        self._eece430_seed_notifications(teams, people)

    def _eece430_seed_weekly_metrics(self, team, curves):
        first_monday = _monday_of_week_containing(timezone.localdate() - timedelta(weeks=7))
        for player, triples in curves.items():
            for idx, (attack, defense, serve) in enumerate(triples):
                PlayerWeeklySkillMetric.objects.update_or_create(
                    player=player,
                    team=team,
                    week_start=first_monday + timedelta(weeks=idx),
                    defaults={
                        "attack": Decimal(str(attack)),
                        "defense": Decimal(str(defense)),
                        "serve": Decimal(str(serve)),
                    },
                )

    def _eece430_upsert_feedback(self, team, coach, rows):
        for player, body, status in rows:
            TeamCoachFeedback.objects.update_or_create(
                team=team,
                player=player,
                coach=coach,
                body=body,
                defaults={"status": status},
            )

    def _eece430_confirm(self, session, player, by_user):
        TrainingSessionConfirmation.objects.update_or_create(
            training_session=session,
            player=player,
            defaults={"confirmed_by": by_user},
        )

    def _eece430_seed_phoenix(self, team, people):
        today = timezone.localdate()
        next_friday = _next_friday_on_or_after(today)
        sessions = []
        for title, off in [
            ("Explosive footwork training", 35),
            ("Serve receive focus", 28),
            ("Transition drills", 21),
            ("Defensive system rehearsal", 14),
            ("Pre-match sharpener", 7),
            ("Video review and light session", 3),
        ]:
            session, _ = TrainingSession.objects.get_or_create(
                team=team,
                title=title,
                scheduled_date=today - timedelta(days=off),
                defaults={
                    "session_type": TrainingSession.SessionType.TRAINING,
                    "start_time": time(18, 0),
                    "end_time": time(19, 30),
                    "location": "AUB Main Court",
                    "status": TrainingSession.Status.SCHEDULED,
                },
            )
            sessions.append(session)
        past_match, _ = TrainingSession.objects.get_or_create(
            team=team,
            title="Friendly vs LAU Spikers",
            scheduled_date=today - timedelta(days=10),
            defaults={
                "session_type": TrainingSession.SessionType.MATCH,
                "start_time": time(19, 0),
                "end_time": time(21, 0),
                "location": "AUB Main Court",
                "opponent": "LAU Spikers",
                "match_type": TrainingSession.MatchType.FRIENDLY,
                "status": TrainingSession.Status.SCHEDULED,
            },
        )
        today_session, _ = TrainingSession.objects.get_or_create(
            team=team,
            title="Tonight's training",
            scheduled_date=today,
            defaults={
                "session_type": TrainingSession.SessionType.TRAINING,
                "start_time": time(18, 30),
                "end_time": time(20, 0),
                "location": "AUB Main Court",
                "status": TrainingSession.Status.SCHEDULED,
            },
        )
        future_session, _ = TrainingSession.objects.get_or_create(
            team=team,
            title="Reception and rotation practice",
            scheduled_date=today + timedelta(days=4),
            defaults={
                "session_type": TrainingSession.SessionType.TRAINING,
                "start_time": time(18, 0),
                "end_time": time(19, 30),
                "location": "AUB Main Court",
                "status": TrainingSession.Status.SCHEDULED,
            },
        )
        upcoming_match, _ = TrainingSession.objects.get_or_create(
            team=team,
            title="League vs Beirut Saints",
            scheduled_date=next_friday,
            defaults={
                "session_type": TrainingSession.SessionType.MATCH,
                "start_time": time(19, 30),
                "end_time": time(21, 30),
                "location": "Athenee Court",
                "opponent": "Beirut Saints",
                "match_type": TrainingSession.MatchType.LEAGUE,
                "status": TrainingSession.Status.SCHEDULED,
            },
        )
        TrainingSession.objects.get_or_create(
            team=team,
            title="Cancelled recovery session",
            scheduled_date=today - timedelta(days=5),
            defaults={
                "session_type": TrainingSession.SessionType.TRAINING,
                "start_time": time(17, 30),
                "end_time": time(18, 30),
                "location": "AUB Main Court",
                "status": TrainingSession.Status.CANCELLED,
            },
        )
        attendance = {
            people["tayma"]: [1, 0, 1, 0, 1, 0],
            people["jad"]: [1, 1, 1, 1, 0, 1],
            people["maya"]: [1, 1, 0, 1, 1, 1],
            people["charbel"]: [0, 1, 1, 0, 1, 1],
            people["rana"]: [1, 1, 1, 1, 1, 0],
        }
        confirmers = {
            people["tayma"]: people["parent_mona"],
            people["jad"]: people["jad"],
            people["maya"]: people["parent_hassan"],
            people["charbel"]: people["charbel"],
            people["rana"]: people["rana"],
        }
        for player, flags in attendance.items():
            for idx, did_confirm in enumerate(flags):
                if did_confirm:
                    self._eece430_confirm(sessions[idx], player, confirmers[player])
        for player in (people["jad"], people["maya"], people["rana"]):
            self._eece430_confirm(past_match, player, confirmers[player])
        for player in (people["tayma"], people["jad"], people["rana"]):
            self._eece430_confirm(today_session, player, confirmers[player])
        for player in (people["jad"], people["charbel"]):
            self._eece430_confirm(future_session, player, confirmers[player])
        for player in (people["tayma"], people["maya"]):
            self._eece430_confirm(upcoming_match, player, confirmers[player])
        self._eece430_team_metrics(
            team,
            [
                (TeamSkillCategory.ATTACK, "78.00", "74.00"),
                (TeamSkillCategory.DEFENSE, "84.00", "81.00"),
                (TeamSkillCategory.SERVE, "72.00", "77.00"),
                (TeamSkillCategory.BLOCK, "69.00", "71.00"),
            ],
        )
        self._eece430_roster_stats(
            team,
            [
                (people["tayma"], 4, 1, "83.00", "79.00"),
                (people["jad"], 18, 4, "76.00", "72.00"),
                (people["maya"], 3, 0, "88.00", "85.00"),
                (people["charbel"], 11, 8, "68.00", "66.00"),
                (people["rana"], 15, 3, "81.00", "77.00"),
            ],
        )
        self._eece430_upsert_feedback(
            team,
            people["coach_phoenix"],
            [
                (people["tayma"], "Good decision-making under pressure. Keep communicating earlier in serve receive.", CoachFeedbackStatus.ADDRESSED),
                (people["maya"], "Excellent floor coverage, but stay louder on second-ball calls.", CoachFeedbackStatus.PENDING),
                (people["charbel"], "Timing on the quick attack is improving. Work on closing the block faster.", CoachFeedbackStatus.PENDING),
            ],
        )
        self._eece430_seed_weekly_metrics(
            team,
            {
                people["tayma"]: [(66, 72, 74), (67, 73, 75), (68, 74, 76), (70, 75, 77), (71, 76, 79), (72, 77, 80), (73, 78, 81), (74, 79, 82)],
                people["jad"]: [(70, 69, 67), (71, 70, 68), (72, 71, 70), (73, 72, 71), (74, 73, 72), (75, 74, 74), (76, 75, 75), (77, 76, 76)],
                people["maya"]: [(74, 80, 79), (75, 81, 80), (76, 82, 81), (77, 83, 82), (78, 84, 83), (79, 85, 84), (80, 86, 85), (81, 87, 86)],
                people["charbel"]: [(62, 66, 60), (63, 67, 61), (64, 68, 62), (65, 69, 63), (66, 70, 64), (67, 71, 65), (68, 72, 66), (69, 73, 67)],
                people["rana"]: [(71, 70, 73), (72, 71, 74), (73, 72, 75), (74, 73, 76), (75, 74, 77), (76, 75, 78), (77, 76, 79), (78, 77, 80)],
            },
        )

    def _eece430_seed_cedars(self, team, people):
        today = timezone.localdate()
        sessions = []
        for title, off in [
            ("Cedars ball-control session", 30),
            ("Cedars serve consistency", 23),
            ("Cedars transition defense", 16),
            ("Cedars block positioning", 9),
            ("Cedars pre-weekend practice", 2),
        ]:
            session, _ = TrainingSession.objects.get_or_create(
                team=team,
                title=title,
                scheduled_date=today - timedelta(days=off),
                defaults={
                    "session_type": TrainingSession.SessionType.TRAINING,
                    "start_time": time(17, 30),
                    "end_time": time(19, 0),
                    "location": "AUB Practice Hall",
                    "status": TrainingSession.Status.SCHEDULED,
                },
            )
            sessions.append(session)
        today_session, _ = TrainingSession.objects.get_or_create(
            team=team,
            title="Cedars training tonight",
            scheduled_date=today,
            defaults={
                "session_type": TrainingSession.SessionType.TRAINING,
                "start_time": time(17, 30),
                "end_time": time(19, 0),
                "location": "AUB Practice Hall",
                "status": TrainingSession.Status.SCHEDULED,
            },
        )
        next_session, _ = TrainingSession.objects.get_or_create(
            team=team,
            title="Cedars weekend tune-up",
            scheduled_date=today + timedelta(days=3),
            defaults={
                "session_type": TrainingSession.SessionType.TRAINING,
                "start_time": time(10, 30),
                "end_time": time(12, 0),
                "location": "AUB Practice Hall",
                "status": TrainingSession.Status.SCHEDULED,
            },
        )
        attendance = {
            people["elie"]: [1, 1, 1, 0, 1],
            people["joelle"]: [1, 0, 1, 1, 1],
            people["marc"]: [0, 1, 0, 1, 1],
            people["nour"]: [1, 1, 0, 0, 1],
            people["serge"]: [1, 1, 1, 1, 0],
        }
        confirmers = {
            people["elie"]: people["elie"],
            people["joelle"]: people["joelle"],
            people["marc"]: people["marc"],
            people["nour"]: people["parent_dania"],
            people["serge"]: people["serge"],
        }
        for player, flags in attendance.items():
            for idx, did_confirm in enumerate(flags):
                if did_confirm:
                    self._eece430_confirm(sessions[idx], player, confirmers[player])
        for player in (people["elie"], people["nour"]):
            self._eece430_confirm(today_session, player, confirmers[player])
        for player in (people["joelle"], people["serge"]):
            self._eece430_confirm(next_session, player, confirmers[player])
        self._eece430_team_metrics(
            team,
            [
                (TeamSkillCategory.ATTACK, "74.00", "70.00"),
                (TeamSkillCategory.DEFENSE, "77.00", "75.00"),
                (TeamSkillCategory.SERVE, "79.00", "73.00"),
                (TeamSkillCategory.BLOCK, "65.00", "68.00"),
            ],
        )
        self._eece430_roster_stats(
            team,
            [
                (people["elie"], 9, 2, "78.00", "74.00"),
                (people["joelle"], 12, 2, "80.00", "76.00"),
                (people["marc"], 10, 5, "69.00", "66.00"),
                (people["nour"], 2, 0, "84.00", "81.00"),
                (people["serge"], 13, 4, "73.00", "70.00"),
            ],
        )
        self._eece430_upsert_feedback(
            team,
            people["coach_cedars"],
            [
                (people["joelle"], "More consistent from the service line this week. Keep your shoulders square.", CoachFeedbackStatus.ADDRESSED),
                (people["marc"], "Read the setter earlier when closing the middle block.", CoachFeedbackStatus.PENDING),
            ],
        )
        self._eece430_seed_weekly_metrics(
            team,
            {
                people["elie"]: [(68, 66, 70), (69, 67, 71), (70, 68, 72), (71, 69, 73), (72, 70, 74), (73, 71, 75), (74, 72, 76), (75, 73, 77)],
                people["joelle"]: [(64, 70, 69), (65, 71, 70), (66, 72, 71), (67, 73, 72), (68, 74, 73), (69, 75, 74), (70, 76, 75), (71, 77, 76)],
                people["marc"]: [(66, 63, 61), (67, 64, 62), (68, 65, 63), (69, 66, 64), (70, 67, 65), (71, 68, 66), (72, 69, 67), (73, 70, 68)],
                people["nour"]: [(60, 72, 74), (61, 73, 75), (62, 74, 76), (63, 75, 77), (64, 76, 78), (65, 77, 79), (66, 78, 80), (67, 79, 81)],
                people["serge"]: [(69, 67, 66), (70, 68, 67), (71, 69, 68), (72, 70, 69), (73, 71, 70), (74, 72, 71), (75, 73, 72), (76, 74, 73)],
            },
        )

    def _eece430_seed_waves(self, team, people):
        today = timezone.localdate()
        sessions = []
        for title, off in [
            ("Waves conditioning and defense", 27),
            ("Waves serve and chase", 20),
            ("Waves scrimmage blocks", 13),
            ("Waves tactical rotation work", 6),
        ]:
            session, _ = TrainingSession.objects.get_or_create(
                team=team,
                title=title,
                scheduled_date=today - timedelta(days=off),
                defaults={
                    "session_type": TrainingSession.SessionType.TRAINING,
                    "start_time": time(18, 15),
                    "end_time": time(19, 45),
                    "location": "Charles Hostler Annex",
                    "status": TrainingSession.Status.SCHEDULED,
                },
            )
            sessions.append(session)
        match_session, _ = TrainingSession.objects.get_or_create(
            team=team,
            title="League vs Byblos Juniors",
            scheduled_date=today - timedelta(days=11),
            defaults={
                "session_type": TrainingSession.SessionType.MATCH,
                "start_time": time(19, 0),
                "end_time": time(21, 0),
                "location": "Byblos Sports Center",
                "opponent": "Byblos Juniors",
                "match_type": TrainingSession.MatchType.LEAGUE,
                "status": TrainingSession.Status.SCHEDULED,
            },
        )
        future_session, _ = TrainingSession.objects.get_or_create(
            team=team,
            title="Waves recovery training",
            scheduled_date=today + timedelta(days=2),
            defaults={
                "session_type": TrainingSession.SessionType.TRAINING,
                "start_time": time(18, 15),
                "end_time": time(19, 30),
                "location": "Charles Hostler Annex",
                "status": TrainingSession.Status.SCHEDULED,
            },
        )
        attendance = {
            people["yara"]: [1, 1, 1, 1],
            people["cynthia"]: [1, 0, 1, 1],
            people["fadi"]: [0, 1, 1, 0],
            people["nadine"]: [1, 1, 0, 1],
            people["walid"]: [1, 0, 0, 1],
        }
        confirmers = {
            people["yara"]: people["yara"],
            people["cynthia"]: people["cynthia"],
            people["fadi"]: people["fadi"],
            people["nadine"]: people["parent_samir"],
            people["walid"]: people["walid"],
        }
        for player, flags in attendance.items():
            for idx, did_confirm in enumerate(flags):
                if did_confirm:
                    self._eece430_confirm(sessions[idx], player, confirmers[player])
        for player in (people["yara"], people["cynthia"], people["nadine"]):
            self._eece430_confirm(match_session, player, confirmers[player])
        for player in (people["yara"], people["walid"]):
            self._eece430_confirm(future_session, player, confirmers[player])
        self._eece430_team_metrics(
            team,
            [
                (TeamSkillCategory.ATTACK, "71.00", "69.00"),
                (TeamSkillCategory.DEFENSE, "76.00", "72.00"),
                (TeamSkillCategory.SERVE, "74.00", "70.00"),
                (TeamSkillCategory.BLOCK, "67.00", "69.00"),
            ],
        )
        self._eece430_roster_stats(
            team,
            [
                (people["yara"], 14, 2, "77.00", "73.00"),
                (people["cynthia"], 6, 1, "82.00", "78.00"),
                (people["fadi"], 11, 7, "70.00", "67.00"),
                (people["nadine"], 2, 0, "86.00", "83.00"),
                (people["walid"], 12, 3, "75.00", "71.00"),
            ],
        )
        self._eece430_upsert_feedback(
            team,
            people["coach_waves"],
            [
                (people["yara"], "Leadership in transition defense has been strong. Keep organizing the back row.", CoachFeedbackStatus.ADDRESSED),
                (people["fadi"], "Better hand positioning at the net will cut down touches off the block.", CoachFeedbackStatus.PENDING),
            ],
        )
        self._eece430_seed_weekly_metrics(
            team,
            {
                people["yara"]: [(69, 71, 70), (70, 72, 71), (71, 73, 72), (72, 74, 73), (73, 75, 74), (74, 76, 75), (75, 77, 76), (76, 78, 77)],
                people["cynthia"]: [(67, 68, 72), (68, 69, 73), (69, 70, 74), (70, 71, 75), (71, 72, 76), (72, 73, 77), (73, 74, 78), (74, 75, 79)],
                people["fadi"]: [(65, 64, 63), (66, 65, 64), (67, 66, 65), (68, 67, 66), (69, 68, 67), (70, 69, 68), (71, 70, 69), (72, 71, 70)],
                people["nadine"]: [(61, 74, 76), (62, 75, 77), (63, 76, 78), (64, 77, 79), (65, 78, 80), (66, 79, 81), (67, 80, 82), (68, 81, 83)],
                people["walid"]: [(68, 66, 67), (69, 67, 68), (70, 68, 69), (71, 69, 70), (72, 70, 71), (73, 71, 72), (74, 72, 73), (75, 73, 74)],
            },
        )

    def _eece430_team_metrics(self, team, rows):
        for category, attendance_rate, average_performance in rows:
            TeamSkillDashboardMetric.objects.update_or_create(
                team=team,
                skill_category=category,
                defaults={
                    "attendance_rate": Decimal(attendance_rate),
                    "average_performance": Decimal(average_performance),
                },
            )

    def _eece430_roster_stats(self, team, rows):
        for player, spikes, blocks, serve_percentage, prior_serve_percentage in rows:
            TeamRosterPlayerStat.objects.update_or_create(
                team=team,
                player=player,
                defaults={
                    "spikes": spikes,
                    "blocks": blocks,
                    "serve_percentage": Decimal(serve_percentage),
                    "prior_serve_percentage": Decimal(prior_serve_percentage),
                },
            )

    def _eece430_seed_fees(self, club, teams, people):
        today = timezone.localdate()
        period_start = date(today.year, today.month, 1)
        due_date = period_start + timedelta(days=12)
        rows = [
            (people["tayma"], teams["phoenix"], "85.00", "85.00", "Monthly dues - AUB Phoenix"),
            (people["jad"], teams["phoenix"], "85.00", "40.00", "Monthly dues - AUB Phoenix"),
            (people["maya"], teams["phoenix"], "85.00", "0.00", "Monthly dues - AUB Phoenix"),
            (people["elie"], teams["cedars"], "75.00", "75.00", "Monthly dues - Beirut Cedars"),
            (people["nour"], teams["cedars"], "75.00", "25.00", "Monthly dues - Beirut Cedars"),
            (people["yara"], teams["waves"], "80.00", "80.00", "Monthly dues - Mount Lebanon Waves"),
            (people["nadine"], teams["waves"], "80.00", "30.00", "Monthly dues - Mount Lebanon Waves"),
        ]
        for player, team, amount_due, amount_paid, description in rows:
            rec, _ = PlayerFeeRecord.objects.update_or_create(
                club=club,
                player=player,
                team=team,
                billing_period_start=period_start,
                defaults={
                    "description": description,
                    "amount_due": Decimal(amount_due),
                    "amount_paid": Decimal(amount_paid),
                    "currency": "USD",
                    "due_date": due_date,
                },
            )
            FeePaymentLedgerEntry.objects.filter(fee_record=rec).delete()
            if Decimal(amount_paid) > 0:
                FeePaymentLedgerEntry.objects.create(
                    fee_record=rec,
                    amount=Decimal(amount_paid),
                    note="Demo payment",
                )
        self._eece430_audit_log(
            club,
            people["director"],
            DirectorPaymentAuditLog.Action.FEE_CREATED,
            "Seed demo: materialized monthly fee lines for EECE430.",
        )
        self._eece430_audit_log(
            club,
            people["director"],
            DirectorPaymentAuditLog.Action.PAYMENT_RECORDED,
            "Seed demo: recorded partial and full payments for EECE430 players.",
        )

    def _eece430_seed_notifications(self, teams, people):
        rows = [
            (
                people["director"],
                teams["phoenix"],
                "Director snapshot",
                "AUB Phoenix has mixed attendance this week and two outstanding fee balances.",
            ),
            (
                people["coach_phoenix"],
                teams["phoenix"],
                "Roster follow-up",
                "Three players still need attendance follow-up across recent and current sessions.",
            ),
            (
                people["parent_mona"],
                teams["phoenix"],
                "Parent reminder",
                "Tayma has an upcoming league match on Friday evening. Review the dashboard before game day.",
            ),
            (
                people["nour"],
                teams["cedars"],
                "Practice reminder",
                "Cedars weekend tune-up is scheduled in three days at AUB Practice Hall.",
            ),
        ]
        for recipient, team, title, message in rows:
            if not Notification.objects.filter(recipient=recipient, team=team, title=title).exists():
                Notification.objects.create(
                    recipient=recipient,
                    created_by=None,
                    team=team,
                    title=title,
                    message=message,
                    category=Notification.Category.MANUAL,
                )

    def _eece430_audit_log(self, club, actor, action, detail):
        if not DirectorPaymentAuditLog.objects.filter(club=club, detail=detail).exists():
            DirectorPaymentAuditLog.objects.create(
                club=club,
                actor=actor,
                action=action,
                detail=detail,
            )

    def _seed_contact_samples(self):
        samples = [
            {
                "name": "Demo Director",
                "email": "demo.contact.director@sprint1.local",
                "role": ContactSubmission.ContactRole.DIRECTOR,
                "message": "We would like to schedule a walkthrough of NetUp for our club board.",
                "phone": "+1 555 0101",
            },
            {
                "name": "Jamie Parent",
                "email": "demo.contact.parent@sprint1.local",
                "role": ContactSubmission.ContactRole.PARENT,
                "message": "Question about parent visibility for U14 schedules.",
                "phone": "",
            },
            {
                "name": "Alex Coach",
                "email": "demo.contact.coach@sprint1.local",
                "role": ContactSubmission.ContactRole.COACH,
                "message": "Interested in the attendance workflow for training sessions.",
                "phone": "+1 555 0199",
            },
        ]
        created = 0
        for row in samples:
            _, was_created = ContactSubmission.objects.get_or_create(
                email=row["email"],
                message=row["message"],
                defaults={
                    "name": row["name"],
                    "role": row["role"],
                    "phone": row["phone"],
                },
            )
            if was_created:
                created += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"Contact samples: {created} new row(s), {len(samples) - created} already present."
            )
        )

    def _ensure_user(
        self,
        *,
        email,
        first_name,
        last_name,
        date_of_birth=None,
        password=DEMO_PASSWORD,
    ):
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "first_name": first_name,
                "last_name": last_name,
                "verification_status": VerificationStatus.VERIFIED,
                "date_of_birth": date_of_birth,
            },
        )
        if not created:
            user.first_name = first_name
            user.last_name = last_name
            user.verification_status = VerificationStatus.VERIFIED
            if date_of_birth is not None:
                user.date_of_birth = date_of_birth
            user.save(
                update_fields=[
                    "first_name",
                    "last_name",
                    "verification_status",
                    "date_of_birth",
                ]
            )
        user.set_password(password)
        user.save(update_fields=["password"])
        return user

    def _ensure_team(self, club, name):
        team, created = Team.objects.get_or_create(
            club=club,
            name=name,
            defaults={"description": "Sprint 1 demo team", "season": "2025-26"},
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created team {name} under {club.name} (id={team.id})"))
        return team

    def _seed_riyadi_sessions_and_dashboard(self, team, karma, racha, nay, tayma, lyn):
        today = timezone.localdate()
        next_friday = _next_friday_on_or_after(today)

        def confirm(sess, player, by_user):
            TrainingSessionConfirmation.objects.update_or_create(
                training_session=sess,
                player=player,
                defaults={"confirmed_by": by_user},
            )

        past_offsets = [56, 49, 42, 35, 28, 24, 21, 17, 14, 10, 7, 3]
        sessions = []
        for i, off in enumerate(past_offsets):
            s = TrainingSession.objects.create(
                team=team,
                title=f"Practice week {-off // 7}",
                session_type=TrainingSession.SessionType.TRAINING,
                scheduled_date=today - timedelta(days=off),
                start_time=time(17, 30),
                end_time=time(19, 0),
                location="Main gym",
                status=TrainingSession.Status.SCHEDULED,
            )
            sessions.append(s)

        past_match = TrainingSession.objects.create(
            team=team,
            title="League vs North Side",
            session_type=TrainingSession.SessionType.MATCH,
            scheduled_date=today - timedelta(days=18),
            start_time=time(19, 0),
            end_time=time(21, 0),
            location="Riyadi Arena",
            opponent="North Side",
            match_type=TrainingSession.MatchType.LEAGUE,
            status=TrainingSession.Status.SCHEDULED,
        )
        confirm(past_match, racha, racha)
        confirm(past_match, nay, nay)
        # Karma absent (no confirmation) for this past match

        today_session = TrainingSession.objects.create(
            team=team,
            title="Practice (today)",
            session_type=TrainingSession.SessionType.TRAINING,
            scheduled_date=today,
            start_time=time(18, 0),
            end_time=time(19, 30),
            location="Main gym",
        )
        confirm(today_session, karma, tayma)
        confirm(today_session, racha, racha)
        # Nay: pending (no row) for today's session

        future_session = TrainingSession.objects.create(
            team=team,
            title="Practice (upcoming)",
            session_type=TrainingSession.SessionType.TRAINING,
            scheduled_date=today + timedelta(days=5),
            start_time=time(18, 0),
            end_time=time(19, 30),
            location="Arena B",
        )

        upcoming_match = TrainingSession.objects.create(
            team=team,
            title="League vs Sea Eagles",
            session_type=TrainingSession.SessionType.MATCH,
            scheduled_date=next_friday,
            start_time=time(18, 30),
            end_time=time(20, 30),
            location="National Court",
            opponent="Sea Eagles",
            match_type=TrainingSession.MatchType.LEAGUE,
        )

        TrainingSession.objects.create(
            team=team,
            title="Cancelled scrimmage (ignored in analytics)",
            session_type=TrainingSession.SessionType.TRAINING,
            scheduled_date=today - timedelta(days=10),
            start_time=time(16, 0),
            end_time=time(17, 30),
            status=TrainingSession.Status.CANCELLED,
        )

        # Racha: high attendance — confirmed all past practices
        for s in sessions:
            confirm(s, racha, racha)

        # Nay: medium — every other past practice
        for idx, s in enumerate(sessions):
            if idx % 2 == 0:
                confirm(s, nay, nay)

        # Karma: low — parent confirms 2 of 8 past practices
        confirm(sessions[0], karma, tayma)
        confirm(sessions[2], karma, tayma)

        confirm(future_session, racha, racha)
        confirm(future_session, nay, nay)

        self.stdout.write(
            f"Sessions: today id={today_session.id}, future practice id={future_session.id}, "
            f"upcoming match id={upcoming_match.id}."
        )

        # --- Coach dashboard DB rows (API: coach-dashboard) ---
        skill_rows = [
            (TeamSkillCategory.ATTACK, Decimal("82.00"), Decimal("71.00")),
            (TeamSkillCategory.DEFENSE, Decimal("76.00"), Decimal("84.00")),
            (TeamSkillCategory.SERVE, Decimal("91.00"), Decimal("63.00")),
            (TeamSkillCategory.BLOCK, Decimal("68.00"), Decimal("79.00")),
        ]
        for cat, att, perf in skill_rows:
            TeamSkillDashboardMetric.objects.update_or_create(
                team=team,
                skill_category=cat,
                defaults={"attendance_rate": att, "average_performance": perf},
            )

        roster_defaults = [
            (karma, 12, 3, Decimal("82.00"), Decimal("74.00")),
            (racha, 6, 1, Decimal("60.00"), Decimal("68.00")),
            (nay, 9, 2, Decimal("75.00"), Decimal("70.00")),
        ]
        for player, spikes, blocks, serve_pct, prior in roster_defaults:
            TeamRosterPlayerStat.objects.update_or_create(
                team=team,
                player=player,
                defaults={
                    "spikes": spikes,
                    "blocks": blocks,
                    "serve_percentage": serve_pct,
                    "prior_serve_percentage": prior,
                },
            )

        TeamCoachFeedback.objects.create(
            team=team,
            player=nay,
            coach=lyn,
            body="Strong blocking in last scrimmage — keep it up.",
            status=CoachFeedbackStatus.ADDRESSED,
        )
        TeamCoachFeedback.objects.create(
            team=team,
            player=karma,
            coach=lyn,
            body="improve footwork timing",
            status=CoachFeedbackStatus.PENDING,
        )
        TeamCoachFeedback.objects.create(
            team=team,
            player=racha,
            coach=lyn,
            body="work on the serve",
            status=CoachFeedbackStatus.PENDING,
        )

    def _seed_player_weekly_skill_metrics(self, team, karma, racha, nay):
        """Eight weeks of Attack/Defense/Serve scores for member dashboard charts."""
        today = timezone.localdate()
        first_monday = _monday_of_week_containing(today - timedelta(weeks=7))
        curves = [
            (karma, [(52 + i * 4, 58 + i * 3, 60 + i * 3) for i in range(8)]),
            (racha, [(68 + i * 2, 72 + i * 2, 64 + i * 2) for i in range(8)]),
            (nay, [(60 + i * 3, 56 + i * 3, 68 + i * 2) for i in range(8)]),
        ]
        for player, triples in curves:
            for i, (a, d, s) in enumerate(triples):
                ws = first_monday + timedelta(weeks=i)
                PlayerWeeklySkillMetric.objects.update_or_create(
                    player=player,
                    team=team,
                    week_start=ws,
                    defaults={
                        "attack": Decimal(str(min(98, a))),
                        "defense": Decimal(str(min(98, d))),
                        "serve": Decimal(str(min(98, s))),
                    },
                )

    def _seed_demo_notifications(self, team, tayma_parent, karma_player, coach_user):
        if not Notification.objects.filter(recipient=tayma_parent, title="Club update (demo)").exists():
            Notification.objects.create(
                recipient=tayma_parent,
                created_by=coach_user,
                team=team,
                title="Club update (demo)",
                message="Riyadi U16 fees and attendance are synced for the sprint 1 demo.",
                category=Notification.Category.MANUAL,
            )
        if not Notification.objects.filter(recipient=karma_player, title="Practice reminder (demo)").exists():
            Notification.objects.create(
                recipient=karma_player,
                created_by=coach_user,
                team=team,
                title="Practice reminder (demo)",
                message="Check your dashboard for the next session and confirm attendance when available.",
                category=Notification.Category.MANUAL,
            )

    def _seed_riyadi_fees_and_ledgers(self, club, team, karma, racha, nay, director_user):
        today = timezone.localdate()
        period_start = date(today.year, today.month, 1)
        due_date = period_start + timedelta(days=14)
        specs = [
            (karma, Decimal("120.00"), Decimal("48.00"), "Monthly dues + kit (Karma)"),
            (racha, Decimal("95.00"), Decimal("95.00"), "Monthly dues (Racha)"),
            (nay, Decimal("80.00"), Decimal("22.50"), "Monthly dues (Nay)"),
        ]
        for player, amount_due, amount_paid, desc in specs:
            rec, _ = PlayerFeeRecord.objects.update_or_create(
                club=club,
                player=player,
                team=team,
                billing_period_start=period_start,
                defaults={
                    "description": desc,
                    "amount_due": amount_due,
                    "amount_paid": amount_paid,
                    "currency": "USD",
                    "due_date": due_date,
                },
            )
            FeePaymentLedgerEntry.objects.filter(fee_record=rec).delete()
            if amount_paid > 0:
                entry = FeePaymentLedgerEntry.objects.create(
                    fee_record=rec,
                    amount=amount_paid,
                    note="Sprint 1 demo ledger entry",
                )
                FeePaymentLedgerEntry.objects.filter(pk=entry.pk).update(recorded_at=timezone.now())

        if (
            DirectorPaymentAuditLog.objects.filter(
                club=club,
                detail="Sprint1 demo: materialized fee lines for director dashboard.",
            ).count()
            == 0
        ):
            DirectorPaymentAuditLog.objects.create(
                club=club,
                actor=director_user,
                action=DirectorPaymentAuditLog.Action.FEE_CREATED,
                detail="Sprint1 demo: materialized fee lines for director dashboard.",
            )
        if (
            DirectorPaymentAuditLog.objects.filter(
                club=club,
                detail="Sprint1 demo: recorded demo ledger payments.",
            ).count()
            == 0
        ):
            DirectorPaymentAuditLog.objects.create(
                club=club,
                actor=director_user,
                action=DirectorPaymentAuditLog.Action.PAYMENT_RECORDED,
                detail="Sprint1 demo: recorded demo ledger payments.",
            )

    def _seed_nahda_low_attendance(self, team, karma_player):
        """Second-team roster + past sessions with no confirmations → low club-wide participation signal."""
        TeamMembership.objects.add_member(user=karma_player, team=team, role=TeamRole.PLAYER)
        today = timezone.localdate()
        for off in (26, 21, 16, 11, 6):
            session_date = today - timedelta(days=off)
            exists = TrainingSession.objects.filter(
                team=team,
                scheduled_date=session_date,
                title="Nahda development (demo)",
            ).exists()
            if exists:
                continue
            TrainingSession.objects.create(
                team=team,
                title="Nahda development (demo)",
                session_type=TrainingSession.SessionType.TRAINING,
                scheduled_date=session_date,
                start_time=time(17, 0),
                end_time=time(18, 30),
                location="Nahda training hall",
                status=TrainingSession.Status.SCHEDULED,
            )


def date_from_year(year):
    return date(year, 6, 15)
