# esd/sofascore/client.py

"""
Sofascore client module
"""

import logging
from typing import Optional, Dict, Any # 🟢 NEW: Added imports for typing the new method
from .service import SofascoreService
from .types import (
    Event,
    Player,
    Tournament,
    Team,
    Category,
    EntityType,
    # 🟢 NEW: Import the TeamTournamentStats type
    TeamTournamentStats, 
)


class SofascoreClient:
    """
    A client to interact with the SofaScore service.
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

    # 🟢 NEW: Method to retrieve team tournament statistics (Average Goals)
    def get_team_tournament_stats(self, team_id: int, tournament_id: int) -> Optional[Dict[str, Any]]:
        """
        Fetches the raw season statistics for a team within a specific tournament.
        
        This method delegates to the SofascoreService to get the data,
        which will then be parsed by bot.py's helper function.
        """
        if not self.service:
            self.logger.error("Service not initialized. Cannot get team tournament stats.")
            return None
            
        # 💡 ASSUMPTION: The SofascoreService must implement this method.
        return self.service.get_team_tournament_stats(team_id, tournament_id)
        
    def get_events(self, date: str = 'today', live: bool = False) -> list[Event]:
        """
        Get events for a specific date or all live events.
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
    
# ... (rest of the client class) ...
