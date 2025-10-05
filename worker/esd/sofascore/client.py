"""
This module contains the client class for interacting with the Sofascore API.
"""

from __future__ import annotations
import logging
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
        self.__service = SofascoreService(browser_path)
        self.__initialized = True
        self.logger.info("SofascoreClient initialized successfully")

    def initialize(self) -> None:
        """
        Explicitly initialize the client.
        This can be useful for testing or delayed initialization.
        """
        if not hasattr(self, '__initialized') or not self.__initialized:
            self.logger.info("Initializing SofascoreClient...")
            # Re-initialize service if needed
            self.__initialized = True
            self.logger.info("SofascoreClient initialized successfully")

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

    def get_events(self, date: str = 'today', live: bool = False) -> list[Event]:
        """
        Get the scheduled events.

        Args:
            date (str): The date of the events in the format "YYYY-MM-DD" or "today".
            live (bool): Whether to get the live events (more precise).

        Returns:
            list[Event]: The scheduled events.
        """
        self.initialize()
        if live:
            return self.__service.get_live_events()
        return self.__service.get_events(date)

    def get_event(self, event_id: int) -> Event:
        """
        Get the event information.

        Args:
            event_id (int): The event id.

        Returns:
            Event: The event information.
        """
        self.initialize()
        return self.__service.get_event(event_id)

    def get_player(self, player_id: int) -> Player:
        """
        Get the player information.

        Args:
            player_id (int): The player id.

        Returns:
            Player: The player information.
        """
        self.initialize()
        return self.__service.get_player(player_id)

    def get_match_incidents(self, event_id: int) -> list[Incident]:
        """
        Get the events of a match.

        Args:
            event_id (int): The event id.

        Returns:
            list[Incident]: The match incidents.
        """
        self.initialize()
        return self.__service.get_match_incidents(event_id)

    def get_match_top_players(self, event_id: int) -> TopPlayersMatch:
        """
        Get the top players of a match.

        Args:
            event_id (int): The event id.

        Returns:
            TopPlayersMatch: The match top players.
        """
        self.initialize()
        return self.__service.get_match_top_players(event_id)

    def get_match_comments(self, event_id: int) -> list[Comment]:
        """
        Get the comments of a match.

        Args:
            event_id (int): The event id.

        Returns:
            list[Comment]: The match comments.
        """
        self.initialize()
        return self.__service.get_match_comments(event_id)

    def get_match_stats(self, event_id: int) -> MatchStats:
        """
        Get the match statistics by event id.

        Args:
            event_id (int): The event id (also known as match id).

        Returns:
            MatchStats: The match statistics.
        """
        self.initialize()
        return self.__service.get_match_stats(event_id)

    def get_match_lineups(self, event_id: int) -> Lineups:
        """
        Get the match lineups.

        Args:
            event_id (int): The event id.

        Returns:
            Lineups: The match lineups.
        """
        self.initialize()
        return self.__service.get_match_lineups(event_id)

    def get_match_shots(self, event_id: int) -> list[Shot]:
        """
        Get the shots of a match.

        Args:
            event_id (int): The event id.

        Returns:
            list[Shot]: The match shots.
        """
        self.initialize()
        return self.__service.get_match_shots(event_id)

    def get_team(self, team_id: int) -> Team:
        """
        Get detailed information about a team.

        Args:
            team_id (int): The team id.

        Returns:
            TeamEx: The team information.
        """
        self.initialize()
        team: Team = self.__service.get_team(team_id)
        players: list[Player] = self.__service.get_team_players(team_id)
        team.players = players
        return team

    def get_team_players(self, team_id: int) -> list[Player]:
        """
        Get the players of a team.

        Args:
            team_id (int): The team id.

        Returns:
            list[Player]: The players of the team.
        """
        self.initialize()
        return self.__service.get_team_players(team_id)

    def get_team_events(
        self, team_id: int, upcoming: bool = False, page: int = 0
    ) -> list[Event]:
        """
        Get the events (matchs) of a team.

        Args:
            team_id (int): The team id.
            upcoming (bool): Whether to get the upcoming events.
            page (int): The page number.

        Returns:
            list[Event]: The events of the team.
        """
        self.initialize()
        return self.__service.get_team_events(team_id, upcoming, page)

    def get_tournaments(self, category_id: Category) -> list[Tournament]:
        """
        Get the tournaments by category.
        TODO: maybe add a argument to include seasons.

        Args:
            category_id (Category): The category id.

        Returns:
            list[Tournament]: The tournaments.
        """
        self.initialize()
        return self.__service.get_tournaments_by_category(category_id)

    def get_tournament_seasons(self, tournament_id: int) -> list[Season]:
        """
        Get the seasons of a tournament.

        Args:
            tournament_id (int): The tournament id.

        Returns:
            list[Season]: The seasons of the tournament.
        """
        self.initialize()
        return self.__service.get_tournament_seasons(tournament_id)

    def get_tournament_brackets(
        self, tournament_id: int | Tournament, season_id: int | Season
    ) -> list[Bracket]:
        """
        Get the tournament bracket.

        Args:
            tournament_id (int, Tournament): The tournament id.
            season_id (int, Season): The season id.

        Returns:
            list[Bracket]: The tournament bracket.
        """
        self.initialize()
        return self.__service.get_tournament_bracket(tournament_id, season_id)

    def get_tournament_standings(
        self, tournament_id: int | Tournament, season_id: int | Season
    ) -> list[Standing]:
        """
        Get the tournament standings.

        Args:
            tournament_id (int, Tournament): The tournament id.
            season_id (int, Season): The season id.

        Returns:
            list[Standing]: The tournament standings.
        """
        self.initialize()
        return self.__service.get_tournament_standings(tournament_id, season_id)

    def get_tournament_top_teams(
        self, tournament_id: int | Tournament, season_id: int | Season
    ) -> TopTournamentTeams:
        """
        Get the top teams of the tournament.

        Args:
            tournament_id (int, Tournament): The tournament id.
            season_id (int, Season): The season id.

        Returns:
            TopTournamentTeams: The top teams of the tournament.
        """
        self.initialize()
        return self.__service.get_tournament_top_teams(tournament_id, season_id)

    def get_tournament_top_players(
        self, tournament_id: int | Tournament, season_id: int | Season
    ) -> TopTournamentPlayers:
        """
        Get the top players of the tournament.

        Args:
            tournament_id (int, Tournament): The tournament id.
            season_id (int, Season): The season id.

        Returns:
            TopTournamentPlayers: The top players of the tournament.
        """
        self.initialize()
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

        Args:
            tournament_id (int, Tournament): The tournament id.
            season_id (int, Season): The season id.
            upcoming (bool): Whether to get the upcoming events.
            page (int): The page number.

        Returns:
            list[Event]: The events of the tournament.
        """
        self.initialize()
        return self.__service.get_tournament_events(
            tournament_id, season_id, upcoming, page
        )

    def search(
        self, query: str, entity: str | EntityType = EntityType.ALL
    ) -> list[Event | Team | Player | Tournament]:
        """
        Search query for matches, teams, players, and tournaments.

        Args:
            query (str): The search query.
            entity (str, EntityType): The entity type to search for.

        Returns:
            list[Event | Team | Player | Tournament]: The search results.
        """
        self.initialize()
        if isinstance(entity, str):
            entity = EntityType(entity)
        return self.__service.search(query, entity)