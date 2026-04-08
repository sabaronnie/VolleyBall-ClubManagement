from django.conf import settings
from django.db import models


class ParentPlayerRelationQuerySet(models.QuerySet):
    def for_parent(self, parent):
        return self.filter(parent=parent)

    def for_player(self, player):
        return self.filter(player=player)


class ParentPlayerRelationManager(models.Manager):
    def get_queryset(self):
        return ParentPlayerRelationQuerySet(self.model, using=self._db)

    def link(self, *, parent, player):
        relation, _ = self.get_or_create(parent=parent, player=player)
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
