"""
Deterministic automatic scheduling for generated tournament matches.

* Anchor on tournament start_date + start_time (not "now"), snapped to 30-minute grid.
* Pool play: for each round across all pools, pack matches on parallel courts; waves when K > C.
* Bracket: ordered rounds, same packing; starts after the last pool match (or at anchor for bracket-only).
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import TYPE_CHECKING, Any, List, Optional, Tuple

from django.utils import timezone

if TYPE_CHECKING:
    from ..models import Pool, Tournament, TournamentMatch

# Default when generating — tournament model may still use 18:00; creation sets 9:00 in tournament_views
DEFAULT_TOURNAMENT_DAY_START = time(9, 0)
MIN_BLOCK_MINUTES = 30
MAX_COURT_COUNT = 8


def _aware_combine(d: date, t: time) -> datetime:
    naive = datetime.combine(d, t)
    if timezone.is_naive(naive):
        return timezone.make_aware(naive, timezone.get_current_timezone())
    return naive


def tournament_day_anchor(tournament) -> datetime:
    """Date + time the tournament is intended to start (not current wall clock)."""
    t = tournament.start_time or DEFAULT_TOURNAMENT_DAY_START
    return _aware_combine(tournament.start_date, t)


def snap_start_to_30min(dt: datetime) -> datetime:
    """Snap local clock time to a 30-minute grid (9:00, 9:30, …) for clean UI."""
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    local = timezone.localtime(dt)
    d = local.date()
    total = local.hour * 60 + local.minute
    snapped = (total // 30) * 30
    h, m = divmod(snapped, 60)
    return _aware_combine(d, time(h, m, 0))


def effective_match_duration_minutes(tournament) -> int:
    d = int(tournament.match_duration_minutes or 90)
    return max(30, min(180, d))


def effective_court_count(tournament) -> int:
    """Director-configured parallel courts (default 1). Not tied to pool count."""
    c = int(getattr(tournament, "court_count", None) or 0) or 1
    return max(1, min(MAX_COURT_COUNT, c))


def schedule_time_blocks(
    anchor: datetime,
    num_matches: int,
    num_courts: int,
    block_minutes: int,
) -> List[Tuple[datetime, int]]:
    """
    Return list of (start_datetime, court_index 0-based) of length num_matches.
    Fills court 0..C-1 in wave 0, then next wave, etc. — no two matches share
    a court in the same wave, and no court hosts two games at the same time.
    """
    if num_matches == 0:
        return []
    c = max(1, int(num_courts))
    d = max(MIN_BLOCK_MINUTES, int(block_minutes))
    out: List[Tuple[datetime, int]] = []
    for i in range(num_matches):
        wave = i // c
        court_i = i % c
        start = anchor + timedelta(minutes=wave * d)
        out.append((start, court_i))
    return out


def bracket_round_sort_key(name: Optional[str]) -> Tuple[int, str]:
    n = (name or "").lower().strip()
    if "quarter" in n:
        return (0, n)
    if "semi" in n:
        return (1, n)
    if n == "final" or ("final" in n and "semi" not in n):
        return (3, n)
    if "round" in n:
        return (2, n)
    return (1, n)


def build_pool_match_schedule(
    tournament,
    pool_rounds: list,
    *,
    seen_pairings: Optional[set] = None,
) -> list[dict[str, Any]]:
    """
    For each global round index, schedule that round's games across all pools in parallel
    (up to C courts), with sequential waves. Same team never plays twice in one round.

    `pool_rounds` is: [(pool_obj, list_of_rounds), ...] where list_of_rounds is from
    _round_robin_pairs: round index -> list of (team_a_id, team_b_id).
    """
    if seen_pairings is None:
        seen_pairings = set()
    max_r = 0
    for _pool, rounds in pool_rounds:
        max_r = max(max_r, len(rounds or []))
    d = effective_match_duration_minutes(tournament)
    c = effective_court_count(tournament)
    t = snap_start_to_30min(tournament_day_anchor(tournament))
    out: list[dict[str, Any]] = []
    for r in range(max_r):
        batch: list[tuple[object, int, int]] = []
        for pool, rounds in pool_rounds:
            if r >= len(rounds):
                continue
            for team_a_id, team_b_id in rounds[r]:
                if team_a_id is None or team_b_id is None or team_a_id == team_b_id:
                    continue
                sig = tuple(sorted((int(team_a_id), int(team_b_id))))
                if sig in seen_pairings:
                    continue
                seen_pairings.add(sig)
                batch.append((pool, int(team_a_id), int(team_b_id)))
        if not batch:
            continue
        batch.sort(key=lambda x: (x[0].id, x[1], x[2]))
        assigned = schedule_time_blocks(t, len(batch), c, d)
        for i, (pool, ta, tb) in enumerate(batch):
            start, court_idx = assigned[i]
            out.append(
                {
                    "pool": pool,
                    "team_a_id": ta,
                    "team_b_id": tb,
                    "pool_round_number": r + 1,
                    "scheduled_time": start,
                    "location": f"Court {int(court_idx) + 1}",
                }
            )
        waves = (len(batch) + c - 1) // c
        t = t + timedelta(minutes=waves * d)
    return out


def build_bracket_match_schedule(
    tournament,
    matches: list,  # TournamentMatch instances (bracket), must have both teams for timing
    *,
    first_round_start: datetime,
) -> List[Tuple[object, datetime, str]]:
    """
    Returns list of (match, scheduled_time, location) in any order; caller should apply updates.
    `matches` = bracket matches with pool IS NULL, mixed rounds.
    """
    d = effective_match_duration_minutes(tournament)
    c = effective_court_count(tournament)
    # group by round sort
    if not matches:
        return []
    from collections import defaultdict

    by_round: dict[tuple[int, str], list] = defaultdict(list)
    for m in matches:
        k = bracket_round_sort_key(m.bracket_round)
        by_round[k].append(m)
    for k in by_round:
        by_round[k].sort(key=lambda x: (x.match_number, x.id))
    ordered_keys = sorted(by_round.keys(), key=lambda t: (t[0], t[1]))
    t = snap_start_to_30min(first_round_start)
    updates: List[Tuple[object, datetime, str]] = []
    for key in ordered_keys:
        r_matches = by_round[key]
        # only matches with two teams for schedule (TBD might exist)
        mlist = r_matches
        n = len(mlist)
        if n == 0:
            continue
        assigned = schedule_time_blocks(t, n, c, d)
        for i, m in enumerate(mlist):
            start, court_idx = assigned[i]
            updates.append((m, start, f"Court {int(court_idx) + 1}"))
        waves = (n + c - 1) // c
        t = t + timedelta(minutes=waves * d)
    return updates
