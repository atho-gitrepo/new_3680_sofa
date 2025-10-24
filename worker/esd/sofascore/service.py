# esd/sofascore/service.py

"""
Sofascore service module
"""

from __future__ import annotations
import playwright
import os
import logging
import subprocess
import sys
from typing import Optional, Dict, Any # 🟢 NEW: Import for typing the new method

# Add browser installation check
# ... (install_playwright_browsers function remains the same) ...

# Install browsers before anything else (Keep this outside the class for startup efficiency)
install_playwright_browsers()

# Corrected relative imports for the local package structure
from ..utils import get_json, get_today
from .endpoints import SofascoreEndpoints
from .types import (
    Event,
    parse_event,
    parse_events,
    parse_player,
    parse_player_attributes,
    parse_transfer_history,
    parse_team,
    parse_tournament,
    parse_tournaments,
    parse_seasons,
    parse_brackets,
    parse_standings,
    parse_incidents,
    parse_top_players_match,
    parse_comments,
    parse_shots,
    parse_top_tournament_teams,
    parse_top_tournament_players,
    TopTournamentPlayers,
    TopTournamentTeams,
    Shot,
    Comment,
    TopPlayersMatch,
    Incident,
    Bracket,
    Season,
    Tournament,
    Standing,
    Team,
    Player,
    PlayerAttributes,
    TransferHistory,
    MatchStats,
    parse_match_stats,
    Lineups,
    parse_lineups,
    EntityType,
    Category,
    # 🟢 NEW: Import the TeamTournamentStats type (required for type hints)
    TeamTournamentStats, 
    parse_team_tournament_stats, # Though not used here, keep the import for completeness
)


class SofascoreService:
    # ... (rest of __init__ and __init_playwright methods remain the same) ...

    def get_team_tournament_stats(self, team_id: int, tournament_id: int) -> Optional[Dict[str, Any]]:
        """
        Get the season statistics (including average goals) for a team
        in a specific tournament.

        Args:
            team_id (int): The ID of the team.
            tournament_id (int): The ID of the tournament (league).

        Returns:
            Optional[Dict[str, Any]]: The raw JSON response data containing the statistics.
        """
        try:
            # 💡 NOTE: This endpoint assumes your Endpoints class has a method
            # to construct the URL for team tournament statistics.
            # Example endpoint structure: /team/{teamId}/tournament/{tournamentId}/statistics
            url = self.endpoints.team_tournament_stats_endpoint(team_id, tournament_id)
            
            # Use your existing Playwright/JSON fetching mechanism
            raw_data = get_json(self.page, url)
            
            # The client expects the raw dictionary, which is then parsed in bot.py
            return raw_data 
            
        except Exception as exc:
            self.logger.error(f"Failed to get team tournament stats for team {team_id} in tournament {tournament_id}: {str(exc)}")
            # Return None to signal failure to the calling function (get_team_goal_averages in bot.py)
            return None


    def get_event(self, event_id: int) -> Event:
        # ... (remains the same) ...
    # ... (all other existing methods remain the same) ...
