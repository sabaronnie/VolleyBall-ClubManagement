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
"""

from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.core.models import (
    Club,
    ClubMembership,
    CoachFeedbackStatus,
    ParentPlayerRelation,
    PlayerProfile,
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

    def handle(self, *args, **options):
        force = options["force"]
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
            self._ensure_team(clubs["Nahda"], "Nahda Development")
            self._ensure_team(clubs["AUB"], "AUB Academy")

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
                TrainingSessionConfirmation.objects.filter(training_session__team=team_riyadi).delete()
                TrainingSession.objects.filter(team=team_riyadi).delete()

            if not TrainingSession.objects.filter(team=team_riyadi).exists() or force:
                self._seed_riyadi_sessions_and_dashboard(team_riyadi, karma, racha, nay, tayma, lyn)
                self.stdout.write(
                    self.style.SUCCESS(
                        "Seeded Riyadi U16 sessions, attendance, skill metrics, roster stats, and feedback."
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Log in as lyn.coach@sprint1.local / {DEMO_PASSWORD} (coach) or "
                f"tayma.parent@sprint1.local (parent of Karma and Racha) or "
                f"taymamerhebi@gmail.com / taymamerhebi (director). "
                f"Team id for Riyadi U16: {team_riyadi.id}."
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

        past_offsets = [56, 49, 42, 35, 28, 21, 14, 7]
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


def date_from_year(year):
    return date(year, 6, 15)
