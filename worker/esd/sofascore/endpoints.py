# esd/sofascore/endpoints.py

"""
This module contains the endpoints of the SofaScore API.
"""


class SofascoreEndpoints:
    """
    A class to represent the endpoints of the SofaScore API.
    """

    def __init__(self, base_url: str = "https://api.sofascore.com/api/v1") -> None:
        self.base_url = base_url

    # 🟢 NEW: Endpoint for retrieving team tournament statistics (Average Goals)
    def team_tournament_stats_endpoint(self, team_id: int, tournament_id: int) -> str:
        """
        Returns the URL of the endpoint to get a team's season-long statistics 
        in a specific tournament (league).

        Args:
            team_id (int): The ID of the team.
            tournament_id (int): The ID of the tournament (league).

        Returns:
            str: The URL of the endpoint to get the team tournament statistics.
        """
        return f"{self.base_url}/team/{team_id}/unique-tournament/{tournament_id}/statistics"
        # NOTE: Sofascore API URLs sometimes change. The common pattern is:
        # /team/{teamId}/unique-tournament/{tournamentId}/statistics
        # or sometimes:
        # /team/{teamId}/tournament/{tournamentId}/statistics 
        # I am using the one that includes 'unique-tournament' as it is generally more common.
        # If this URL fails, try removing 'unique-'.
    
    @property
    def events_endpoint(self) -> str:
        # ... (remains the same) ...
        """
        Returns the URL of the endpoint to get the scheduled events.

        Returns:
            str: The URL of the endpoint to get the scheduled events.
        """
        return self.base_url + "/sport/football/scheduled-events/{date}"

    # ... (all other existing methods remain the same) ...
    # The new method is added near the top for visibility and easy integration.
