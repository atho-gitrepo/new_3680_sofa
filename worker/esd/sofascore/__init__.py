# esd/sofascore/__init__.py

"""
Sofascore module
"""

# Import the main client class
from .client import SofascoreClient 

# Import and expose all necessary types from the .types submodule
from .types import (
    Event,
    Team,
    Player,
    TransferHistory,
    PlayerAttributes,
    MatchStats,
    Lineups,
    Incident,
    TopPlayersMatch,
    Comment,
    Shot,
    Tournament,
    Season,
    Bracket,
    Standing,
    TopTournamentTeams,
    TopTournamentPlayers,
    EntityType,
    Category,
    # 🟢 CRITICAL FIX: Explicitly import the new class and parser from .types
    TeamTournamentStats, 
    parse_team_tournament_stats,
)

# Import the entire types submodule as well (for users who want to access other types)
from . import types

# Update __all__ to include the new symbols you want to expose at the package level
__all__ = [
    "SofascoreClient", 
    "EntityType", 
    "TeamTournamentStats", # Must be listed here
    "parse_team_tournament_stats", # Must be listed here
    "types"
]
