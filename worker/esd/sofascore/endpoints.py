# esd/sofascore/endpoints.py

class SofascoreEndpoints:
    """
    Manages all endpoint URLs for the Sofascore API.
    """
    
    # --- BASE URLS ---
    BASE_URL = "https://api.sofascore.com/api/v1/"
    EVENT_BASE_URL = BASE_URL + "event/{event_id}/"
    TEAM_BASE_URL = BASE_URL + "team/{team_id}/"
    PLAYER_BASE_URL = BASE_URL + "player/{player_id}/"
    TOURNAMENT_BASE_URL = BASE_URL + "unique-tournament/{tournament_id}/"

    # --- MATCH/EVENT ENDPOINTS ---
    
    # Used by get_events
    events_endpoint = BASE_URL + "sport/football/scheduled-events/{date}"
    
    # 🟢 CRITICAL FIX: The missing endpoint for get_live_events
    live_events_endpoint = BASE_URL + "sport/football/scheduled-events/live"
    
    # Used by get_event
    event_endpoint = EVENT_BASE_URL
    
    match_events_endpoint = EVENT_BASE_URL + "incidents"
    match_lineups_endpoint = EVENT_BASE_URL + "lineups"
    match_stats_endpoint = EVENT_BASE_URL + "statistics"
    match_probabilities_endpoint = EVENT_BASE_URL + "probabilities"
    match_top_players_endpoint = EVENT_BASE_URL + "top-players"
    match_comments_endpoint = EVENT_BASE_URL + "commentaries"
    match_shots_endpoint = EVENT_BASE_URL + "shotmap"

    # --- PLAYER ENDPOINTS ---
    
    player_endpoint = PLAYER_BASE_URL
    player_attributes_endpoint = PLAYER_BASE_URL + "attributes"
    player_transfer_history_endpoint = PLAYER_BASE_URL + "transfers"
    player_stats_endpoint = PLAYER_BASE_URL + "statistics"

    # --- TEAM ENDPOINTS ---
    
    team_endpoint = TEAM_BASE_URL
    team_players_endpoint = TEAM_BASE_URL + "players"
    team_events_endpoint = TEAM_BASE_URL + "events/{upcoming}/{page}"
    
    # 🟢 NEW: Endpoint for fetching team stats (used for goal average)
    team_tournament_stats_endpoint_template = TEAM_BASE_URL + "unique-tournament/{tournament_id}/statistics"

    # --- TOURNAMENT/LEAGUE ENDPOINTS ---
    
    tournaments_endpoint = BASE_URL + "category/{category_id}/tournaments"
    tournament_seasons_endpoint = TOURNAMENT_BASE_URL + "seasons"
    tournament_bracket_endpoint = TOURNAMENT_BASE_URL + "season/{season_id}/cup-tree"
    tournament_standings_endpoint = TOURNAMENT_BASE_URL + "season/{season_id}/standings"
    tournament_topteams_endpoint = TOURNAMENT_BASE_URL + "season/{season_id}/top-teams"
    tournament_topplayers_endpoint = TOURNAMENT_BASE_URL + "season/{season_id}/top-players"
    tournament_events_endpoint = TOURNAMENT_BASE_URL + "season/{season_id}/events/{upcoming}/{page}"

    # --- SEARCH ENDPOINTS ---
    
    search_endpoint_template = BASE_URL + "search?q={query}&entity={entity_type}"
    
    # --- HELPER METHODS ---

    def team_tournament_stats_endpoint(self, team_id: int, tournament_id: int) -> str:
        """Helper to format the team tournament stats URL."""
        return self.team_tournament_stats_endpoint_template.format(
            team_id=team_id, 
            tournament_id=tournament_id
        )

    def search_endpoint(self, query: str, entity_type: str) -> str:
        """Helper to format the search URL."""
        return self.search_endpoint_template.format(
            query=query, 
            entity_type=entity_type
        )
