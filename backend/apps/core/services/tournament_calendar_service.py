"""
Link TournamentMatch records to TrainingSession so tournament games appear on team schedules
(Schedule) and coach Events/attendance. Two sessions per match (one per team); update_or_create
avoids duplicates when matches are regenerated (same tournament_match + team key).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from datetime import time as time_type

from django.utils import timezone

from ..models import Team, TrainingSession, TournamentMatch


def _format_local_time_12h(dt: datetime) -> str:
    s = dt.strftime("%I:%M %p")
    if s[0] == "0" and s[1] != "0":
        return s[1:]
    return s


def _add_minutes_to_time(start: time_type, minutes: int) -> time_type:
    d = datetime.combine(datetime.min.date(), start)
    return (d + timedelta(minutes=minutes)).time()


def _stage_description(match: TournamentMatch) -> str:
    t = match.tournament
    if match.pool_id and match.pool:
        return f"Pool — {match.pool.name}"
    return f"Bracket — {match.bracket_round or 'Knockout'}"


def _public_title(tournament_name: str, match: TournamentMatch) -> str:
    """Compact one-line (legacy / API)."""
    a = match.team_a.name if match.team_a else "TBD"
    b = match.team_b.name if match.team_b else "TBD"
    if match.pool_id and match.pool:
        return f"Tournament: {a} vs {b} — {match.pool.name}"
    br = (match.bracket_round or "Round").strip()
    return f"Tournament: {a} vs {b} — {br}"


def _tournament_session_card_title(match: TournamentMatch) -> str:
    """
    Multi-line title for schedule / list views (stays under 255 chars).
    """
    a = match.team_a.name if match.team_a else "TBD"
    b = match.team_b.name if match.team_b else "TBD"
    if match.status == TournamentMatch.MatchStatus.COMPLETED and match.winner_team_id:
        if match.team_a_score is not None and match.team_b_score is not None:
            wn = match.winner_team.name if match.winner_team else "Winner"
            return f"Tournament Match\n{a} {match.team_a_score} - {match.team_b_score} {b}\nWinner: {wn}"[:255]
    stage = f"{match.pool.name}" if (match.pool_id and match.pool) else (match.bracket_round or "Bracket").strip()
    return f"Tournament Match\n{a} vs {b}\n{stage}"[:255]


def _public_notes(
    match: TournamentMatch,
    *,
    for_team: Team,
    opponent: Team,
) -> str:
    """Rich notes for Schedule / Events detail."""
    t = match.tournament
    lines = [
        f"Tournament: {t.name}",
        f"Stage: {_stage_description(match)}",
    ]
    if match.scheduled_time:
        st = match.scheduled_time
        if timezone.is_naive(st):
            st = timezone.make_aware(st, timezone.get_current_timezone())
        st = timezone.localtime(st)
        dur = int(t.match_duration_minutes or 90)
        end_dt = st + timedelta(minutes=dur)
        lines.append(
            f"Time: {_format_local_time_12h(st)} – {_format_local_time_12h(end_dt)} · {st.strftime('%Y-%m-%d')}"
        )
    loc = (match.location or t.venue or "").strip()
    if loc:
        lines.append(f"Location: {loc}")
    if match.status == TournamentMatch.MatchStatus.COMPLETED and match.winner_team_id:
        sa = match.team_a_score
        sb = match.team_b_score
        a_name = match.team_a.name if match.team_a else "A"
        b_name = match.team_b.name if match.team_b else "B"
        if sa is not None and sb is not None:
            lines.append(f"Score: {a_name} {sa} - {sb} {b_name}")
        w = match.winner_team.name if match.winner_team else ""
        if w:
            lines.append(f"Winner: {w}")
        lines.append("Status: Completed")
    else:
        lines.append(f"Opponent: {opponent.name}")
        lines.append("Status: Scheduled")
    return "\n".join(lines)


def sync_calendar_sessions_for_tournament_match(match: TournamentMatch) -> None:
    if not match or not match.pk:
        return

    qs = TrainingSession.objects.filter(tournament_match_id=match.id)
    if not match.scheduled_time:
        qs.delete()
        return

    t = match.tournament
    st = match.scheduled_time
    if timezone.is_naive(st):
        st = timezone.make_aware(st, timezone.get_current_timezone())
    st = timezone.localtime(st)
    s_date = st.date()
    s_time = st.time().replace(microsecond=0)
    duration = t.match_duration_minutes or 90
    end_time = _add_minutes_to_time(s_time, int(duration))
    loc = (match.location or t.venue or "").strip() or ""
    is_done = match.status == TournamentMatch.MatchStatus.COMPLETED
    match_ended = timezone.now() if is_done else None

    if not match.team_a_id or not match.team_b_id:
        qs.delete()
        return
    team_a = match.team_a
    team_b = match.team_b
    if not (team_a and team_b):
        qs.delete()
        return

    valid_ids = {team_a.id, team_b.id}
    qs.exclude(team_id__in=valid_ids).delete()

    def _upsert(for_team: Team, opp: Team) -> None:
        title = _tournament_session_card_title(match)
        notes = _public_notes(match, for_team=for_team, opponent=opp)
        # Per-team "final score" from this team's perspective (optional field on session)
        opp_score = None
        own_score = None
        if is_done and match.team_a_score is not None and match.team_b_score is not None:
            if for_team.id == team_a.id:
                own_score = match.team_a_score
                opp_score = match.team_b_score
            else:
                own_score = match.team_b_score
                opp_score = match.team_a_score

        TrainingSession.objects.update_or_create(
            tournament_match=match,
            team=for_team,
            defaults={
                "title": title,
                "session_type": TrainingSession.SessionType.MATCH,
                "scheduled_date": s_date,
                "start_time": s_time,
                "end_time": end_time,
                "location": loc,
                "opponent": opp.name,
                "opponent_team": opp,
                "match_type": TrainingSession.MatchType.TOURNAMENT,
                "match_request_status": TrainingSession.MatchRequestStatus.ACCEPTED,
                "notes": notes,
                "notify_players": False,
                "notify_parents": False,
                "status": TrainingSession.Status.SCHEDULED,
                "created_by": t.created_by,
                "match_ended_at": match_ended,
                "opponent_final_score": opp_score,
            },
        )

    _upsert(team_a, team_b)
    _upsert(team_b, team_a)


def sync_all_matches_in_tournament(tournament_id: int) -> None:
    for m in (
        TournamentMatch.objects.filter(tournament_id=tournament_id)
        .select_related("tournament", "team_a", "team_b", "pool", "winner_team")
        .order_by("id")
    ):
        sync_calendar_sessions_for_tournament_match(m)
