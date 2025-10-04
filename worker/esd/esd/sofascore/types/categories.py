"""
Module with all tournament categories.
"""

from enum import Enum


class Category(Enum):
    """
    Enum with all tournament categories (Asia, Europe, World, etc).
    """

    AFRICA = 1466
    ASIA = 1467
    EUROPE = 1465
    WORLD = 1468
    NORTH_AMERICA = 1469
    SOUTH_AMERICA = 1470
    OCEANIA = 1471
