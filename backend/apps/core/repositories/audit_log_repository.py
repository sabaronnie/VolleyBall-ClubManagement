from django.db.models import Q

from apps.core.models import (
    AuditLog,
    MatchPlayerStat,
    PlayerFeeRecord,
    Tournament,
    TournamentMatch,
    TrainingSession,
)


class AuditLogRepository:
    @staticmethod
    def create(
        *,
        user,
        user_role,
        action_type,
        entity_type,
        entity_id,
        old_value=None,
        new_value=None,
    ):
        return AuditLog.objects.create(
            user=user,
            user_role=user_role,
            action_type=action_type,
            entity_type=entity_type,
            entity_id=str(entity_id),
            old_value=old_value,
            new_value=new_value,
        )

    @staticmethod
    def list_logs(*, user_id=None, entity_type=None):
        queryset = AuditLog.objects.select_related("user").all()
        if user_id is not None:
            queryset = queryset.filter(user_id=user_id)
        if entity_type:
            queryset = queryset.filter(entity_type=entity_type)
        return queryset.order_by("-timestamp", "-id")

    @staticmethod
    def list_logs_for_club(*, club_id: int):
        tids = [str(tid) for tid in Tournament.objects.filter(club_id=club_id).values_list("id", flat=True)]
        mids = [
            str(mid)
            for mid in TournamentMatch.objects.filter(tournament__club_id=club_id).values_list("id", flat=True)
        ]
        fids = [str(fid) for fid in PlayerFeeRecord.objects.filter(club_id=club_id).values_list("id", flat=True)]
        session_ids = [
            str(sid) for sid in TrainingSession.objects.filter(team__club_id=club_id).values_list("id", flat=True)
        ]
        stat_ids = [
            str(sid)
            for sid in MatchPlayerStat.objects.filter(
                training_session__team__club_id=club_id
            ).values_list("id", flat=True)
        ]
        cond = Q()
        if tids:
            cond |= Q(entity_type="tournament", entity_id__in=tids)
        if mids:
            cond |= Q(entity_type="tournament_match", entity_id__in=mids)
        if fids:
            cond |= Q(entity_type="payment", entity_id__in=fids)
        if session_ids:
            cond |= Q(entity_type="session", entity_id__in=session_ids)
        if stat_ids:
            cond |= Q(entity_type="stats", entity_id__in=stat_ids)
        if not cond:
            return AuditLog.objects.none()
        return AuditLog.objects.select_related("user").filter(cond).order_by("-timestamp", "-id")
