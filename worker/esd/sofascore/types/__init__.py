"""
Contains the types for the Sofascore service.
"""

from .event import Event, parse_events, parse_event
from .status import StatusType, Status
from .team import Team, parse_team
from .player import Player, parse_player
from .player_attributes import PlayerAttributes, parse_player_attributes
from .transfer import TransferHistory, parse_transfer_history
from .match_stats import MatchStats, parse_match_stats
from .lineup import Lineups, PlayerLineup, TeamColor, TeamLineup, parse_lineups
from .shot import Shot, parse_shots
from .tournament import Tournament, parse_tournaments, parse_tournament
from .season import Season, parse_seasons, parse_season
from .bracket import Bracket, parse_bracket, parse_brackets
from .standing import Standing, parse_standing, parse_standings
from .incident import Incident, IncidentType, parse_incident, parse_incidents
from .top import TopPlayersMatch, parse_top_players_match
from .comment import Comment, CommentType, parse_comments
from .top_tournament_teams import TopTournamentTeams, parse_top_tournament_teams
from .top_tournament_players import TopTournamentPlayers, parse_top_tournament_players
from .entity import EntityType
from .categories import Category


__all__ = [
    "Event",
    "parse_events",
    "parse_event",
    "Tournament",
    "parse_tournaments",
    "parse_tournament",
    "TopTournamentPlayers",
    "parse_top_tournament_players",
    "TopTournamentTeams",
    "parse_top_tournament_teams",
    "Shot",
    "parse_shots",
    "Comment",
    "CommentType",
    "parse_comments",
    "TopPlayersMatch",
    "parse_top_players_match",
    "Incident",
    "IncidentType",
    "parse_incident",
    "parse_incidents",
    "Standing",
    "parse_standing",
    "parse_standings",
    "Season",
    "parse_seasons",
    "parse_season",
    "Bracket",
    "parse_bracket",
    "parse_brackets",
    "Team",
    "parse_team",
    "Player",
    "parse_player",
    "TransferHistory",
    "parse_transfer_history",
    "PlayerAttributes",
    "parse_player_attributes",
    "MatchStats",
    "parse_match_stats",
    "Lineups",
    "PlayerLineup",
    "TeamColor",
    "TeamLineup",
    "parse_lineups",
    "EntityType",
    "Category",
    "StatusType",
    "Status",
]
