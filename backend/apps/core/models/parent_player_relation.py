from django.conf import settings
from django.db import models


class ParentLinkApprovalStatus(models.TextChoices):
    PENDING = "pending", "Pending director approval"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"


class ParentPlayerRelationQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def inactive(self):
        return self.filter(is_active=False)

    def approved(self):
        """Active links directors have approved (used for access, emails, fees)."""
        return self.active().filter(approval_status=ParentLinkApprovalStatus.APPROVED)

    def pending(self):
        return self.active().filter(approval_status=ParentLinkApprovalStatus.PENDING)

    def for_parent(self, parent):
        return self.filter(parent=parent)

    def for_player(self, player):
        return self.filter(player=player)


class ParentPlayerRelationManager(models.Manager):
    def get_queryset(self):
        return ParentPlayerRelationQuerySet(self.model, using=self._db)

    def active(self):
        return self.get_queryset().active()

    def inactive(self):
        return self.get_queryset().inactive()

    def approved(self):
        return self.get_queryset().approved()

    def pending(self):
        return self.get_queryset().pending()

    def link(self, *, parent, player, is_legal_guardian=False, approval_status=ParentLinkApprovalStatus.APPROVED):
        relation, created = self.update_or_create(
            parent=parent,
            player=player,
            defaults={
                "is_active": True,
                "is_legal_guardian": is_legal_guardian,
                "approval_status": approval_status,
            },
        )
        return relation, created

    def deactivate(self, relation):
        relation.is_active = False
        relation.save(update_fields=["is_active"])
        return relation


class ParentPlayerRelation(models.Model):
    parent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="player_relationships",
    )
    player = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="parent_relationships",
    )
    is_legal_guardian = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    approval_status = models.CharField(
        max_length=20,
        choices=ParentLinkApprovalStatus.choices,
        default=ParentLinkApprovalStatus.APPROVED,
    )

    objects = ParentPlayerRelationManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["parent", "player"],
                name="unique_parent_player_relation",
            )
        ]

    def __str__(self) -> str:
        return f"{self.parent} -> {self.player}"
