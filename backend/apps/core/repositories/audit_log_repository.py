from apps.core.models import AuditLog


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
