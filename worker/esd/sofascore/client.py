# esd/sofascore/client.py

"""
Sofascore client module wrapped with hybrid recovery fallback capability.
"""

import logging
from .service import SofascoreService
from .types import (
    Event,
    Player,
    Tournament,
    Team,
    Category,
    EntityType,
)
from .types.match_stats import parse_match_stats, MatchStats


class SofascoreClient:
    """
    A client to interact with the SofascoreService with automatic fallback mechanisms.
    """

    def __init__(self, browser_path: str = None):
        """
        Initializes the Sofascore client.
        """
        self.logger = logging.getLogger(__name__)
        self.service: SofascoreService | None = None
        self.browser_path = browser_path
        self.__initialized = False
        self.logger.info("SofascoreClient initialized (service pending).")

    def initialize(self):
        """
        Explicitly initializes the underlying service and resources.
        """
        if self.service is None:
            self.service = SofascoreService(self.browser_path)
            self.__initialized = True
            self.logger.info("SofascoreService successfully initialized.")
        else:
            self.logger.warning("SofascoreService already initialized.")

    def close(self):
        """
        Closes the underlying service and releases resources (Playwright).
        """
        if self.service:
            self.service.close()
            self.service = None
            self.__initialized = False
            self.logger.info("SofascoreClient resources closed.")

    # --- Data Retrieval Methods ---

    def get_events(self, date: str = 'today', live: bool = False) -> list[Event]:
        """
        Get events for a specific date or all live events.
        Dynamically falls back to LiveScore if SofaScore fails.
        """
        if not self.service:
            self.logger.error("Service not initialized. Cannot fetch events.")
            return []
            
        if live:
            return self.service.get_live_events()
        return self.service.get_events(date)

    def search(self, query: str, entity: EntityType = EntityType.ALL) -> list[Event | Team | Player | Tournament]:
        """
        Search query for matches, teams, players, and tournaments.
        """
        if not self.service:
            self.logger.error("Service not initialized. Cannot search.")
            return []
            
        return self.service.search(query, entity)

    def get_event(self, event_id: int) -> Event:
        """
        Get the event information.
        """
        if not self.service:
            self.logger.error("Service not initialized. Cannot get event.")
            return None
            
        return self.service.get_event(event_id)
    
    def get_player(self, player_id: int) -> Player:
        """
        Get the player information.
        """
        if not self.service:
            self.logger.error("Service not initialized. Cannot get player.")
            return None
            
        return self.service.get_player(player_id)

    def get_stats(self, event_id: int) -> MatchStats:
        """
        Fetches and parses the match statistics for a given event ID.
        Gracefully handles fallback payloads if primary provider is blocked.
        """
        if not self.service:
            self.logger.error("Service not initialized. Cannot get statistics.")
            return MatchStats()
            
        try:
            raw_stats_data = self.service.get_raw_statistics(event_id)
            raw_probabilities = self.service.get_raw_probabilities(event_id)
            return parse_match_stats(raw_stats_data, raw_probabilities)
        except Exception as e:
            self.logger.error(f"Failed parsing match statistics inside client layer: {e}")
            return MatchStats()
