"""
Sprint 1 / EP-26 demo data: clubs, teams, users (Tayma, Lyn, Karma, Racha, Farouk, Nay),
training sessions over time, and mixed attendance confirmations.

Run from backend/: python manage.py seed_sprint1_demo

Default login password for all seeded accounts: Sprint1Demo123!
"""

from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.core.models import (
    AssignedAccountRole,
    Club,
    ParentPlayerRelation,
    PlayerProfile,
    Team,
    TeamMembership,
    TeamRole,
    TrainingSession,
    TrainingSessionConfirmation,
    VerificationStatus,
)

User = get_user_model()

DEMO_PASSWORD = "Sprint1Demo123!"

CLUB_NAMES = ("Riyadi", "Nahda", "CPF", "AUB")


class Command(BaseCommand):
    help = "Seed realistic clubs, teams, users, and training attendance for local EP-26 testing."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Recreate training sessions and confirmations even if demo users already exist.",
        )

    def handle(self, *args, **options):
        force = options["force"]
        with transaction.atomic():
            director = self._ensure_user(
                email="demo.director@sprint1.local",
                first_name="Club",
                last_name="Director",
                assigned_account_role=AssignedAccountRole.DIRECTOR,
            )
            clubs = {}
            for name in CLUB_NAMES:
                club = Club.objects.filter(name=name).first()
                if club is None:
                    club = Club.objects.create_club(name=name, director=director)
                    self.stdout.write(self.style.SUCCESS(f"Created club {name} (id={club.id})"))
                clubs[name] = club

            tayma = self._ensure_user(
                email="tayma.parent@sprint1.local",
                first_name="Tayma",
                last_name="Merhebi",
                assigned_account_role=AssignedAccountRole.PARENT,
                date_of_birth=date_from_year(1985),
            )
            lyn = self._ensure_user(
                email="lyn.coach@sprint1.local",
                first_name="Lyn",
                last_name="Coach",
                assigned_account_role=AssignedAccountRole.COACH,
                date_of_birth=date_from_year(1990),
            )
            karma = self._ensure_user(
                email="karma.player@sprint1.local",
                first_name="Karma",
                last_name="Player",
                assigned_account_role=AssignedAccountRole.PLAYER,
                date_of_birth=date_from_year(2012),
            )
            racha = self._ensure_user(
                email="racha.player@sprint1.local",
                first_name="Racha",
                last_name="Player",
                assigned_account_role=AssignedAccountRole.PLAYER,
                date_of_birth=date_from_year(2006),
            )
            nay = self._ensure_user(
                email="nay.player@sprint1.local",
                first_name="Nay",
                last_name="Player",
                assigned_account_role=AssignedAccountRole.PLAYER,
                date_of_birth=date_from_year(2008),
            )
            farouk = self._ensure_user(
                email="farouk.coach@sprint1.local",
                first_name="Farouk",
                last_name="Coach",
                assigned_account_role=AssignedAccountRole.COACH,
                date_of_birth=date_from_year(1988),
            )

            ParentPlayerRelation.objects.link(parent=tayma, player=karma)

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
                TrainingSessionConfirmation.objects.filter(training_session__team=team_riyadi).delete()
                TrainingSession.objects.filter(team=team_riyadi).delete()

            if not TrainingSession.objects.filter(team=team_riyadi).exists() or force:
                self._seed_riyadi_sessions(team_riyadi, karma, racha, nay, tayma)
                self.stdout.write(self.style.SUCCESS("Seeded Riyadi U16 training sessions and confirmations."))

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Log in as lyn.coach@sprint1.local / {DEMO_PASSWORD} (coach) or "
                f"tayma.parent@sprint1.local (parent of Karma). Team id for Riyadi U16: {team_riyadi.id}."
            )
        )

    def _ensure_user(self, *, email, first_name, last_name, assigned_account_role, date_of_birth=None):
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "first_name": first_name,
                "last_name": last_name,
                "assigned_account_role": assigned_account_role,
                "verification_status": VerificationStatus.VERIFIED,
                "date_of_birth": date_of_birth,
            },
        )
        if not created:
            user.first_name = first_name
            user.last_name = last_name
            user.assigned_account_role = assigned_account_role
            user.verification_status = VerificationStatus.VERIFIED
            if date_of_birth is not None:
                user.date_of_birth = date_of_birth
            user.save(
                update_fields=[
                    "first_name",
                    "last_name",
                    "assigned_account_role",
                    "verification_status",
                    "date_of_birth",
                ]
            )
        user.set_password(DEMO_PASSWORD)
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

    def _seed_riyadi_sessions(self, team, karma, racha, nay, tayma):
        today = timezone.localdate()
        # Eight past sessions (weekly), one today (pending if no confirm), one future (pending)
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

        today_session = TrainingSession.objects.create(
            team=team,
            title="Practice (today)",
            session_type=TrainingSession.SessionType.TRAINING,
            scheduled_date=today,
            start_time=time(18, 0),
            end_time=time(19, 30),
            location="Main gym",
        )
        future_session = TrainingSession.objects.create(
            team=team,
            title="Practice (upcoming)",
            session_type=TrainingSession.SessionType.TRAINING,
            scheduled_date=today + timedelta(days=5),
            start_time=time(18, 0),
            end_time=time(19, 30),
            location="Arena B",
        )

        cancelled = TrainingSession.objects.create(
            team=team,
            title="Cancelled scrimmage (ignored in analytics)",
            session_type=TrainingSession.SessionType.TRAINING,
            scheduled_date=today - timedelta(days=10),
            start_time=time(16, 0),
            end_time=time(17, 30),
            status=TrainingSession.Status.CANCELLED,
        )

        def confirm(sess, player, by_user):
            TrainingSessionConfirmation.objects.update_or_create(
                training_session=sess,
                player=player,
                defaults={"confirmed_by": by_user},
            )

        # Racha: high attendance — confirmed all past sessions (self, 18+)
        for s in sessions:
            confirm(s, racha, racha)

        # Nay: medium — every other past session
        for idx, s in enumerate(sessions):
            if idx % 2 == 0:
                confirm(s, nay, nay)

        # Karma: low — parent confirms 2 of 8
        confirm(sessions[0], karma, tayma)
        confirm(sessions[2], karma, tayma)

        # One session with early confirmations for everyone on a future slot (optional)
        confirm(future_session, racha, racha)
        confirm(future_session, nay, nay)

        self.stdout.write(f"Also created today session id={today_session.id}, future id={future_session.id}, cancelled id={cancelled.id}.")


def date_from_year(year):
    return date(year, 6, 15)
