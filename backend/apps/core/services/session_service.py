from apps.core.models import TrainingSession
from apps.core.services.audit_log_service import AuditLogService


def _serialize_session_for_audit(session):
    return {
        "id": session.id,
        "team_id": session.team_id,
        "title": session.title,
        "session_type": session.session_type,
        "scheduled_date": session.scheduled_date,
        "start_time": session.start_time,
        "end_time": session.end_time,
        "location": session.location,
        "opponent": session.opponent,
        "opponent_team_id": session.opponent_team_id,
        "match_type": session.match_type,
        "status": session.status,
        "notes": session.notes,
    }


def create_training_session(*, team, created_by, session_data):
    session = TrainingSession.objects.create(team=team, created_by=created_by, **session_data)
    AuditLogService.log_action(
        user=created_by,
        action_type="CREATE_SESSION",
        entity_type="session",
        entity_id=session.id,
        new_value=_serialize_session_for_audit(session),
    )
    return session


def update_training_session(*, session, actor, session_data):
    old_value = _serialize_session_for_audit(session)
    for field, value in session_data.items():
        setattr(session, field, value)
    session.save()
    AuditLogService.log_action(
        user=actor,
        action_type="UPDATE_SESSION",
        entity_type="session",
        entity_id=session.id,
        old_value=old_value,
        new_value=_serialize_session_for_audit(session),
    )
    return session


def cancel_training_session(*, session, actor):
    old_value = _serialize_session_for_audit(session)
    session.status = TrainingSession.Status.CANCELLED
    session.save(update_fields=["status", "updated_at"])
    AuditLogService.log_action(
        user=actor,
        action_type="DELETE_SESSION",
        entity_type="session",
        entity_id=session.id,
        old_value=old_value,
        new_value=_serialize_session_for_audit(session),
    )
    return session
