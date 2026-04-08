from django.conf import settings
from django.db import models


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

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["parent", "player"],
                name="unique_parent_player_relation",
            )
        ]

    def __str__(self) -> str:
        return f"{self.parent} -> {self.player}"
