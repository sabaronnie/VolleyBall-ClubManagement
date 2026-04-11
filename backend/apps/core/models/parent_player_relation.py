from django.conf import settings
from django.db import models


class ParentPlayerRelationQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def inactive(self):
        return self.filter(is_active=False)

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

    def link(self, *, parent, player, is_legal_guardian=False):
        relation, created = self.update_or_create(
            parent=parent,
            player=player,
            defaults={
                "is_active": True,
                "is_legal_guardian": is_legal_guardian,
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
