from .base import *  # noqa: F403


DEBUG = True

# Relax roster checks so directors can test fee lookup / manual fees for any user id without team membership.
# Production uses production settings (roster required). Override with DJANGO_PAYMENTS_REQUIRE_TEAM_ROSTER=true
# if you need strict roster behavior locally.
PAYMENTS_REQUIRE_TEAM_ROSTER = False

