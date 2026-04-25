from django.db import transaction

from apps.core.models import MatchPlayerStat, TrainingSession
from apps.core.services.audit_log_service import AuditLogService


def save_match_player_stat(*, session, player, stat_data, actor):
    with transaction.atomic():
        TrainingSession.objects.select_for_update().filter(pk=session.pk).exists()
        existing = MatchPlayerStat.objects.filter(training_session=session, player=player).first()
        old_value = None
        if existing is not None:
            old_value = {
                "points_scored": existing.points_scored,
                "aces": existing.aces,
                "blocks": existing.blocks,
                "assists": existing.assists,
                "errors": existing.errors,
                "digs": existing.digs,
            }
        stat, _ = MatchPlayerStat.objects.update_or_create(
            training_session=session,
            player=player,
            defaults={**stat_data, "updated_by": actor},
        )

    AuditLogService.log_action(
        user=actor,
        action_type="UPDATE_STATS",
        entity_type="stats",
        entity_id=stat.id,
        old_value=old_value,
        new_value={
            "training_session_id": stat.training_session_id,
            "player_id": stat.player_id,
            "points_scored": stat.points_scored,
            "aces": stat.aces,
            "blocks": stat.blocks,
            "assists": stat.assists,
            "errors": stat.errors,
            "digs": stat.digs,
        },
    )
    return stat
