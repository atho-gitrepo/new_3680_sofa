from dataclasses import dataclass, field
from typing import Optional, Dict, Any

@dataclass
class TeamTournamentStats:
    """
    Data class to hold a team's season-long statistics within a specific tournament.
    
    This is what the bot requires to check the 2.38 average goal condition.
    """

    # Team ID and Tournament ID for context
    team_id: int = field(default=0)
    tournament_id: int = field(default=0)
    
    # Crucial fields for the betting condition (Total Average = Scored + Conceded)
    average_goals_scored: float = field(default=0.0)
    average_goals_conceded: float = field(default=0.0)
    
    # Optional fields you might find in the Sofascore API response (for completeness)
    average_cards_total: Optional[float] = field(default=None)
    average_corner_kicks: Optional[float] = field(default=None)
    matches_played: Optional[int] = field(default=None)
    
    @property
    def total_average_goals(self) -> float:
        """
        Calculates the combined average of goals scored and conceded.
        This is the value checked against the MAX_GOAL_AVERAGE (2.38).
        """
        return self.average_goals_scored + self.average_goals_conceded


def parse_team_tournament_stats(team_id: int, tournament_id: int, data: Dict[str, Any]) -> TeamTournamentStats:
    """
    Parses the raw dictionary response from the Sofascore API endpoint 
    (e.g., /team/{team_id}/tournament/{tournament_id}/statistics) 
    into the TeamTournamentStats object.
    
    Args:
        team_id (int): The ID of the team.
        tournament_id (int): The ID of the tournament.
        data (Dict[str, Any]): The raw statistics data retrieved from the Sofascore API.

    Returns:
        TeamTournamentStats: The parsed statistics object.
    """
    
    # Sofascore data often nests the actual statistics inside a 'statistics' key.
    stats = data.get('statistics', data)

    # 💡 IMPORTANT: These key names must exactly match what the Sofascore API returns 
    # for the team statistics endpoint. Adjust if necessary after inspecting the response.
    
    return TeamTournamentStats(
        team_id=team_id,
        tournament_id=tournament_id,
        average_goals_scored=stats.get("averageGoalsScored", 0.0),
        average_goals_conceded=stats.get("averageGoalsConceded", 0.0),
        
        # Example of other fields you might parse
        average_cards_total=stats.get("averageTotalCards", None),
        average_corner_kicks=stats.get("averageCornerKicks", None),
        matches_played=stats.get("matchesPlayed", None),
    )
