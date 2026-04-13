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
