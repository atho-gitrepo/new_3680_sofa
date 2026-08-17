"""
Contains the event data types and parsers (also known as matches).
Handles hybrid parsing workflows for both SofaScore and LiveScore data structures,
ensuring pitch time descriptions are fully normalized.
"""

import time
import logging
from datetime import datetime
from dataclasses import dataclass, field
from .team import Team, parse_team
from .team_score import TeamScore, parse_team_score
from .tournament import Tournament, parse_tournament
from .status import Status, parse_status

logger = logging.getLogger("BetBot.TypeParser")

@dataclass
class Season:
    """
    Season data class.
    """
    name: str
    year: str
    editor: bool
    season_coverage_info: dict
    id: int


@dataclass
class RoundInfo:
    """
    Round info data class.
    """
    round: int
    name: str
    cup_round_type: int


@dataclass
class TimeEvent:
    """
    Time event data class, half time, extra time, etc.
    """
    first_injury_time: int = 0
    second_injury_time: int = 0
    third_injury_time: int = 0
    quarter_injury_time: int = 0
    current_period_start: int = 0


@dataclass
class StatusTime:
    """
    Current status time data class.
    """
    initial: int = 0
    max: int = 0
    timestamp: int = 0
    extra: int = 0


@dataclass
class Event:
    """
    Event data class also known as match.
    """
    id: int = field(default=0)
    status: Status = field(default_factory=Status)
    home_team: Team = field(default_factory=Team)
    home_score: TeamScore = field(default_factory=TeamScore)
    away_team: Team = field(default_factory=Team)
    away_score: TeamScore = field(default_factory=TeamScore)
    time: TimeEvent = field(default_factory=TimeEvent)
    tournament: Tournament = field(default_factory=Tournament)
    status_time: StatusTime = field(default_factory=StatusTime)
    start_timestamp: int = field(default=0)
    slug: str = field(default="")
    round_info: RoundInfo = field(default_factory=RoundInfo)

    @property
    def current_period_start(self) -> datetime:
        try:
            return datetime.fromtimestamp(self.time.current_period_start)
        except (ValueError, OSError, TypeError):
            return datetime.now()

    @property
    def total_elapsed_minutes(self) -> int:
        if not self.start_timestamp:
            return 0
        return int((time.time() - self.start_timestamp) / 60)

    @property
    def current_elapsed_minutes(self) -> int:
        if not self.time.current_period_start:
            return 0
        return int((time.time() - self.time.current_period_start) / 60)


def parse_status_time(data: dict) -> StatusTime:
    if not data:
        return StatusTime()
    return StatusTime(
        initial=data.get("initial", 0),
        max=data.get("max", 2700),
        extra=data.get("extra", 9),
        timestamp=data.get("timestamp", 0),
    )


def parse_time_event(data: dict) -> TimeEvent:
    if not data:
        return TimeEvent()
    return TimeEvent(
        first_injury_time=data.get("injuryTime1", 0),
        second_injury_time=data.get("injuryTime2", 0),
        third_injury_time=data.get("injuryTime3", 0),
        quarter_injury_time=data.get("injuryTime4", 0),
        current_period_start=data.get("currentPeriodStartTimestamp", 0),
    )


def parse_round_info(data: dict) -> RoundInfo:
    if not data:
        return RoundInfo(round=0, name="n/a", cup_round_type=0)
    return RoundInfo(
        round=data.get("round", 0),
        name=data.get("name", "n/a"),
        cup_round_type=data.get("cupRoundType", 0),
    )


def _parse_livescore_event(data: dict) -> Event:
    """
    Transforms LiveScore nested data matrix frames into a standardized Event model.
    Extracts data directly from Livescore's API structure.
    """
    # Extract team names from Livescore's T1/T2 structure
    home_name = data.get("T1", [{}])[0].get("Nm", "Unknown")
    away_name = data.get("T2", [{}])[0].get("Nm", "Unknown")
    
    # Extract scores
    try:
        home_curr = int(data.get("Tr1", 0))
        away_curr = int(data.get("Tr2", 0))
    except (ValueError, TypeError):
        home_curr, away_curr = 0, 0

    # Extract start timestamp
    start_ts = 0
    if "Esd" in data:
        try:
            dt = datetime.strptime(str(data["Esd"]), "%Y%m%d%H%M%S")
            start_ts = int(dt.timestamp())
        except (ValueError, KeyError, TypeError):
            pass

    # =========================================================================
    # EXTRACT TOURNAMENT AND COUNTRY DATA FROM LIVESCORE STAGE
    # =========================================================================
    tournament_name = "Unknown Tournament"
    tournament_id = None
    country_name = None
    country_id = None
    country_code = None
    
    if "Stg" in data:
        stage = data["Stg"]
        
        # CRITICAL FIX: Get tournament name from Snm (Stage Name)
        # Snm is the actual tournament/league name in Livescore
        tournament_name = stage.get("Snm")  # Stage Name - THIS IS THE TOURNAMENT NAME!
        
        # If Snm is None, try other fields
        if not tournament_name:
            tournament_name = stage.get("CompN")  # Competition Name (World Cup, etc.)
        if not tournament_name:
            tournament_name = stage.get("Nm")  # Fallback
        if not tournament_name:
            tournament_name = "Unknown Tournament"
        
        tournament_id = stage.get("Sid") or stage.get("CompId") or stage.get("Tid")
        
        # Extract country information directly from Livescore fields
        country_name = stage.get("Cnm")  # Livescore's country name field
        if not country_name:
            country_name = stage.get("Rgn")  # Region as fallback
        if not country_name:
            country_name = "World"
        
        country_id = stage.get("Cid") or stage.get("CategoryId")
        country_code = stage.get("Ccd")
    
    # If no country data from stage, try event-level fields
    if not country_name or country_name == "World":
        country_name = data.get("Cnm") or "World"
        country_id = data.get("Cid")
        country_code = data.get("Ccd")
    
    # Build category/country structure using actual data
    category_data = {
        "id": country_id,
        "name": country_name or "World",
        "slug": country_name.lower() if country_name else "world",
        "ccd": country_code or ""
    }
    
    # Build tournament structure with actual data
    tournament_data = {
        "id": tournament_id,
        "name": tournament_name,
        "slug": tournament_name.lower().replace(" ", "-") if tournament_name and tournament_name != "Unknown Tournament" else "unknown",
        "category": category_data
    }

    # =========================================================================
    # Normalize LiveScore status/description
    # =========================================================================
    raw_eps = str(data.get("Eps", "NS")).upper()
    normalized_status_desc = raw_eps

    if "'" in raw_eps:
        clean_min = raw_eps.replace("'", "").strip()
        if "+" in clean_min:
            clean_min = clean_min.split("+")[0].strip()
        
        if clean_min.isdigit():
            normalized_status_desc = clean_min

    elif raw_eps in ["HT", "HALF-TIME", "HALFTIME"]:
        normalized_status_desc = "HT"
    elif raw_eps in ["FT", "FULL-TIME", "FULLTIME"]:
        normalized_status_desc = "FT"

    return Event(
        id=data.get("Eid", 0),
        start_timestamp=start_ts,
        slug=f"{home_name.lower()}-{away_name.lower()}",
        tournament=parse_tournament(tournament_data),
        time=TimeEvent(current_period_start=start_ts),
        status_time=StatusTime(),
        home_team=parse_team({"name": home_name}),
        away_team=parse_team({"name": away_name}),
        home_score=parse_team_score({"current": home_curr}),
        away_score=parse_team_score({"current": away_curr}),
        status=parse_status({"description": normalized_status_desc}),
        round_info=RoundInfo(round=0, name="n/a", cup_round_type=0),
    )


def parse_event(data: dict) -> Event:
    if not data:
        return Event()

    # Check if it's a Livescore event (has Eid field)
    if "Eid" in data:
        return _parse_livescore_event(data)

    # Sofascore event format
    return Event(
        id=data.get("id", 0),
        start_timestamp=data.get("startTimestamp", 0),
        slug=data.get("slug", ""),
        tournament=parse_tournament(data.get("tournament", {})),
        time=parse_time_event(data.get("time", {})),
        status_time=parse_status_time(data.get("statusTime", {})),
        home_team=parse_team(data.get("homeTeam", {})),
        away_team=parse_team(data.get("awayTeam", {})),
        home_score=parse_team_score(data.get("homeScore", {})),
        away_score=parse_team_score(data.get("awayScore", {})),
        status=parse_status(data.get("status", {})),
        round_info=parse_round_info(data.get("roundInfo", {})),
    )


def parse_events(events: list[dict]) -> list[Event]:
    if not events:
        return []
    
    parsed_events = []
    for event in events:
        try:
            parsed_events.append(parse_event(event))
        except Exception as e:
            logger.error(f"Failed to parse event: {e}")
            continue
    
    return parsed_events