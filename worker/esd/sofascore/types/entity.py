"""
Module with entity types.

All entities are used in the search endpoint also each entity has its own baseclass.
"""

from enum import Enum


class EntityType(Enum):
    """
    Enum with all entity types.
    """

    ALL = "all"
    TEAM = "teams"
    PLAYER = "player-team-persons"
    TOURNAMENT = "unique-tournaments"
    EVENT = "events"
