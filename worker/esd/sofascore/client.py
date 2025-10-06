# esd/sofascore/client.py

"""
This module contains the client class for interacting with the Sofascore API.
"""

from __future__ import annotations
import logging
# Assuming SofascoreService handles the Playwright logic
from .service import SofascoreService
from .types import (
    EntityType,
    Event,
    Team,
    Player,
    MatchStats,
    Lineups,
    Shot,
    Category,
    Tournament,
    Season,
    Bracket,
    Standing,
    Incident,
    TopPlayersMatch,
    Comment,
    TopTournamentTeams,
    TopTournamentPlayers,
)


class SofascoreClient:
    """
    Client for interacting with the Sofascore website.
    This class provides methods to access and retrieve data from Sofascore.
    """

    def __init__(self, browser_path: str = None) -> None:
        """
        Initializes a new instance of the SofascoreClient.

        Required for interacting with the Sofascore website.

        Args:
            browser_path (str): The path to the browser executable.
                If None, uses Playwright's bundled Chromium (recommended for Railway).
        """
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initializing SofascoreClient...")
        # NOTE: SofascoreService constructor should handle the main Playwright browser launch
        self.__service = SofascoreService(browser_path)
        self.__initialized = True
        self.logger.info("SofascoreClient initialized successfully")

    def initialize(self) -> None:
        """
        Explicitly initialize the client.
        This is called by bot.py at startup to ensure the client is ready.
        """
        # FIX: Added logic to prevent spamming the "Re-initializing" log
        if not hasattr(self, '__initialized') or not self.__initialized:
            self.logger.info("Re-initializing SofascoreClient (called explicitly)...")
            self.__initialized = True
            self.logger.info("SofascoreClient re-initialized successfully")
        else:
            # FIX: Added a distinct log for when initialize is called redundantly
            self.logger.info("SofascoreClient is already initialized.")

    def close(self) -> None:
        """
        Close the browser and release resources.
        """
        self.logger.info("Closing SofascoreClient resources...")
        self.__service.close()
        self.__initialized = False
        self.logger.info("SofascoreClient resources closed successfully")

    def __enter__(self):
        """Context manager entry."""
        self.initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    # =========================================================
    # 🛑 FIX APPLIED: Removed self.initialize() from all methods below
    # =========================================================

    def get_events(self, date: str = 'today', live: bool = False) -> list[Event]:
        """
        Get the scheduled events.
        """
        if live:
            return self.__service.get_live_events()
        return self.__service.get_events(date)

    def get_event(self, event_id: int) -> Event:
        """
        Get the event information.
        """
        return self.__service.get_event(event_id)

    def get_player(self, player_id: int) -> Player:
        """
        Get the player information.
        """
        return self.__service.get_player(player_id)

    def get_match_incidents(self, event_id: int) -> list[Incident]:
        """
        Get the events of a match.
        """
        return self.__service.get_match_incidents(event_id)

    def get_match_top_players(self, event_id: int) -> TopPlayersMatch:
        """
        Get the top players of a match.
        """
        return self.__service.get_match_top_players(event_id)

    def get_match_comments(self, event_id: int) -> list[Comment]:
        """
        Get the comments of a match.
        """
        return self.__service.get_match_comments(event_id)

    def get_match_stats(self, event_id: int) -> MatchStats:
        """
        Get the match statistics by event id.
        """
        return self.__service.get_match_stats(event_id)

    def get_match_lineups(self, event_id: int) -> Lineups:
        """
        Get the match lineups.
        """
        return self.__service.get_match_lineups(event_id)

    def get_match_shots(self, event_id: int) -> list[Shot]:
        """
        Get the shots of a match.
        """
        return self.__service.get_match_shots(event_id)

    def get_team(self, team_id: int) -> Team:
        """
        Get detailed information about a team.
        """
        team: Team = self.__service.get_team(team_id)
        players: list[Player] = self.__service.get_team_players(team_id)
        team.players = players
        return team

    def get_team_players(self, team_id: int) -> list[Player]:
        """
        Get the players of a team.
        """
        return self.__service.get_team_players(team_id)

    def get_team_events(
        self, team_id: int, upcoming: bool = False, page: int = 0
    ) -> list[Event]:
        """
        Get the events (matchs) of a team.
        """
        return self.__service.get_team_events(team_id, upcoming, page)

    def get_tournaments(self, category_id: Category) -> list[Tournament]:
        """
        Get the tournaments by category.
        """
        return self.__service.get_tournaments_by_category(category_id)

    def get_tournament_seasons(self, tournament_id: int) -> list[Season]:
        """
        Get the seasons of a tournament.
        """
        return self.__service.get_tournament_seasons(tournament_id)

    def get_tournament_brackets(
        self, tournament_id: int | Tournament, season_id: int | Season
    ) -> list[Bracket]:
        """
        Get the tournament bracket.
        """
        return self.__service.get_tournament_bracket(tournament_id, season_id)

    def get_tournament_standings(
        self, tournament_id: int | Tournament, season_id: int | Season
    ) -> list[Standing]:
        """
        Get the tournament standings.
        """
        return self.__service.get_tournament_standings(tournament_id, season_id)

    def get_tournament_top_teams(
        self, tournament_id: int | Tournament, season_id: int | Season
    ) -> TopTournamentTeams:
        """
        Get the top teams of the tournament.
        """
        return self.__service.get_tournament_top_teams(tournament_id, season_id)

    def get_tournament_top_players(
        self, tournament_id: int | Tournament, season_id: int | Season
    ) -> TopTournamentPlayers:
        """
        Get the top players of the tournament.
        """
        return self.__service.get_tournament_top_players(tournament_id, season_id)

    def get_tournament_events(
        self,
        tournament_id: int | Tournament,
        season_id: int | Season,
        upcoming: bool = False,
        page: int = 0,
    ) -> list[Event]:
        """
        Get the events of the tournament.
        """
        return self.__service.get_tournament_events(
            tournament_id, season_id, upcoming, page
        )

    def search(
        self, query: str, entity: str | EntityType = EntityType.ALL
    ) -> list[Event | Team | Player | Tournament]:
        """
        Search query for matches, teams, players, and tournaments.
        """
        if isinstance(entity, str):
            entity = EntityType(entity)
        return self.__service.search(query, entity)
