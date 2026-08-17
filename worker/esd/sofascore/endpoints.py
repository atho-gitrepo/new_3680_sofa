"""
This module contains the combined hybrid endpoints and client profiles for the 
SofaScore and LiveScore APIs to handle fallback routing and anti-blocking transparently.
"""

from typing import Union, Dict, Any, Tuple

class HybridEndpoints:
    """
    A unified configuration layer to dynamically generate URLs, optimal request parameters,
    and anti-blocking headers for SofaScore and LiveScore API execution components.
    """

    def __init__(
        self, 
        sofa_base: str = "https://api.sofascore.com/api/v1",
        live_base: str = "https://prod-public-api.livescore.com/v1/api/app"
    ) -> None:
        self.sofa_base = sofa_base
        self.live_base = live_base

    def get_provider_profile(self, provider: str = "sofascore") -> Dict[str, Any]:
        """
        Generates dynamic anti-blocking header blueprints customized per provider platform.
        These are designed to bypass basic Cloudflare fingerprint tracking checks.
        """
        if provider == "livescore":
            return {
                "headers": {
                    "User-Agent": "LiveScore/5.23.0 (iPhone; iOS 16.5; Scale/3.00)",
                    "Accept": "application/json, text/plain, */*",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Origin": "https://www.livescore.com",
                    "Referer": "https://www.livescore.com/",
                    "Cache-Control": "no-cache"
                },
                "timeout": 10.0
            }
        
        # Default Profile: SofaScore Web App Emulation Blueprint
        return {
            "headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Accept": "*/*",
                "Accept-Language": "en-US,en;q=0.5",
                "Cache-Control": "no-cache",
                "Origin": "https://www.sofascore.com",
                "Referer": "https://www.sofascore.com/",
                "X-Sofascore-Client": "web"
            },
            "timeout": 8.0
        }

    # --- Global / Live Event Endpoints ---
    def get_events_endpoint(self, date: str, provider: str = "sofascore") -> Tuple[str, Dict[str, Any]]:
        if provider == "livescore":
            sanitized_date = date.replace("-", "")
            return f"{self.live_base}/date/soccer/{sanitized_date}/0.00", {"MD": "1"}
        return f"{self.sofa_base}/sport/football/scheduled-events/{date}", {}

    def get_live_events_endpoint(self, provider: str = "sofascore") -> Tuple[str, Dict[str, Any]]:
        if provider == "livescore":
            return f"{self.live_base}/live/soccer/0.00", {"MD": "1"}
        return f"{self.sofa_base}/sport/football/events/live", {}

    # --- Match Specific Endpoints ---
    def event_endpoint(self, event_id: Union[int, str], provider: str = "sofascore") -> Tuple[str, Dict[str, Any]]:
        if provider == "livescore":
            return f"{self.live_base}/detail/soccer/{event_id}", {}
        return f"{self.sofa_base}/event/{event_id}", {}

    def match_stats_endpoint(self, event_id: Union[int, str], provider: str = "sofascore") -> Tuple[str, Dict[str, Any]]:
        if provider == "livescore":
            return f"{self.live_base}/statistics/soccer/{event_id}", {}
        return f"{self.sofa_base}/event/{event_id}/statistics", {}

    def match_events_endpoint(self, event_id: Union[int, str], provider: str = "sofascore") -> Tuple[str, Dict[str, Any]]:
        if provider == "livescore":
            return f"{self.live_base}/incidents/soccer/{event_id}", {}
        return f"{self.sofa_base}/event/{event_id}/incidents", {}

    def match_lineups_endpoint(self, event_id: Union[int, str], provider: str = "sofascore") -> Tuple[str, Dict[str, Any]]:
        if provider == "livescore":
            return f"{self.live_base}/lineups/soccer/{event_id}", {}
        return f"{self.sofa_base}/event/{event_id}/lineups", {}

    def match_comments_endpoint(self, event_id: Union[int, str], provider: str = "sofascore") -> Tuple[str, Dict[str, Any]]:
        if provider == "livescore":
            return f"{self.live_base}/commentary/soccer/{event_id}", {}
        return f"{self.sofa_base}/event/{event_id}/comments", {}

    def match_probabilities_endpoint(self, event_id: Union[int, str], provider: str = "sofascore") -> Tuple[str, Dict[str, Any]]:
        if provider == "livescore":
            return "", {}
        return f"{self.sofa_base}/event/{event_id}/win-probability", {}

    def match_top_players_endpoint(self, event_id: Union[int, str], provider: str = "sofascore") -> Tuple[str, Dict[str, Any]]:
        if provider == "livescore":
            return "", {}
        return f"{self.sofa_base}/event/{event_id}/best-players/summary", {}

    def match_shots_endpoint(self, event_id: Union[int, str], provider: str = "sofascore") -> Tuple[str, Dict[str, Any]]:
        if provider == "livescore":
            return "", {}
        return f"{self.sofa_base}/event/{event_id}/shotmap", {}

    # --- Search ---
    def search_endpoint(self, query: str, entity_type: str = "", provider: str = "sofascore") -> Tuple[str, Dict[str, Any]]:
        if provider == "livescore":
            return f"https://search-api.livescore.com/v1/api/app/search/{query}", {}
        
        url = f"{self.sofa_base}/search"
        if entity_type:
            url += f"/{entity_type}"
        return url, {"q": query, "page": "0"}

    # --- Player Endpoints ---
    def player_endpoint(self, player_id: Union[int, str], provider: str = "sofascore") -> Tuple[str, Dict[str, Any]]:
        if provider == "livescore":
            return f"{self.live_base}/player/{player_id}", {}
        return f"{self.sofa_base}/player/{player_id}", {}

    def player_stats_endpoint(self, player_id: Union[int, str], provider: str = "sofascore") -> Tuple[str, Dict[str, Any]]:
        if provider == "livescore":
            return f"{self.live_base}/player/{player_id}/statistics", {}
        return f"{self.sofa_base}/player/{player_id}/statistics", {}

    def player_transfer_history_endpoint(self, player_id: Union[int, str], provider: str = "sofascore") -> Tuple[str, Dict[str, Any]]:
        if provider == "livescore":
            return f"{self.live_base}/player/{player_id}/transfers", {}
        return f"{self.sofa_base}/player/{player_id}/transfer-history", {}

    def player_charac_endpoint(self, player_id: Union[int, str], provider: str = "sofascore") -> Tuple[str, Dict[str, Any]]:
        if provider == "livescore": 
            return "", {}
        return f"{self.sofa_base}/player/{player_id}/characteristics", {}

    def player_attributes_endpoint(self, player_id: Union[int, str], provider: str = "sofascore") -> Tuple[str, Dict[str, Any]]:
        if provider == "livescore": 
            return "", {}
        return f"{self.sofa_base}/player/{player_id}/attribute-overviews", {}

    # --- Team Endpoints ---
    def team_endpoint(self, team_id: Union[int, str], provider: str = "sofascore") -> Tuple[str, Dict[str, Any]]:
        if provider == "livescore":
            return f"{self.live_base}/team/soccer/{team_id}", {}
        return f"{self.sofa_base}/team/{team_id}", {}

    def team_players_endpoint(self, team_id: Union[int, str], provider: str = "sofascore") -> Tuple[str, Dict[str, Any]]:
        if provider == "livescore":
            return f"{self.live_base}/team/soccer/{team_id}/squad", {}
        return f"{self.sofa_base}/team/{team_id}/players", {}

    def team_events_endpoint(self, team_id: Union[int, str], upcoming: bool, page: int = 1, provider: str = "sofascore") -> Tuple[str, Dict[str, Any]]:
        if provider == "livescore":
            _from = "results" if not upcoming else "fixtures"
            return f"{self.live_base}/team/soccer/{team_id}/{_from}", {}
        _from = "last" if not upcoming else "next"
        return f"{self.sofa_base}/team/{team_id}/events/{_from}/{page}", {}

    # --- Tournament / League Endpoints ---
    def tournaments_endpoint(self, category_id: Union[int, str], provider: str = "sofascore") -> Tuple[str, Dict[str, Any]]:
        if provider == "livescore":
            return f"{self.live_base}/category/soccer/{category_id}", {}
        return f"{self.sofa_base}/category/{category_id}/unique-tournaments", {}

    def tournament_seasons_endpoint(self, tournament_id: Union[int, str], provider: str = "sofascore") -> Tuple[str, Dict[str, Any]]:
        if provider == "livescore":
            return f"{self.live_base}/competitions/soccer/{tournament_id}/seasons", {}
        return f"{self.sofa_base}/unique-tournament/{tournament_id}/seasons", {}

    def tournament_bracket_endpoint(self, tournament_id: Union[int, str], season_id: Union[int, str], provider: str = "sofascore") -> Tuple[str, Dict[str, Any]]:
        if provider == "livescore":
            return f"{self.live_base}/competitions/soccer/{tournament_id}/{season_id}/draws", {}
        return f"{self.sofa_base}/unique-tournament/{tournament_id}/season/{season_id}/cuptrees", {}

    def tournament_standings_endpoint(self, tournament_id: Union[int, str], season_id: Union[int, str], provider: str = "sofascore") -> Tuple[str, Dict[str, Any]]:
        if provider == "livescore":
            return f"{self.live_base}/standings/soccer/{tournament_id}/{season_id}", {}
        return f"{self.sofa_base}/unique-tournament/{tournament_id}/season/{season_id}/standings/total", {}

    def tournament_topplayers_endpoint(self, tournament_id: Union[int, str], season_id: Union[int, str], provider: str = "sofascore") -> Tuple[str, Dict[str, Any]]:
        if provider == "livescore":
            return f"{self.live_base}/top-scorers/soccer/{tournament_id}/{season_id}", {}
        return f"{self.sofa_base}/unique-tournament/{tournament_id}/season/{season_id}/top-players/overall", {}

    def tournament_topteams_endpoint(self, tournament_id: Union[int, str], season_id: Union[int, str], provider: str = "sofascore") -> Tuple[str, Dict[str, Any]]:
        if provider == "livescore": 
            return "", {}
        return f"{self.sofa_base}/unique-tournament/{tournament_id}/season/{season_id}/top-teams/overall", {}

    def tournament_events_endpoint(self, tournament_id: Union[int, str], season_id: Union[int, str], upcoming: bool, page: int = 1, provider: str = "sofascore") -> Tuple[str, Dict[str, Any]]:
        if provider == "livescore":
            _from = "results" if not upcoming else "fixtures"
            return f"{self.live_base}/competitions/soccer/{tournament_id}/{season_id}/{_from}", {}
        _from = "last" if not upcoming else "next"
        return f"{self.sofa_base}/unique-tournament/{tournament_id}/season/{season_id}/events/{_from}/{page}", {}