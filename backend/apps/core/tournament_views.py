import json
import random
from collections import defaultdict
from datetime import datetime, time, timedelta

from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods

from .decorators import login_required
from .models import (
    ClubMembership,
    ClubRole,
    ParentPlayerRelation,
    Pool,
    Standing,
    Team,
    TeamMembership,
    TeamRole,
    Tournament,
    TournamentMatch,
    TournamentTeam,
)
from .services.audit_log_service import AuditLogService
from .services.tournament_calendar_service import (
    sync_all_matches_in_tournament,
    sync_calendar_sessions_for_tournament_match,
)
from .services.tournament_scheduling import (
    build_bracket_match_schedule,
    build_pool_match_schedule,
    snap_start_to_30min,
    tournament_day_anchor,
    effective_match_duration_minutes,
)


def _parse_body(request):
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def _canonical_tournament_type(raw_type):
    legacy_map = {
        Tournament.TournamentType.POOLS: Tournament.TournamentType.POOL_ONLY,
        Tournament.TournamentType.BRACKET: Tournament.TournamentType.BRACKET_ONLY,
        Tournament.TournamentType.HYBRID: Tournament.TournamentType.POOL_AND_BRACKET,
    }
    return legacy_map.get(raw_type, raw_type)


def _normalize_tournament_status(tournament):
    if tournament.status == Tournament.Status.GENERATED:
        tournament.status = Tournament.Status.DRAFT
        tournament.save(update_fields=["status", "updated_at"])
    return tournament


def _is_director_for_club(user, club_id):
    return user.is_staff or ClubMembership.objects.active().filter(
        user=user, club_id=club_id, role=ClubRole.CLUB_DIRECTOR
    ).exists()


def _team_ids_for_user(user):
    team_ids = set(
        TeamMembership.objects.active()
        .filter(user=user, role__in=[TeamRole.COACH, TeamRole.PLAYER])
        .values_list("team_id", flat=True)
    )
    child_ids = ParentPlayerRelation.objects.approved().filter(parent=user).values_list("player_id", flat=True)
    if child_ids:
        child_team_ids = TeamMembership.objects.active().filter(
            user_id__in=child_ids, role=TeamRole.PLAYER
        ).values_list("team_id", flat=True)
        team_ids.update(child_team_ids)
    return team_ids


def _can_submit_result(user, match):
    if user.is_staff or _is_director_for_club(user, match.tournament.club_id):
        return True
    if not (match.team_a_id and match.team_b_id):
        return False
    return TeamMembership.objects.active().filter(
        user=user, role=TeamRole.COACH, team_id__in=[match.team_a_id, match.team_b_id]
    ).exists()


def _has_started_or_ended_matches(tournament):
    return TournamentMatch.objects.filter(tournament=tournament).exclude(
        status=TournamentMatch.MatchStatus.SCHEDULED
    ).exists()


def _can_view_tournament(user, tournament):
    if user.is_staff or _is_director_for_club(user, tournament.club_id):
        return True
    team_scope = _team_ids_for_user(user)
    return TournamentTeam.objects.filter(tournament=tournament, team_id__in=team_scope).exists()


def _serialize_match(match):
    return {
        "id": match.id,
        "tournament_id": match.tournament_id,
        "pool_id": match.pool_id,
        "pool_name": match.pool.name if match.pool_id else None,
        "bracket_round": match.bracket_round or None,
        "match_number": match.match_number,
        "team_a_id": match.team_a_id,
        "team_b_id": match.team_b_id,
        "team_a_name": match.team_a.name if match.team_a_id else None,
        "team_b_name": match.team_b.name if match.team_b_id else None,
        "team_a_score": match.team_a_score,
        "team_b_score": match.team_b_score,
        "winner_team_id": match.winner_team_id,
        "winner_team_name": match.winner_team.name if match.winner_team_id else None,
        "loser_team_id": match.loser_team_id,
        "loser_team_name": match.loser_team.name if match.loser_team_id else None,
        "status": match.status,
        "scheduled_time": match.scheduled_time.isoformat() if match.scheduled_time else None,
        "location": match.location,
        "next_match_id": match.next_match_id,
        "next_match_slot": match.next_match_slot or None,
    }


def _serialize_tournament(tournament):
    normalized = _normalize_tournament_status(tournament)
    return {
        "id": normalized.id,
        "name": normalized.name,
        "location": normalized.venue,
        "start_date": normalized.start_date.isoformat(),
        "status": normalized.status,
        "format": _canonical_tournament_type(normalized.tournament_type),
        "number_of_pools": normalized.pool_count,
        "teams_per_pool": normalized.teams_per_pool,
        "top_teams_advance_per_pool": normalized.teams_qualifying_per_pool,
        "tie_break_rule": normalized.scoring_format,
        "created_by": normalized.created_by_id,
        "created_at": normalized.created_at.isoformat(),
        "updated_at": normalized.updated_at.isoformat(),
    }


def _round_robin_pairs(team_ids):
    teams = list(team_ids)
    if len(teams) % 2 == 1:
        teams.append(None)
    rounds = []
    for _ in range(len(teams) - 1):
        pairings = []
        half = len(teams) // 2
        for idx in range(half):
            a = teams[idx]
            b = teams[-1 - idx]
            if a is None or b is None:
                continue
            if a == b:
                continue
            pairings.append((a, b))
        rounds.append(pairings)
        teams = [teams[0], teams[-1], *teams[1:-1]]
    seen = set()
    deduped = []
    for pairings in rounds:
        row = []
        for a, b in pairings:
            sig = tuple(sorted((a, b)))
            if sig in seen:
                continue
            seen.add(sig)
            row.append((a, b))
        if row:
            deduped.append(row)
    return deduped


def _recalculate_pool_standings(tournament, pool):
    rows = {}
    for tteam in TournamentTeam.objects.filter(tournament=tournament, pool=pool).select_related("team"):
        standing, _ = Standing.objects.get_or_create(
            tournament=tournament,
            pool=pool,
            team=tteam.team,
            defaults={"wins": 0, "losses": 0, "points": 0, "points_for": 0, "points_against": 0, "point_difference": 0},
        )
        standing.wins = 0
        standing.losses = 0
        standing.points = 0
        standing.points_for = 0
        standing.points_against = 0
        standing.point_difference = 0
        standing.set_ratio = 0.0
        standing.rank = 1
        standing.save(
            update_fields=["wins", "losses", "points", "points_for", "points_against", "point_difference", "set_ratio", "rank"]
        )
        rows[standing.team_id] = standing

    completed_matches = TournamentMatch.objects.filter(
        tournament=tournament, pool=pool, status=TournamentMatch.MatchStatus.COMPLETED
    )
    for match in completed_matches:
        if not (match.team_a_id and match.team_b_id and match.winner_team_id):
            continue
        a = rows.get(match.team_a_id)
        b = rows.get(match.team_b_id)
        if not a or not b:
            continue
        a_pf = match.team_a_score or 0
        b_pf = match.team_b_score or 0
        a.points_for += a_pf
        a.points_against += b_pf
        b.points_for += b_pf
        b.points_against += a_pf
        if match.winner_team_id == a.team_id:
            a.wins += 1
            a.points += 3
            b.losses += 1
        else:
            b.wins += 1
            b.points += 3
            a.losses += 1

    for standing in rows.values():
        standing.point_difference = standing.points_for - standing.points_against
        standing.save(
            update_fields=["wins", "losses", "points", "points_for", "points_against", "point_difference"]
        )

    standings = list(Standing.objects.filter(tournament=tournament, pool=pool).select_related("team"))
    standings.sort(
        key=lambda row: (
            -row.wins,
            -row.points,
            -row.point_difference,
            -row.points_for,
        )
    )

    i = 0
    while i < len(standings):
        j = i + 1
        while j < len(standings) and standings[j].wins == standings[i].wins and standings[j].points == standings[i].points:
            j += 1
        tie = standings[i:j]
        if len(tie) == 2:
            left, right = tie
            h2h = completed_matches.filter(
                Q(team_a_id=left.team_id, team_b_id=right.team_id)
                | Q(team_a_id=right.team_id, team_b_id=left.team_id)
            ).order_by("-id")
            if h2h.exists():
                winner_id = h2h.first().winner_team_id
                if winner_id == right.team_id:
                    standings[i], standings[i + 1] = standings[i + 1], standings[i]
        elif len(tie) > 2:
            tie.sort(
                key=lambda row: (
                    -row.point_difference,
                    -row.points_for,
                    random.Random(f"{tournament.id}:{pool.id}:{row.team_id}").random(),
                )
            )
            standings[i:j] = tie
        i = j

    for index, standing in enumerate(standings, start=1):
        standing.rank = index
        standing.save(update_fields=["rank"])


def _advance_winner(match):
    if not match.next_match_id or not match.winner_team_id:
        return
    next_match = match.next_match
    if not next_match:
        return
    if match.next_match_slot == "A":
        next_match.team_a_id = match.winner_team_id
    elif match.next_match_slot == "B":
        next_match.team_b_id = match.winner_team_id
    next_match.save(update_fields=["team_a", "team_b", "updated_at"])


@csrf_exempt
@login_required
@require_http_methods(["POST", "GET"])
def tournaments(request):
    if request.method == "GET":
        team_scope = _team_ids_for_user(request.user)
        if request.user.is_staff:
            queryset = Tournament.objects.all()
        else:
            queryset = Tournament.objects.filter(
                Q(club__memberships__user=request.user, club__memberships__role=ClubRole.CLUB_DIRECTOR)
                | Q(tournament_teams__team_id__in=team_scope)
            ).distinct()
        rows = list(queryset.order_by("-id"))
        for row in rows:
            _normalize_tournament_status(row)
        return JsonResponse({"tournaments": [_serialize_tournament(t) for t in rows]})

    payload = _parse_body(request)
    if payload is None:
        return JsonResponse({"errors": {"payload": "Invalid JSON payload."}}, status=400)
    club_id = payload.get("club_id")
    if not club_id:
        return JsonResponse({"errors": {"club_id": "club_id is required."}}, status=400)
    if not _is_director_for_club(request.user, club_id):
        return JsonResponse({"errors": {"authorization": "Only directors can create tournament."}}, status=403)

    name = (payload.get("name") or "").strip()
    location = (payload.get("location") or "").strip()
    start_date_raw = payload.get("start_date")
    format_code = payload.get("format")
    raw_team_ids = payload.get("team_ids") or []
    if not isinstance(raw_team_ids, list):
        return JsonResponse({"errors": {"team_ids": "team_ids must be an array of numeric IDs."}}, status=400)
    parsed_team_ids = []
    duplicate_team_ids = set()
    invalid_team_id_values = []
    for raw_team_id in raw_team_ids:
        try:
            team_id = int(raw_team_id)
        except (TypeError, ValueError):
            invalid_team_id_values.append(raw_team_id)
            continue
        if team_id in parsed_team_ids:
            duplicate_team_ids.add(team_id)
            continue
        parsed_team_ids.append(team_id)
    number_of_pools = int(payload.get("number_of_pools") or 0)
    teams_per_pool = int(payload.get("teams_per_pool") or 0)
    top_teams = int(payload.get("top_teams_advance_per_pool") or 0)
    tie_break_rule = (payload.get("tie_break_rule") or "wins, head-to-head, point_difference, points_for, random").strip()
    errors = {}
    if not name:
        errors["name"] = "Tournament name is required."
    if not location:
        errors["location"] = "Location is required."
    if not start_date_raw:
        errors["start_date"] = "Start date is required."
    if format_code not in {
        Tournament.TournamentType.POOL_ONLY,
        Tournament.TournamentType.BRACKET_ONLY,
        Tournament.TournamentType.POOL_AND_BRACKET,
    }:
        errors["format"] = "Invalid format."
    if invalid_team_id_values:
        errors["team_ids"] = "All team_ids must be valid numeric IDs."
    if duplicate_team_ids:
        errors["team_ids"] = "Duplicate team IDs are not allowed."
    if len(parsed_team_ids) < 2:
        errors["teams"] = "At least two teams are required."
    if errors:
        return JsonResponse({"errors": errors}, status=400)
    team_qs = Team.objects.filter(club_id=club_id, id__in=parsed_team_ids)
    if team_qs.count() != len(parsed_team_ids):
        return JsonResponse(
            {"errors": {"teams": "Some selected teams are invalid or not part of this club."}},
            status=400,
        )
    if format_code != Tournament.TournamentType.BRACKET_ONLY:
        if number_of_pools < 1:
            return JsonResponse({"errors": {"number_of_pools": "At least one pool is required."}}, status=400)
        if teams_per_pool < 2:
            return JsonResponse({"errors": {"teams_per_pool": "Teams per pool must be at least 2."}}, status=400)
        if number_of_pools * teams_per_pool != len(parsed_team_ids):
            return JsonResponse({"errors": {"pool_layout": "Pools configuration does not match selected team count."}}, status=400)
        if top_teams > teams_per_pool:
            return JsonResponse({"errors": {"top_teams_advance_per_pool": "Top teams cannot exceed teams per pool."}}, status=400)

    start_date = datetime.fromisoformat(start_date_raw).date()
    tournament = Tournament.objects.create(
        club_id=club_id,
        created_by=request.user,
        name=name,
        start_date=start_date,
        start_time=time(9, 0),
        venue=location,
        tournament_type=format_code,
        status=Tournament.Status.DRAFT,
        number_of_teams=len(parsed_team_ids),
        pool_count=number_of_pools,
        teams_per_pool=teams_per_pool,
        teams_qualifying_per_pool=top_teams,
        scoring_format=tie_break_rule,
    )
    tournament.teams.set(list(team_qs))
    for index, team in enumerate(team_qs.order_by("name", "id"), start=1):
        TournamentTeam.objects.create(tournament=tournament, team=team, seed=index)
    AuditLogService.log_action(
        user=request.user,
        action_type="tournament_created",
        entity_type="tournament",
        entity_id=tournament.id,
        new_value={"name": tournament.name, "format": tournament.tournament_type},
    )
    return JsonResponse(
        {
            "id": tournament.id,
            "tournament_id": tournament.id,
            "tournament": {
                "id": tournament.id,
                "name": tournament.name,
                "status": tournament.status,
                "format": _canonical_tournament_type(tournament.tournament_type),
                "number_of_teams": tournament.number_of_teams,
                "number_of_pools": tournament.pool_count,
                "teams_per_pool": tournament.teams_per_pool,
            },
            "name": tournament.name,
            "status": tournament.status,
            "format": _canonical_tournament_type(tournament.tournament_type),
            "number_of_teams": tournament.number_of_teams,
            "number_of_pools": tournament.pool_count,
            "teams_per_pool": tournament.teams_per_pool,
            "message": "Tournament created successfully.",
        },
        status=201,
    )


@csrf_exempt
@login_required
@require_http_methods(["GET", "PUT"])
def tournament_detail(request, tournament_id):
    try:
        tournament = Tournament.objects.select_related("club").get(id=tournament_id)
    except Tournament.DoesNotExist:
        return JsonResponse({"errors": {"tournament": "Tournament not found."}}, status=404)
    _normalize_tournament_status(tournament)
    if not _can_view_tournament(request.user, tournament):
        return JsonResponse({"errors": {"authorization": "You do not have access to this tournament."}}, status=403)
    if request.method == "GET":
        return JsonResponse({"tournament": _serialize_tournament(tournament)})
    if not _is_director_for_club(request.user, tournament.club_id):
        return JsonResponse({"errors": {"authorization": "Only directors can edit tournament."}}, status=403)
    if tournament.status != Tournament.Status.DRAFT or _has_started_or_ended_matches(tournament):
        return JsonResponse({"errors": {"tournament": "Tournament can only be edited before it starts."}}, status=400)
    payload = _parse_body(request)
    if payload is None:
        return JsonResponse({"errors": {"payload": "Invalid JSON payload."}}, status=400)
    tournament.name = (payload.get("name") or tournament.name).strip()
    tournament.venue = (payload.get("location") or tournament.venue).strip()
    if payload.get("start_date"):
        tournament.start_date = datetime.fromisoformat(payload["start_date"]).date()
    tournament.save(update_fields=["name", "venue", "start_date", "updated_at"])
    return JsonResponse({"message": "Tournament updated.", "tournament": _serialize_tournament(tournament)})


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def generate_pools(request, tournament_id):
    try:
        tournament = Tournament.objects.get(id=tournament_id)
    except Tournament.DoesNotExist:
        return JsonResponse({"errors": {"tournament": "Tournament not found."}}, status=404)
    _normalize_tournament_status(tournament)
    if not _is_director_for_club(request.user, tournament.club_id):
        return JsonResponse({"errors": {"authorization": "Only directors can generate pools."}}, status=403)
    if tournament.tournament_type == Tournament.TournamentType.BRACKET_ONLY:
        return JsonResponse({"errors": {"format": "Bracket-only tournament does not use pools."}}, status=400)
    if _has_started_or_ended_matches(tournament):
        return JsonResponse(
            {"errors": {"matches": "Cannot regenerate pools after matches have started or ended."}},
            status=400,
        )
    with transaction.atomic():
        Pool.objects.filter(tournament=tournament).delete()
        tteams = list(TournamentTeam.objects.filter(tournament=tournament).select_related("team").order_by("seed", "id"))
        if len(tteams) != tournament.number_of_teams:
            return JsonResponse({"errors": {"teams": "Tournament teams are missing."}}, status=400)
        pools = []
        for i in range(tournament.pool_count):
            pool = Pool.objects.create(tournament=tournament, name=f"Pool {chr(65 + i)}")
            pools.append(pool)
        for index, tteam in enumerate(tteams):
            pool = pools[index % len(pools)]
            tteam.pool = pool
            tteam.save(update_fields=["pool"])
            Standing.objects.get_or_create(tournament=tournament, pool=pool, team=tteam.team)
        tournament.status = Tournament.Status.POOL_STAGE
        tournament.save(update_fields=["status", "updated_at"])
    AuditLogService.log_action(
        user=request.user, action_type="pools_generated", entity_type="tournament", entity_id=tournament.id
    )
    return JsonResponse({"message": "Pools generated."})


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def generate_pool_matches(request, tournament_id):
    try:
        tournament = Tournament.objects.get(id=tournament_id)
    except Tournament.DoesNotExist:
        return JsonResponse({"errors": {"tournament": "Tournament not found."}}, status=404)
    _normalize_tournament_status(tournament)
    if not _is_director_for_club(request.user, tournament.club_id):
        return JsonResponse({"errors": {"authorization": "Only directors can generate pool matches."}}, status=403)
    existing = TournamentMatch.objects.filter(tournament=tournament, pool__isnull=False)
    if existing.exclude(status=TournamentMatch.MatchStatus.SCHEDULED).exists():
        return JsonResponse({"errors": {"matches": "Cannot regenerate schedule after matches have started."}}, status=400)
    with transaction.atomic():
        existing.delete()
        match_number = 1
        pool_rows = list(Pool.objects.filter(tournament=tournament).order_by("id"))
        pool_rounds = []
        for pool in pool_rows:
            team_ids = list(
                TournamentTeam.objects.filter(tournament=tournament, pool=pool)
                .order_by("seed", "id")
                .values_list("team_id", flat=True)
            )
            pool_rounds.append((pool, _round_robin_pairs(team_ids)))
        plan = build_pool_match_schedule(tournament, pool_rounds)
        for item in plan:
            TournamentMatch.objects.create(
                tournament=tournament,
                pool=item["pool"],
                match_number=match_number,
                team_a_id=item["team_a_id"],
                team_b_id=item["team_b_id"],
                scheduled_time=item["scheduled_time"],
                location=str(item["location"]),
                status=TournamentMatch.MatchStatus.SCHEDULED,
            )
            match_number += 1
    AuditLogService.log_action(
        user=request.user, action_type="pool_matches_generated", entity_type="tournament", entity_id=tournament.id
    )
    sync_all_matches_in_tournament(tournament.id)
    return JsonResponse({"message": "Pool schedule generated."})


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def generate_bracket(request, tournament_id):
    try:
        tournament = Tournament.objects.get(id=tournament_id)
    except Tournament.DoesNotExist:
        return JsonResponse({"errors": {"tournament": "Tournament not found."}}, status=404)
    _normalize_tournament_status(tournament)
    if not _is_director_for_club(request.user, tournament.club_id):
        return JsonResponse({"errors": {"authorization": "Only directors can generate bracket."}}, status=403)
    if tournament.tournament_type == Tournament.TournamentType.POOL_ONLY:
        return JsonResponse({"errors": {"format": "Pool-only tournament has no bracket stage."}}, status=400)
    pool_matches = TournamentMatch.objects.filter(tournament=tournament, pool__isnull=False)
    if pool_matches.exists() and pool_matches.exclude(status=TournamentMatch.MatchStatus.COMPLETED).exists():
        return JsonResponse({"errors": {"pool_stage": "Complete all pool matches before generating bracket."}}, status=400)
    existing_bracket = TournamentMatch.objects.filter(tournament=tournament, pool__isnull=True)
    if existing_bracket.filter(status__in=[TournamentMatch.MatchStatus.ONGOING, TournamentMatch.MatchStatus.COMPLETED]).exists():
        return JsonResponse({"errors": {"bracket": "Bracket already started and cannot be regenerated."}}, status=400)
    pool_planned = TournamentMatch.objects.filter(
        tournament=tournament, pool__isnull=False, scheduled_time__isnull=False
    )
    if pool_planned.exists():
        last_pool_start = max(m.scheduled_time for m in pool_planned)
        bracket_run_start = snap_start_to_30min(last_pool_start + timedelta(minutes=30))
    else:
        bracket_run_start = snap_start_to_30min(tournament_day_anchor(tournament))
    with transaction.atomic():
        existing_bracket.delete()
        qualifiers = []
        if tournament.tournament_type == Tournament.TournamentType.BRACKET_ONLY:
            qualifiers = list(TournamentTeam.objects.filter(tournament=tournament).order_by("seed", "id").values_list("team_id", flat=True))
        else:
            for pool in Pool.objects.filter(tournament=tournament).order_by("id"):
                _recalculate_pool_standings(tournament, pool)
                pool_qualifiers = list(
                    Standing.objects.filter(tournament=tournament, pool=pool)
                    .order_by("rank", "id")
                    .values_list("team_id", flat=True)[: tournament.teams_qualifying_per_pool]
                )
                qualifiers.extend(pool_qualifiers)
        if len(qualifiers) < 2:
            return JsonResponse({"errors": {"bracket": "Not enough qualified teams for bracket."}}, status=400)
        bracket_size = 1
        while bracket_size < len(qualifiers):
            bracket_size *= 2
        qualifiers += [None] * (bracket_size - len(qualifiers))
        round_name = "Semi-Final" if bracket_size == 4 else "Quarter-Final"
        round_matches = []
        match_number = TournamentMatch.objects.filter(tournament=tournament).count() + 1
        for idx in range(bracket_size // 2):
            a = qualifiers[idx]
            b = qualifiers[-1 - idx]
            match = TournamentMatch.objects.create(
                tournament=tournament,
                bracket_round=round_name,
                match_number=match_number,
                team_a_id=a,
                team_b_id=b,
                scheduled_time=bracket_run_start,
                location="Court 1",
                status=TournamentMatch.MatchStatus.SCHEDULED,
            )
            round_matches.append(match)
            match_number += 1
        next_round_name = "Final" if len(round_matches) == 2 else "Round 2"
        next_round = []
        for idx in range((len(round_matches) + 1) // 2):
            next_round.append(
                TournamentMatch.objects.create(
                    tournament=tournament,
                    bracket_round=next_round_name,
                    match_number=match_number + idx,
                    scheduled_time=bracket_run_start,
                    location="Court 1",
                    status=TournamentMatch.MatchStatus.SCHEDULED,
                )
            )
        for idx, match in enumerate(round_matches):
            target = next_round[idx // 2]
            match.next_match = target
            match.next_match_slot = "A" if idx % 2 == 0 else "B"
            match.save(update_fields=["next_match", "next_match_slot", "updated_at"])
            if (match.team_a_id and not match.team_b_id) or (match.team_b_id and not match.team_a_id):
                match.winner_team_id = match.team_a_id or match.team_b_id
                match.status = TournamentMatch.MatchStatus.COMPLETED
                match.save(update_fields=["winner_team", "status", "updated_at"])
                _advance_winner(match)
        # Realistic, non-overlapping times & courts; bracket_run_start is after pool play when applicable.
        bracket_list = list(
            TournamentMatch.objects.filter(tournament=tournament, pool__isnull=True)
            .select_related("tournament")
            .order_by("id")
        )
        for match_obj, st, loc in build_bracket_match_schedule(
            tournament, bracket_list, first_round_start=bracket_run_start
        ):
            match_obj.scheduled_time = st
            match_obj.location = loc
            match_obj.save(update_fields=["scheduled_time", "location", "updated_at"])
        tournament.status = Tournament.Status.BRACKET_STAGE
        tournament.save(update_fields=["status", "updated_at"])
    AuditLogService.log_action(
        user=request.user, action_type="bracket_generated", entity_type="tournament", entity_id=tournament.id
    )
    sync_all_matches_in_tournament(tournament.id)
    return JsonResponse({"message": "Bracket generated."})


@login_required
@require_GET
def tournament_matches(request, tournament_id):
    try:
        tournament = Tournament.objects.get(id=tournament_id)
    except Tournament.DoesNotExist:
        return JsonResponse({"errors": {"tournament": "Tournament not found."}}, status=404)
    _normalize_tournament_status(tournament)
    if not _can_view_tournament(request.user, tournament):
        return JsonResponse({"errors": {"authorization": "You do not have access to this tournament."}}, status=403)
    if request.user.is_staff or _is_director_for_club(request.user, tournament.club_id):
        matches = TournamentMatch.objects.filter(tournament=tournament).select_related(
            "team_a", "team_b", "pool", "winner_team", "loser_team"
        )
    else:
        team_scope = _team_ids_for_user(request.user)
        matches = TournamentMatch.objects.filter(tournament=tournament).filter(
            Q(team_a_id__in=team_scope) | Q(team_b_id__in=team_scope)
        ).select_related("team_a", "team_b", "pool", "winner_team", "loser_team")
    return JsonResponse({"matches": [_serialize_match(match) for match in matches.order_by("match_number", "id")]})


@login_required
@require_GET
def match_detail(request, match_id):
    try:
        match = TournamentMatch.objects.select_related("tournament", "team_a", "team_b", "winner_team", "loser_team", "pool").get(
            id=match_id
        )
    except TournamentMatch.DoesNotExist:
        return JsonResponse({"errors": {"match": "Match not found."}}, status=404)
    if not (request.user.is_staff or _is_director_for_club(request.user, match.tournament.club_id)):
        team_scope = _team_ids_for_user(request.user)
        if match.team_a_id not in team_scope and match.team_b_id not in team_scope:
            return JsonResponse({"errors": {"authorization": "You do not have access to this match."}}, status=403)
    return JsonResponse({"match": _serialize_match(match)})


@csrf_exempt
@login_required
@require_http_methods(["PUT"])
def reschedule_match(request, match_id):
    try:
        match = TournamentMatch.objects.select_related("tournament").get(id=match_id)
    except TournamentMatch.DoesNotExist:
        return JsonResponse({"errors": {"match": "Match not found."}}, status=404)
    if not _is_director_for_club(request.user, match.tournament.club_id):
        return JsonResponse({"errors": {"authorization": "Only directors can reschedule matches."}}, status=403)
    if match.status == TournamentMatch.MatchStatus.COMPLETED:
        return JsonResponse({"errors": {"match": "Completed matches cannot be rescheduled."}}, status=400)
    payload = _parse_body(request)
    if payload is None or not payload.get("scheduled_time"):
        return JsonResponse({"errors": {"scheduled_time": "scheduled_time is required."}}, status=400)
    old_schedule = match.scheduled_time.isoformat() if match.scheduled_time else None
    match.scheduled_time = datetime.fromisoformat(payload["scheduled_time"])
    if payload.get("location") is not None:
        match.location = str(payload["location"]).strip()
    match.save(update_fields=["scheduled_time", "location", "updated_at"])
    match = TournamentMatch.objects.select_related("tournament", "team_a", "team_b", "pool").get(pk=match.pk)
    sync_calendar_sessions_for_tournament_match(match)
    AuditLogService.log_action(
        user=request.user,
        action_type="match_rescheduled",
        entity_type="tournament_match",
        entity_id=match.id,
        old_value={"scheduled_time": old_schedule},
        new_value={"scheduled_time": match.scheduled_time.isoformat()},
    )
    return JsonResponse({"message": "Match rescheduled.", "match": _serialize_match(match)})


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def submit_match_result(request, match_id):
    try:
        match = TournamentMatch.objects.select_related("tournament", "pool", "next_match").get(id=match_id)
    except TournamentMatch.DoesNotExist:
        return JsonResponse({"errors": {"match": "Match not found."}}, status=404)
    if not _can_submit_result(request.user, match):
        return JsonResponse({"errors": {"authorization": "You cannot enter results for this match."}}, status=403)
    payload = _parse_body(request)
    if payload is None:
        return JsonResponse({"errors": {"payload": "Invalid JSON payload."}}, status=400)
    if match.status == TournamentMatch.MatchStatus.COMPLETED and not (
        match.can_edit_result or _is_director_for_club(request.user, match.tournament.club_id)
    ):
        return JsonResponse({"errors": {"match": "Result already entered for this match."}}, status=400)
    a_score = payload.get("team_a_score")
    b_score = payload.get("team_b_score")
    if a_score is None or b_score is None:
        return JsonResponse({"errors": {"score": "team_a_score and team_b_score are required."}}, status=400)
    a_score = int(a_score)
    b_score = int(b_score)
    if a_score == b_score:
        return JsonResponse({"errors": {"score": "Volleyball matches cannot end in a tie."}}, status=400)
    if not (match.team_a_id and match.team_b_id):
        return JsonResponse({"errors": {"teams": "Both teams must be assigned before entering result."}}, status=400)
    with transaction.atomic():
        match.team_a_score = a_score
        match.team_b_score = b_score
        if a_score > b_score:
            match.winner_team_id = match.team_a_id
            match.loser_team_id = match.team_b_id
        else:
            match.winner_team_id = match.team_b_id
            match.loser_team_id = match.team_a_id
        match.status = TournamentMatch.MatchStatus.COMPLETED
        match.save(
            update_fields=[
                "team_a_score",
                "team_b_score",
                "winner_team",
                "loser_team",
                "status",
                "updated_at",
            ]
        )
        if match.pool_id:
            _recalculate_pool_standings(match.tournament, match.pool)
            if not TournamentMatch.objects.filter(tournament=match.tournament, pool__isnull=False).exclude(
                status=TournamentMatch.MatchStatus.COMPLETED
            ).exists():
                if match.tournament.tournament_type == Tournament.TournamentType.POOL_ONLY:
                    match.tournament.status = Tournament.Status.COMPLETED
                else:
                    match.tournament.status = Tournament.Status.BRACKET_STAGE
                match.tournament.save(update_fields=["status", "updated_at"])
        else:
            _advance_winner(match)
            if match.bracket_round == "Final":
                match.tournament.status = Tournament.Status.COMPLETED
                match.tournament.save(update_fields=["status", "updated_at"])
    AuditLogService.log_action(
        user=request.user,
        action_type="match_result_entered",
        entity_type="tournament_match",
        entity_id=match.id,
        new_value={"winner_team_id": match.winner_team_id, "team_a_score": a_score, "team_b_score": b_score},
    )
    if match.next_match_id:
        AuditLogService.log_action(
            user=request.user,
            action_type="winner_advanced",
            entity_type="tournament_match",
            entity_id=match.next_match_id,
            new_value={"winner_team_id": match.winner_team_id},
        )
    m_saved = (
        TournamentMatch.objects.select_related("tournament", "team_a", "team_b", "pool", "winner_team", "loser_team")
        .filter(pk=match_id)
        .first()
    )
    if m_saved:
        sync_calendar_sessions_for_tournament_match(m_saved)
    next_id = match.next_match_id
    if next_id:
        m_next = (
            TournamentMatch.objects.select_related("tournament", "team_a", "team_b", "pool", "winner_team")
            .filter(pk=next_id)
            .first()
        )
        if m_next:
            sync_calendar_sessions_for_tournament_match(m_next)
    return JsonResponse({"message": "Result saved.", "match": _serialize_match(match)})


@login_required
@require_GET
def tournament_standings(request, tournament_id):
    try:
        tournament = Tournament.objects.get(id=tournament_id)
    except Tournament.DoesNotExist:
        return JsonResponse({"errors": {"tournament": "Tournament not found."}}, status=404)
    _normalize_tournament_status(tournament)
    if not _can_view_tournament(request.user, tournament):
        return JsonResponse({"errors": {"authorization": "You do not have access to this tournament."}}, status=403)
    payload = []
    for pool in Pool.objects.filter(tournament=tournament).order_by("id"):
        _recalculate_pool_standings(tournament, pool)
        rows = []
        for row in Standing.objects.filter(tournament=tournament, pool=pool).select_related("team").order_by("rank", "id"):
            rows.append(
                {
                    "team_id": row.team_id,
                    "team_name": row.team.name,
                    "rank": row.rank,
                    "wins": row.wins,
                    "losses": row.losses,
                    "points": row.points,
                    "points_for": row.points_for,
                    "points_against": row.points_against,
                    "point_difference": row.point_difference,
                    "set_ratio": row.set_ratio,
                    "advances": row.rank <= tournament.teams_qualifying_per_pool if tournament.teams_qualifying_per_pool else False,
                }
            )
        payload.append({"pool_id": pool.id, "pool_name": pool.name, "rows": rows})
    return JsonResponse({"standings": payload})


@login_required
@require_GET
def tournament_bracket(request, tournament_id):
    try:
        tournament = Tournament.objects.get(id=tournament_id)
    except Tournament.DoesNotExist:
        return JsonResponse({"errors": {"tournament": "Tournament not found."}}, status=404)
    _normalize_tournament_status(tournament)
    if not _can_view_tournament(request.user, tournament):
        return JsonResponse({"errors": {"authorization": "You do not have access to this tournament."}}, status=403)
    matches = TournamentMatch.objects.filter(tournament=tournament, pool__isnull=True).select_related(
        "team_a", "team_b", "winner_team", "loser_team"
    )
    rounds = defaultdict(list)
    for match in matches:
        rounds[match.bracket_round or "Bracket"].append(_serialize_match(match))
    return JsonResponse({"rounds": [{"name": name, "matches": rows} for name, rows in rounds.items()]})


@login_required
@require_GET
def my_tournament_matches(request):
    team_scope = _team_ids_for_user(request.user)
    if not team_scope and not request.user.is_staff:
        return JsonResponse({"matches": []})
    matches = TournamentMatch.objects.all()
    if not request.user.is_staff:
        matches = matches.filter(Q(team_a_id__in=team_scope) | Q(team_b_id__in=team_scope))
    matches = matches.select_related("tournament", "team_a", "team_b", "pool").order_by("-scheduled_time", "id")
    return JsonResponse({"matches": [_serialize_match(match) for match in matches]})
