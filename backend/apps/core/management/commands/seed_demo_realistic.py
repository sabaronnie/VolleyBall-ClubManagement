"""
Full realistic demo database seed for end-to-end feature verification.

Usage:
  python manage.py seed_demo_realistic
  python manage.py seed_demo_realistic --reset-demo-data   # delete demo clubs and rebuild

All demo-tagged schedule rows and tournaments use the \"DEMO |\" title/name prefix
so a normal re-run purges and recreates dynamic data idempotently.
"""
from __future__ import annotations

import random
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.core.models import (
    AuditLog,
    Club,
    ClubMembership,
    DirectorPaymentAuditLog,
    FeePaymentLedgerEntry,
    MatchPlayerStat,
    ParentPlayerRelation,
    PaymentSchedule,
    PlayerFeeRecord,
    PlayerProfile,
    PlayerWeeklySkillMetric,
    Pool,
    Standing,
    Team,
    TeamCoachFeedback,
    TeamMembership,
    TeamRole,
    TeamRosterPlayerStat,
    TeamScheduleEntry,
    TeamSkillCategory,
    TeamSkillDashboardMetric,
    Tournament,
    TournamentMatch,
    TournamentTeam,
    TrainingSession,
    TrainingSessionConfirmation,
    VerificationStatus,
)
from apps.core.services.audit_log_service import AuditLogService
from apps.core.services.tournament_calendar_service import sync_all_matches_in_tournament
from apps.core.tournament_views import _recalculate_pool_standings

User = get_user_model()

SEED_PASSWORD = "Password123!"
DEMO_PREFIX = "DEMO |"
DEMO_CLUBS = ("AUB", "CPF", "LAK", "LAU")
RANDOM_SEED = 20260427

# Key personas (Gmail, per request)
KEY_EMAILS = {
    "tayma": "tayma@gmail.com",
    "racha": "racha@gmail.com",
    "karma": "karma@gmail.com",
    "nay": "nay@gmail.com",
}
# Karmas primary team: first club + first girls youth template (set after TEAM_SPECS is defined)
# Karma plays on: AUB U18 Girls; Nay coaches that team. Tayma directs AUB only; other clubs have their own director.

# Leaner team set per club: (display suffix, age_group, gender, short template id)
TEAM_SPECS: tuple[tuple[str, str, str, str], ...] = (
    ("U18 Girls", "U18", Team.Gender.GIRLS, "u18g"),
    ("U18 Boys", "U18", Team.Gender.BOYS, "u18b"),
    ("U16 Girls", "U16", Team.Gender.GIRLS, "u16g"),
    ("U16 Boys", "U16", Team.Gender.BOYS, "u16b"),
)

# Session volume
MATCHES_PAST_PER_TEAM = 8
KARMA_EXTRA_LEAGUE_MATCHES = 4
TRAININGS_PAST = 6
FUTURE_TRAININGS = 1
FUTURE_MATCHES = 2
WEEKS_SKILL = 16

LEBANESE_FIRST = (
    "Ali", "Maya", "Jad", "Nour", "Rita", "Yara", "Karim", "Samar", "Nadine", "Elie",
    "Zeina", "Tarek", "Diana", "Fadi", "Mira", "Hadi", "Rami", "Lea", "Lina", "Joelle",
    "Ziad", "Rana", "Sami", "Lynn", "Charbel", "Celine", "Rawan", "Tony", "Aline", "Bilal",
)
LEBANESE_LAST = (
    "Khoury", "Haddad", "Nassar", "Helou", "AbiRached", "Mouawad", "Sfeir", "Salameh", "Khalil",
    "Mansour", "Zein", "Shami", "Aoun", "Karam", "Bitar", "Nehme", "Ghanem", "Saba", "Dagher",
    "Kfoury",
)
POSITIONS = ("Setter", "Outside Hitter", "Middle Blocker", "Opposite", "Libero")


def _d(*parts: str) -> str:
    return DEMO_PREFIX + " ".join(parts)


class Command(BaseCommand):
    help = "Realistic end-to-end demo data (clubs, rosters, attendance, performance, fees, tournaments)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset-demo-data",
            action="store_true",
            help="Delete demo clubs (AUB, CPF, LAK, LAU) and all cascaded data, then re-seed from scratch.",
        )

    @transaction.atomic()
    def handle(self, *args: Any, **options: Any) -> None:
        self._rng = random.Random(RANDOM_SEED)
        reset = bool(options.get("reset_demo_data"))

        if reset:
            self._delete_demo_clubs()
        else:
            self._purge_dynamic_demo_data()

        ctx = self._seed_foundation()
        self._seed_schedules_and_performance(ctx)
        self._seed_financials(ctx)
        t_stats = self._seed_tournaments(ctx)
        self._seed_audit_trail(ctx, t_stats)

        counts = self._collect_counts()
        self._print_report(counts, t_stats)

    # --- reset / idempotency ---

    def _delete_demo_clubs(self) -> None:
        deleted, _ = Club.objects.filter(name__in=DEMO_CLUBS).delete()
        self.stdout.write(self.style.WARNING(f"Removed prior demo clubs and cascaded data (rows affected: {deleted})."))

    def _purge_dynamic_demo_data(self) -> None:
        """Re-run safe path: keep clubs/users, remove earlier DEMO| sessions/tournaments and metrics."""
        club_qs = Club.objects.filter(name__in=DEMO_CLUBS)
        if not club_qs.exists():
            return
        team_qs = Team.objects.filter(club__in=club_qs)
        # Delete tournaments tagged DEMO |
        Tournament.objects.filter(club__in=club_qs, name__startswith=DEMO_PREFIX).delete()
        # League/training/match sessions we created
        TrainingSession.objects.filter(
            Q(title__startswith=DEMO_PREFIX) | Q(notes__icontains="Seeded"),
            team__in=team_qs,
        ).delete()
        TeamSkillDashboardMetric.objects.filter(team__in=team_qs).delete()
        TeamRosterPlayerStat.objects.filter(team__in=team_qs).delete()
        TeamCoachFeedback.objects.filter(team__in=team_qs).delete()
        PlayerWeeklySkillMetric.objects.filter(team__in=team_qs).delete()
        PlayerFeeRecord.objects.filter(club__in=club_qs, description__startswith="DEMO").delete()
        PaymentSchedule.objects.filter(club__in=club_qs, description__startswith="DEMO").delete()
        DirectorPaymentAuditLog.objects.filter(club__in=club_qs, detail__startswith="DEMO").delete()
        # Notifications referencing deleted sessions would cascade; optional cleanup
        from apps.core.models import Notification
        Notification.objects.filter(team__in=team_qs, title__startswith=DEMO_PREFIX).delete()

    # --- main seed steps ---

    def _seed_foundation(self) -> dict:
        key = self._seed_key_users()
        directors = self._seed_club_directors()
        all_users: dict[str, User] = {**key, **directors}
        clubs: dict[str, Club] = {}
        for code, director in [("AUB", key["tayma"]), ("CPF", directors["cpf_dir"]), ("LAK", directors["lak_dir"]), ("LAU", directors["lau_dir"])]:
            club = Club.objects.filter(name=code).first()
            if club is None:
                club = Club.objects.create_club(name=code, director=director)
            else:
                ClubMembership.objects.assign_director(user=director, club=club)
            club.short_name = code
            club.description = f"{DEMO_PREFIX} {code} — Lebanese club volleyball (demo)."
            club.country = "Lebanon"
            club.city = {"AUB": "Beirut", "CPF": "Jounieh", "LAK": "Baabda", "LAU": "Jbeil"}.get(code, "Beirut")
            club.default_monthly_player_fee = Decimal("75.00")
            club.save()
            clubs[code] = club

        teams, team_index = self._seed_teams(clubs)
        coaches, parents, players_ledger = self._seed_memberships(teams, key, all_users)
        self._link_parents(parents, players_ledger, key)
        self._seed_player_profiles(players_ledger["all"])
        return {
            "key": key,
            "directors": directors,
            "clubs": clubs,
            "teams": teams,
            "team_index": team_index,
            "coaches": coaches,
            "parents": parents,
            "players_ledger": players_ledger,
        }

    def _upsert_user(
        self,
        *,
        email: str,
        first_name: str,
        last_name: str,
        dob: date,
    ) -> User:
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
        user.save(
            update_fields=["first_name", "last_name", "date_of_birth", "verification_status", "password"]
        )
        return user

    def _seed_key_users(self) -> dict:
        return {
            "tayma": self._upsert_user(
                email=KEY_EMAILS["tayma"],
                first_name="Tayma",
                last_name="Merhebi",
                dob=date(1988, 7, 14),
            ),
            "racha": self._upsert_user(
                email=KEY_EMAILS["racha"],
                first_name="Racha",
                last_name="Haddad",
                dob=date(1986, 3, 25),
            ),
            "karma": self._upsert_user(
                email=KEY_EMAILS["karma"],
                first_name="Karma",
                last_name="Merhebi",
                dob=date(2009, 5, 18),
            ),
            "nay": self._upsert_user(
                email=KEY_EMAILS["nay"],
                first_name="Nay",
                last_name="El Khoury",
                dob=date(1992, 11, 2),
            ),
        }

    def _seed_club_directors(self) -> dict:
        return {
            "cpf_dir": self._upsert_user(
                email="cpf.director@gmail.com", first_name="Maya", last_name="Directeur", dob=date(1985, 1, 12)
            ),
            "lak_dir": self._upsert_user(
                email="lak.director@gmail.com", first_name="Karim", last_name="Directeur", dob=date(1984, 6, 2)
            ),
            "lau_dir": self._upsert_user(
                email="lau.director@gmail.com", first_name="Nadine", last_name="Directeur", dob=date(1983, 9, 19)
            ),
        }

    def _seed_teams(self, clubs: dict[str, Club]) -> tuple[dict[str, Team], dict[str, dict[str, Team]]]:
        """Returns flat team dict keyed by 'AUB U18 Girls' and nested team_index[code][slot]."""
        teams: dict[str, Team] = {}
        by_club: dict[str, dict[str, Team]] = {c: {} for c in clubs}
        for code, club in clubs.items():
            for label, age, gender, slot in TEAM_SPECS:
                name = f"{code} {label}"
                t, _ = Team.objects.get_or_create(club=club, name=name)
                t.short_name = f"{code}-{label.replace(' ', '')}"
                t.age_group = age
                t.gender = gender
                t.season = "2025-26"
                t.status = Team.Status.ACTIVE
                t.home_venue = f"{code} Volleyball Center — {age} {gender}"
                t.description = f"{DEMO_PREFIX} {name} roster, schedule, and finances."
                t.save()
                teams[name] = t
                by_club[code][slot] = t
        return teams, by_club

    def _seed_memberships(
        self,
        teams: dict[str, Team],
        key: dict,
        all_directors: dict,
    ) -> tuple[dict, list[User], dict]:
        coaches: dict[int, User] = {}
        parents: list[User] = []
        for code in DEMO_CLUBS:
            for i in range(2):
                p = self._upsert_user(
                    email=f"parent.{code.lower()}.{i + 1}@gmail.com",
                    first_name=LEBANESE_FIRST[(i + 7) % len(LEBANESE_FIRST)],
                    last_name=LEBANESE_LAST[(i + 3) % len(LEBANESE_LAST)] + " (Parent)",
                    dob=date(1982 + (i % 6), 4, 10 + i),
                )
                parents.append(p)
        aub_girls = teams["AUB U18 Girls"]
        TeamMembership.objects.add_member(user=key["nay"], team=aub_girls, role=TeamRole.COACH)
        coaches[aub_girls.id] = key["nay"]
        n_player = 0
        club_coaches: dict[str, tuple[User, User]] = {}
        for code in DEMO_CLUBS:
            c1 = self._upsert_user(
                email=f"coach.{code.lower()}.1@gmail.com",
                first_name=LEBANESE_FIRST[(2 + n_player) % len(LEBANESE_FIRST)],
                last_name=f"Coach{code}",
                dob=date(1991 + (n_player % 5), 3, 6 + n_player),
            )
            c2 = self._upsert_user(
                email=f"coach.{code.lower()}.2@gmail.com",
                first_name=LEBANESE_FIRST[(7 + n_player) % len(LEBANESE_FIRST)],
                last_name=f"Coach{code}",
                dob=date(1990 + (n_player % 5), 5, 10 + n_player),
            )
            n_player += 1
            club_coaches[code] = (c1, c2)
            for spec_idx, spec in enumerate(TEAM_SPECS):
                label, _age, _g, _slot_id = spec
                tname = f"{code} {label}"
                team = teams[tname]
                if team.id in coaches:
                    continue
                c = club_coaches[code][spec_idx % 2]
                TeamMembership.objects.add_member(user=c, team=team, role=TeamRole.COACH)
                coaches[team.id] = c
        n_player = 0
        for code in DEMO_CLUBS:
            for spec in TEAM_SPECS:
                team = teams[f"{code} {spec[0]}"]
                for slot in range(6):
                    n_player += 1
                    is_karma = code == "AUB" and spec[0] == "U18 Girls" and slot == 0
                    if is_karma:
                        u = key["karma"]
                    else:
                        u = self._upsert_user(
                            email=f"player.{code.lower()}.{spec[3]}.{slot + 1}@gmail.com",
                            first_name=LEBANESE_FIRST[n_player % len(LEBANESE_FIRST)],
                            last_name=LEBANESE_LAST[(n_player * 2) % len(LEBANESE_LAST)],
                            dob=date(
                                2010
                                - (0 if "U18" in spec[0] else 2 if "U16" in spec[0] else 4),
                                (n_player % 12) + 1,
                                (n_player % 27) + 1,
                            ),
                        )
                    role_capt = slot == 0
                    TeamMembership.objects.add_member(
                        user=u, team=team, role=TeamRole.PLAYER, is_captain=role_capt
                    )
        all_p: list[User] = []
        for t in teams.values():
            for m in (
                TeamMembership.objects.filter(team=t, role=TeamRole.PLAYER, is_active=True)
                .select_related("user")
                .order_by("id")
            ):
                all_p.append(m.user)
        return coaches, parents, {
            "all": all_p,
            "aub_u18_girls": [m.user for m in TeamMembership.objects.filter(team=aub_girls, role=TeamRole.PLAYER)],
        }

    def _link_parents(self, parents: list[User], ledger: dict, key: dict) -> None:
        ParentPlayerRelation.objects.link(
            parent=key["racha"],
            player=key["karma"],
            is_legal_guardian=True,
        )
        girls = Team.objects.get(club__name="AUB", name="AUB U18 Girls")
        for m in TeamMembership.objects.filter(team=girls, role=TeamRole.PLAYER).select_related("user"):
            pl = m.user
            pr = parents[(pl.id or 0) % len(parents)]
            if pl.id == key["karma"].id:
                continue
            try:
                ParentPlayerRelation.objects.link(parent=pr, player=pl, is_legal_guardian=bool(pl.id % 2 == 0))
            except Exception:
                pass
        n = 0
        for t in Team.objects.filter(club__name__in=DEMO_CLUBS).exclude(name="AUB U18 Girls"):
            for m in TeamMembership.objects.filter(team=t, role=TeamRole.PLAYER)[:6]:
                pr = parents[n % len(parents)]
                n += 1
                try:
                    ParentPlayerRelation.objects.link(
                        parent=pr,
                        player=m.user,
                        is_legal_guardian=bool(n % 3 == 0),
                    )
                except Exception:
                    pass

    def _seed_player_profiles(self, players: list) -> None:
        for i, p in enumerate(players, start=1):
            note = f"{DEMO_PREFIX} Roster / analytics demo profile"
            if p.email == KEY_EMAILS["karma"]:
                note = f"{DEMO_PREFIX} Professor demo: primary showcase player (progress + fees)."
            PlayerProfile.objects.update_or_create(
                user=p,
                defaults={
                    "jersey_number": (i % 20) + 1,
                    "primary_position": POSITIONS[i % len(POSITIONS)],
                    "notes": note,
                },
            )

    def _seed_schedules_and_performance(self, ctx: dict) -> None:
        teams: dict = ctx["teams"]
        coaches: dict = ctx["coaches"]
        key = ctx["key"]
        today = timezone.localdate()
        monday = today - timedelta(days=today.weekday())
        tz = timezone.get_current_timezone()
        tlist = list(teams.values())
        for t_idx, team in enumerate(teams.values()):
            coach = coaches.get(team.id) or key["nay"]
            roster = [m.user for m in TeamMembership.objects.filter(team=team, role=TeamRole.PLAYER, is_active=True).select_related("user").order_by("id")]
            TeamScheduleEntry.objects.update_or_create(
                team=team,
                activity_name="Technical + Systems",
                weekday=t_idx % 6,
                defaults={
                    "start_time": time(18, 0),
                    "end_time": time(19, 30),
                    "location": team.home_venue,
                    "created_by": coach,
                },
            )
            for tr in range(TRAININGS_PAST):
                s_date = today - timedelta(days=4 + 7 * tr + (t_idx % 3))
                ts, _ = TrainingSession.objects.get_or_create(
                    team=team,
                    title=_d(f"{team.short_name} Training {tr + 1}"),
                    scheduled_date=s_date,
                    defaults={
                        "session_type": TrainingSession.SessionType.TRAINING,
                        "start_time": time(18, 0),
                        "end_time": time(19, 30),
                        "location": team.home_venue,
                        "created_by": coach,
                    },
                )
                for pi, pl in enumerate(roster):
                    if s_date < today:
                        if tr % 4 == 0 and pi in (0, 1) and s_date < today:
                            continue
                        if (tr + pi) % 3 == 0 and s_date < today:
                            TrainingSessionConfirmation.objects.update_or_create(
                                training_session=ts, player=pl, defaults={"confirmed_by": pl}
                            )
                        else:
                            pass
            for mi in range(1, MATCHES_PAST_PER_TEAM + 1):
                s_date = today - timedelta(days=4 + 6 * mi + (t_idx % 4))
                others = [x for x in tlist if x.id != team.id and x.club_id == team.club_id]
                if not others:
                    others = [x for x in tlist if x.id != team.id]
                opp = others[(mi + team.id) % len(others)]
                title = _d(f"League R{mi} — vs {opp.name}")
                m_end = timezone.make_aware(datetime.combine(s_date, time(21, 0)), tz)
                ppts: list[tuple[User, int]] = []
                for pi, pl in enumerate(roster, start=1):
                    base = 4 + (mi % 5) + self._rng.randint(0, 6) + (2 if pl.email == KEY_EMAILS["karma"] else 0) + (2 if pi <= 2 else 0)
                    ppts.append((pl, min(28, max(0, base))))
                our_sum = sum(p for _u, p in ppts)
                opp_total = max(40, our_sum + self._rng.randint(-12, 14) + (4 if mi % 8 == 0 else 0))
                sess = TrainingSession.objects.create(
                    team=team,
                    title=title,
                    session_type=TrainingSession.SessionType.MATCH,
                    scheduled_date=s_date,
                    start_time=time(19, 0),
                    end_time=time(20, 45),
                    location=team.home_venue,
                    opponent=opp.name,
                    opponent_team=opp,
                    opponent_final_score=opp_total,
                    match_type=TrainingSession.MatchType.LEAGUE,
                    match_request_status=TrainingSession.MatchRequestStatus.NONE,
                    created_by=coach,
                    match_ended_at=m_end,
                    status=TrainingSession.Status.SCHEDULED,
                    notes="Seeded coach match with roster stats; opponent score line in opponent_final_score.",
                )
                for pl, pts in ppts:
                    MatchPlayerStat.objects.create(
                        training_session=sess,
                        player=pl,
                        points_scored=pts,
                        aces=self._rng.randint(0, 5),
                        blocks=self._rng.randint(0, 4),
                        assists=self._rng.randint(0, 10),
                        errors=self._rng.randint(0, 4),
                        digs=self._rng.randint(1, 14),
                        updated_by=coach,
                    )
            for ex in range(KARMA_EXTRA_LEAGUE_MATCHES):
                if team.name != "AUB U18 Girls":
                    break
                s2 = today - timedelta(days=2 + ex * 2)
                o2 = tlist[(t_idx + ex + 3) % len(tlist)]
                if o2.id == team.id:
                    o2 = tlist[1]
                s = TrainingSession.objects.create(
                    team=team,
                    title=_d(f"Karma focus scrimmage {ex + 1} — vs {o2.name}"),
                    session_type=TrainingSession.SessionType.MATCH,
                    match_type=TrainingSession.MatchType.SCRIMMAGE,
                    scheduled_date=s2,
                    start_time=time(10, 0),
                    end_time=time(11, 30),
                    location=team.home_venue,
                    opponent=o2.name,
                    opponent_team=o2,
                    opponent_final_score=55 + ex,
                    created_by=coaches[team.id],
                    match_ended_at=timezone.make_aware(datetime.combine(s2, time(11, 45)), tz),
                )
                k = key["karma"]
                pval = 12 + ex + self._rng.randint(0, 3)
                MatchPlayerStat.objects.create(
                    training_session=s,
                    player=k,
                    points_scored=pval,
                    aces=1 + (ex % 2),
                    blocks=ex % 3,
                    assists=2 + (ex % 4),
                    errors=0 if ex < 3 else 1,
                    digs=5 + ex,
                    updated_by=coaches[team.id],
                )
            for fu in range(FUTURE_TRAININGS):
                TrainingSession.objects.get_or_create(
                    team=team,
                    title=_d(f"Upcoming practice {fu + 1}"),
                    scheduled_date=today + timedelta(days=2 + 4 * fu + t_idx % 2),
                    defaults={
                        "session_type": TrainingSession.SessionType.TRAINING,
                        "start_time": time(18, 0),
                        "end_time": time(19, 20),
                        "location": team.home_venue,
                        "created_by": coach,
                    },
                )
            for fu in range(FUTURE_MATCHES):
                o3 = tlist[(t_idx + fu) % len(tlist)]
                if o3.id == team.id:
                    o3 = tlist[(t_idx + fu + 1) % len(tlist)]
                TrainingSession.objects.get_or_create(
                    team=team,
                    title=_d(f"Upcoming league — vs {o3.name}"),
                    scheduled_date=today + timedelta(days=3 + 7 * fu),
                    defaults={
                        "session_type": TrainingSession.SessionType.MATCH,
                        "start_time": time(19, 0),
                        "end_time": time(21, 0),
                        "location": team.home_venue,
                        "opponent": o3.name,
                        "opponent_team": o3,
                        "match_type": TrainingSession.MatchType.LEAGUE,
                        "created_by": coach,
                    },
                )
        for idx, team in enumerate(teams.values()):
            co = coaches.get(team.id) or key["nay"]
            ro = [m.user for m in TeamMembership.objects.filter(team=team, role=TeamRole.PLAYER, is_active=True).select_related("user")]
            for cat, _ in TeamSkillCategory.choices:
                TeamSkillDashboardMetric.objects.update_or_create(
                    team=team,
                    skill_category=cat,
                    defaults={
                        "attendance_rate": Decimal(str(round(self._rng.uniform(70.0, 96.0), 2))),
                        "average_performance": Decimal(str(round(self._rng.uniform(62.0, 91.0), 2))),
                    },
                )
            for p_idx, pl in enumerate(ro, start=1):
                s_pct = Decimal(str(round(self._rng.uniform(60.0, 94.0), 2)))
                TeamRosterPlayerStat.objects.update_or_create(
                    team=team,
                    player=pl,
                    defaults={
                        "spikes": self._rng.randint(20, 85),
                        "blocks": self._rng.randint(6, 40),
                        "serve_percentage": s_pct,
                        "prior_serve_percentage": Decimal(str(max(float(s_pct) - self._rng.uniform(0.2, 4.0), 45.0))),
                    },
                )
                for wb in range(WEEKS_SKILL):
                    ws = monday - timedelta(weeks=wb)
                    base = 56 + p_idx + (1 if pl.email == KEY_EMAILS["karma"] else 0)
                    g = (WEEKS_SKILL - 1 - wb) * 0.15 * (1.0 if pl.email == KEY_EMAILS["karma"] else 0.08)
                    PlayerWeeklySkillMetric.objects.update_or_create(
                        player=pl,
                        team=team,
                        week_start=ws,
                        defaults={
                            "attack": Decimal(
                                str(round(min(99, base + g * 30 + self._rng.uniform(-2, 4)), 2))
                            ),
                            "defense": Decimal(
                                str(round(min(99, base + g * 28 + self._rng.uniform(-3, 3)), 2))
                            ),
                            "serve": Decimal(
                                str(round(min(99, base + g * 32 + self._rng.uniform(-2, 5)), 2))
                            ),
                        },
                    )
                if p_idx <= 2 and team.name == "AUB U18 Girls":
                    TeamCoachFeedback.objects.get_or_create(
                        team=team,
                        player=pl,
                        coach=co,
                        body=f"{DEMO_PREFIX} Work serve-receive first contact; good leadership in set 2.",
                    )

    def _seed_financials(self, ctx: dict) -> None:
        clubs: dict = ctx["clubs"]
        key = ctx["key"]
        teams = ctx["teams"]
        for code, cl in clubs.items():
            dmap = {
                "AUB": key["tayma"],
                "CPF": ctx["directors"]["cpf_dir"],
                "LAK": ctx["directors"]["lak_dir"],
                "LAU": ctx["directors"]["lau_dir"],
            }[code]
            ps, _ = PaymentSchedule.objects.get_or_create(
                club=cl,
                description="DEMO: Monthly training & facility",
                start_date=date.today().replace(day=1) - timedelta(days=60),
                defaults={
                    "scope": PaymentSchedule.Scope.CLUB,
                    "frequency": PaymentSchedule.Frequency.MONTHLY,
                    "amount": Decimal("75.00"),
                    "currency": "USD",
                    "is_active": True,
                    "created_by": dmap,
                },
            )
            ps.amount = Decimal("75.00")
            ps.frequency = PaymentSchedule.Frequency.MONTHLY
            ps.is_active = True
            ps.save()
            m_count = 0
            for t in Team.objects.filter(club=cl):
                for m in TeamMembership.objects.filter(team=t, role=TeamRole.PLAYER).select_related("user"):
                    for month_off in (0, 1, 2):
                        b_start = (date.today().replace(day=1) - timedelta(days=30 * month_off)).replace(day=1)
                        amount = Decimal("75.00")
                        due = b_start + timedelta(days=20)
                        status_roll = (m.id + month_off) % 5
                        paid = Decimal("0.00")
                        paid_at = None
                        if status_roll in (0, 1, 4):
                            paid = amount
                            paid_at = timezone.now() - timedelta(days=5 * month_off)
                        elif status_roll == 2:
                            paid = Decimal("35.00")
                        elif status_roll == 3:
                            paid = Decimal("0.00")
                        fr, _ = PlayerFeeRecord.objects.update_or_create(
                            club=cl,
                            player=m.user,
                            team=t,
                            billing_period_start=b_start,
                            defaults={
                                "description": "DEMO: Monthly team fee",
                                "amount_due": amount,
                                "amount_paid": paid,
                                "due_date": due,
                                "currency": "USD",
                                "schedule": ps,
                                "paid_at": paid_at,
                                "schedule_occurrence_key": f"demo|{cl.id}|{m.user_id}|{b_start.isoformat()}",
                            },
                        )
                        if fr.amount_paid and fr.amount_paid > 0 and fr.amount_paid < fr.amount_due:
                            FeePaymentLedgerEntry.objects.get_or_create(
                                fee_record=fr,
                                amount=fr.amount_paid,
                                note="DEMO: partial",
                            )
                        m_count += 1
            DirectorPaymentAuditLog.objects.create(
                club=cl,
                actor=dmap,
                action=DirectorPaymentAuditLog.Action.MONTHLY_FEES_MATERIALIZED,
                detail="DEMO: materialized three billing periods for all roster players.",
            )

    def _seed_tournaments(self, ctx: dict) -> dict:
        cs = ctx["clubs"]
        teams = ctx["teams"]
        key = ctx["key"]
        stats: dict = defaultdict(int)
        tmap = {k: teams[k] for k in ("AUB U16 Girls", "AUB U18 Girls", "AUB U16 Boys", "AUB U18 Boys") if k in teams}
        self._tournament_aub_pool_only(ctx["clubs"]["AUB"], tmap, key, stats)
        c_teams = [teams[f"CPF {s[0]}"] for s in TEAM_SPECS[:4]]
        self._tournament_cpf_bracket(ctx["clubs"]["CPF"], c_teams, key, ctx["directors"]["cpf_dir"], stats)
        l_teams = [teams["LAK " + s[0]] for s in TEAM_SPECS if s[0] in ("U18 Girls", "U18 Boys", "U16 Girls", "U16 Boys")][:4]
        self._tournament_lak_hybrid(ctx["clubs"]["LAK"], l_teams, key, ctx["directors"]["lak_dir"], stats)
        la_teams = [teams["LAU " + s[0]] for s in TEAM_SPECS[:3]]
        self._tournament_lau_draft_in_progress(ctx["clubs"]["LAU"], la_teams, key, ctx["directors"]["lau_dir"], stats)
        return dict(stats)

    def _tournament_aub_pool_only(
        self,
        club: Club,
        team_by_key: dict,
        key,
        stats: dict,
    ) -> None:
        names = ["AUB U16 Girls", "AUB U18 Girls", "AUB U16 Boys", "AUB U18 Boys"]
        chosen = [team_by_key[k] for k in names if k in team_by_key]
        tourn, _ = Tournament.objects.update_or_create(
            club=club,
            name=f"{DEMO_PREFIX} AUB — Pool Play Cup",
            defaults={
                "created_by": key["tayma"],
                "tournament_type": Tournament.TournamentType.POOL_ONLY,
                "status": Tournament.Status.POOL_STAGE,
                "number_of_teams": 4,
                "pool_count": 1,
                "teams_per_pool": 4,
                "teams_qualifying_per_pool": 2,
                "start_date": timezone.localdate() - timedelta(days=10),
                "venue": "AUB Beirut — OSB Arena (demo)",
                "scoring_format": "3 pts win, 0 loss; PD tie-breaker",
            },
        )
        tourn.teams.set(chosen)
        TournamentTeam.objects.filter(tournament=tourn).delete()
        for s, te in enumerate(chosen, start=1):
            TournamentTeam.objects.create(tournament=tourn, team=te, seed=s, pool=None)
        Pool.objects.filter(tournament=tourn).delete()
        pool = Pool.objects.create(tournament=tourn, name="Pool A")
        for tteam in TournamentTeam.objects.filter(tournament=tourn).select_related("team"):
            tteam.pool = pool
            tteam.save(update_fields=["pool"])
            Standing.objects.get_or_create(
                tournament=tourn,
                pool=pool,
                team=tteam.team,
            )
        TournamentMatch.objects.filter(tournament=tourn).delete()
        mnum = 1
        pairs = [(0, 1), (2, 3), (0, 2), (1, 3), (0, 3), (1, 2)]
        for i, (a, b) in enumerate(pairs):
            ta, tb = chosen[a], chosen[b]
            sa, sb = 25, 20 + (i % 3)
            if i == 1:
                sa, sb = 22, 25
            comp = i < 4
            tw = None
            lw = None
            if comp:
                tw = ta if sa > sb else tb
                lw = tb if sa > sb else ta
            TournamentMatch.objects.create(
                tournament=tourn,
                pool=pool,
                match_number=mnum,
                team_a=ta,
                team_b=tb,
                team_a_score=sa if comp else None,
                team_b_score=sb if comp else None,
                winner_team=tw,
                loser_team=lw,
                status=TournamentMatch.MatchStatus.COMPLETED if comp else TournamentMatch.MatchStatus.SCHEDULED,
                scheduled_time=timezone.now() - timedelta(days=7 - i) if comp else timezone.now() + timedelta(days=3 + i),
                location="Court 1" if i % 2 == 0 else "Court 2",
            )
            mnum += 1
        _recalculate_pool_standings(tourn, pool)
        sync_all_matches_in_tournament(tourn.id)
        stats["tournaments"] += 1
        stats["tournament_matches"] += len(pairs)
        AuditLogService.log_action(
            user=key["tayma"],
            action_type="tournament_pools_games_seeded",
            entity_type="tournament",
            entity_id=tourn.id,
            new_value={"name": tourn.name, "pools": 1, "round_robin": len(pairs)},
        )

    def _tournament_cpf_bracket(
        self,
        club: Club,
        c_teams: list[Team],
        key,
        director: User,
        stats: dict,
    ) -> None:
        tourn, _ = Tournament.objects.update_or_create(
            club=club,
            name=f"{DEMO_PREFIX} CPF — Winter Knockout (Bracket)",
            defaults={
                "created_by": director,
                "tournament_type": Tournament.TournamentType.BRACKET_ONLY,
                "status": Tournament.Status.BRACKET_STAGE,
                "number_of_teams": 4,
                "pool_count": 0,
                "teams_per_pool": 0,
                "teams_qualifying_per_pool": 0,
                "start_date": timezone.localdate() - timedelta(days=2),
                "venue": "CPF Arena (demo)",
            },
        )
        tourn.teams.set(c_teams)
        TournamentTeam.objects.filter(tournament=tourn).delete()
        for s, te in enumerate(c_teams, start=1):
            TournamentTeam.objects.create(tournament=tourn, team=te, seed=s, pool=None)
        TournamentMatch.objects.filter(tournament=tourn).delete()
        t1, t2, t3, t4 = c_teams[0], c_teams[1], c_teams[2], c_teams[3]
        m1 = TournamentMatch.objects.create(
            tournament=tourn,
            pool=None,
            match_number=1,
            bracket_round="Semi-Final 1",
            team_a=t1,
            team_b=t4,
            team_a_score=25,
            team_b_score=20,
            winner_team=t1,
            loser_team=t4,
            status=TournamentMatch.MatchStatus.COMPLETED,
            scheduled_time=timezone.now() - timedelta(hours=8),
        )
        m2 = TournamentMatch.objects.create(
            tournament=tourn,
            pool=None,
            match_number=2,
            bracket_round="Semi-Final 2",
            team_a=t2,
            team_b=t3,
            team_a_score=23,
            team_b_score=25,
            winner_team=t3,
            loser_team=t2,
            status=TournamentMatch.MatchStatus.COMPLETED,
            scheduled_time=timezone.now() - timedelta(hours=6),
        )
        fin = TournamentMatch.objects.create(
            tournament=tourn,
            pool=None,
            match_number=3,
            bracket_round="Final",
            team_a=t1,
            team_b=t3,
            team_a_score=None,
            team_b_score=None,
            status=TournamentMatch.MatchStatus.SCHEDULED,
            scheduled_time=timezone.now() + timedelta(days=1),
        )
        m1.next_match = fin
        m1.next_match_slot = "A"
        m1.save(update_fields=["next_match", "next_match_slot", "updated_at"])
        m2.next_match = fin
        m2.next_match_slot = "B"
        m2.save(update_fields=["next_match", "next_match_slot", "updated_at"])
        sync_all_matches_in_tournament(tourn.id)
        stats["tournaments"] += 1
        stats["tournament_matches"] += 3
        AuditLogService.log_action(
            user=director,
            action_type="tournament_bracket_seeded",
            entity_type="tournament",
            entity_id=tourn.id,
            new_value={"name": tourn.name, "round": "Semi + Final (final pending)"},
        )

    def _tournament_lak_hybrid(
        self,
        club: Club,
        teams4: list[Team],
        key,
        director: User,
        stats: dict,
    ) -> None:
        tourn, _ = Tournament.objects.update_or_create(
            club=club,
            name=f"{DEMO_PREFIX} LAK — Spring Pool + Bracket",
            defaults={
                "created_by": director,
                "tournament_type": Tournament.TournamentType.POOL_AND_BRACKET,
                "status": Tournament.Status.POOL_STAGE,
                "number_of_teams": 4,
                "pool_count": 2,
                "teams_per_pool": 2,
                "teams_qualifying_per_pool": 1,
                "start_date": timezone.localdate() - timedelta(days=4),
                "venue": "LAK Sports Dome (demo)",
            },
        )
        tourn.teams.set(teams4)
        TournamentTeam.objects.filter(tournament=tourn).delete()
        Pool.objects.filter(tournament=tourn).delete()
        p1 = Pool.objects.create(tournament=tourn, name="Pool A")
        p2 = Pool.objects.create(tournament=tourn, name="Pool B")
        pools = (p1, p2)
        for s, te in enumerate(teams4, start=1):
            pool = pools[(s - 1) // 2]
            TournamentTeam.objects.create(tournament=tourn, team=te, seed=s, pool=pool)
            Standing.objects.get_or_create(tournament=tourn, pool=pool, team=te)
        pa = (teams4[0], teams4[1])
        pb = (teams4[2], teams4[3])
        mnum = 1
        for pool, pteams in ((p1, pa), (p2, pb)):
            ta, tb = pteams[0], pteams[1]
            a, b = 25, 22
            if pool.name == "Pool B":
                a, b = 20, 25
            tw = ta if a > b else tb
            lw = tb if a > b else ta
            TournamentMatch.objects.create(
                tournament=tourn,
                pool=pool,
                match_number=mnum,
                team_a=ta,
                team_b=tb,
                team_a_score=a,
                team_b_score=b,
                winner_team=tw,
                loser_team=lw,
                status=TournamentMatch.MatchStatus.COMPLETED,
                scheduled_time=timezone.now() - timedelta(hours=20 + mnum),
            )
            mnum += 1
        for pool in (p1, p2):
            _recalculate_pool_standings(tourn, pool)
        top_a = list(
            Standing.objects.filter(tournament=tourn, pool=p1)
            .order_by("-wins", "-points", "-point_difference", "-points_for", "id")
        )[0]
        top_b = list(
            Standing.objects.filter(tournament=tourn, pool=p2)
            .order_by("-wins", "-points", "-point_difference", "-points_for", "id")
        )[0]
        TournamentMatch.objects.create(
            tournament=tourn,
            pool=None,
            match_number=mnum,
            bracket_round="Championship",
            team_a=top_a.team,
            team_b=top_b.team,
            team_a_score=None,
            team_b_score=None,
            status=TournamentMatch.MatchStatus.SCHEDULED,
            scheduled_time=timezone.now() + timedelta(days=2),
        )
        tourn.status = Tournament.Status.BRACKET_STAGE
        tourn.save(update_fields=["status", "updated_at"])
        sync_all_matches_in_tournament(tourn.id)
        stats["tournaments"] += 1
        stats["tournament_matches"] += 3
        AuditLogService.log_action(
            user=director,
            action_type="tournament_hybrid_pools_bracket",
            entity_type="tournament",
            entity_id=tourn.id,
            new_value={"pools": 2, "championship": "pending"},
        )

    def _tournament_lau_draft_in_progress(
        self,
        club: Club,
        teams3: list[Team],
        key,
        director: User,
        stats: dict,
    ) -> None:
        tourn, _ = Tournament.objects.update_or_create(
            club=club,
            name=f"{DEMO_PREFIX} LAU — Intra-Club (Draft)",
            defaults={
                "created_by": director,
                "tournament_type": Tournament.TournamentType.POOL_ONLY,
                "status": Tournament.Status.DRAFT,
                "number_of_teams": 3,
                "pool_count": 1,
                "teams_per_pool": 3,
                "teams_qualifying_per_pool": 2,
                "start_date": timezone.localdate() + timedelta(days=14),
                "venue": "Byblos Campus (demo)",
            },
        )
        tourn.teams.set(teams3)
        TournamentTeam.objects.filter(tournament=tourn).delete()
        for s, te in enumerate(teams3, start=1):
            TournamentTeam.objects.create(tournament=tourn, team=te, seed=s, pool=None)
        stats["tournaments"] += 1
        stats["tournament_matches"] += 0
        AuditLogService.log_action(
            user=director,
            action_type="tournament_created",
            entity_type="tournament",
            entity_id=tourn.id,
            new_value={"name": tourn.name, "status": "DRAFT"},
        )

    def _seed_audit_trail(self, ctx: dict, t_stats: dict) -> None:
        key = ctx["key"]
        AuditLog.objects.create(
            user=key["nay"],
            user_role="coach",
            action_type="demo_attendance_confirmed",
            entity_type="training_session",
            entity_id="bulk",
            new_value={"note": f"{DEMO_PREFIX} multiple confirmations in training week"},
        )
        t_stats["audit_logs"] = t_stats.get("audit_logs", 0) + 2

    def _collect_counts(self) -> dict:
        club_qs = Club.objects.filter(name__in=DEMO_CLUBS)
        team_qs = Team.objects.filter(club__in=club_qs)
        t_ids = list(team_qs.values_list("id", flat=True))
        player_users = (
            User.objects.filter(team_memberships__team_id__in=t_ids, team_memberships__role=TeamRole.PLAYER)
            .distinct()
        )
        coach_users = (
            User.objects.filter(team_memberships__team_id__in=t_ids, team_memberships__role=TeamRole.COACH)
            .distinct()
        )
        parent_users = (
            User.objects.filter(player_relationships__player__in=player_users).distinct() if t_ids else User.objects.none()
        )
        return {
            "clubs": club_qs.count(),
            "teams": team_qs.count(),
            "users": User.objects.filter(email__endswith="@gmail.com").count(),
            "players": player_users.count(),
            "parents": parent_users.count(),
            "coaches": coach_users.count(),
            "sessions": TrainingSession.objects.filter(team__in=team_qs).count(),
            "attendance": TrainingSessionConfirmation.objects.filter(
                training_session__team__in=team_qs
            ).count(),
            "performance": MatchPlayerStat.objects.filter(
                training_session__team__in=team_qs
            ).count(),
            "tournaments": Tournament.objects.filter(club__in=club_qs, name__startswith=DEMO_PREFIX).count(),
            "tournament_matches": TournamentMatch.objects.filter(tournament__club__in=club_qs).count(),
            "payments": PlayerFeeRecord.objects.filter(club__in=club_qs, description__startswith="DEMO").count(),
            "audit_logs": AuditLog.objects.count() + DirectorPaymentAuditLog.objects.filter(club__in=club_qs).count(),
        }

    def _print_report(self, c: dict, t_stats: dict) -> None:
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS("DEMO SEED — SUMMARY (approximate)"))
        self.stdout.write(
            f"Created/updated: {c['clubs']} clubs | {c['teams']} teams | {c['users']} Gmail-tagged users in DB | "
            f"{c['players']} players (rostered) | {c['parents']} linked parents (distinct) | {c['coaches']} coaches | "
        )
        self.stdout.write(
            f"Sessions: {c['sessions']} | Confirmations: {c['attendance']} | "
            f"Match stat rows: {c['performance']} | Tournaments: {c['tournaments']} | "
            f"TournamentMatch rows: {c['tournament_matches']} | Fee rows: {c['payments']} | Audit records: {c['audit_logs']}"
        )
        self.stdout.write(self.style.SUCCESS("Password (all seed accounts): " + SEED_PASSWORD))
        self.stdout.write("Key: tayma, racha, karma, nay = @gmail.com (see KEY_EMAILS in seed_demo_realistic.py).")
        self.stdout.write("Directors: cpf.director, lak.director, lau.director @gmail.com")
        self.stdout.write("-" * 60)
        self.stdout.write("Features supported by this data: multi-club org, roles, schedules (past/upcoming),")
        self.stdout.write("attendance (present/absent/pending via date rules + confirmations + future rows),")
        self.stdout.write("player progress (weekly + match aggregates), team KPIs, fee schedules + AR states,")
        self.stdout.write("tournaments (pool-only, bracket-only, hybrid+championship + draft).")
        self.stdout.write(self.style.SUCCESS("=" * 60))
