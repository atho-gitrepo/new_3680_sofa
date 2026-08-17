# esd/sofascore/match_stats.py

"""
This module contains functions to parse match statistics data.
Handles hybrid translation workflows for both SofaScore and LiveScore payloads.
"""

from dataclasses import dataclass, field
from typing import Optional
from .lineup import Lineups


@dataclass
class StatisticItem:
    """
    The statistic item class.
    """

    home_value: float = field(default=0.0)
    away_value: float = field(default=0.0)
    stat_type: str = field(default="")
    home_total: Optional[int] = field(default=None)
    away_total: Optional[int] = field(default=None)


def parse_statistic_item(item: dict[str, any]) -> StatisticItem:
    """
    Parse a statistic item.
    """
    return StatisticItem(
        stat_type=item.get("statisticsType", ""),
        home_value=item.get("homeValue", 0.0),
        away_value=item.get("awayValue", 0.0),
        home_total=item.get("homeTotal"),
        away_total=item.get("awayTotal"),
    )


@dataclass
class MatchOverviewStats:
    """
    The match overview statistics class.
    """

    ball_possession: StatisticItem = field(default_factory=StatisticItem)
    expected_goals: StatisticItem = field(default_factory=StatisticItem)
    big_chance_created: StatisticItem = field(default_factory=StatisticItem)
    total_shots_on_goal: StatisticItem = field(default_factory=StatisticItem)
    goalkeeper_saves: StatisticItem = field(default_factory=StatisticItem)
    corner_kicks: StatisticItem = field(default_factory=StatisticItem)
    fouls: StatisticItem = field(default_factory=StatisticItem)
    passes: StatisticItem = field(default_factory=StatisticItem)
    total_tackle: StatisticItem = field(default_factory=StatisticItem)
    free_kicks: StatisticItem = field(default_factory=StatisticItem)
    yellow_cards: StatisticItem = field(default_factory=StatisticItem)


def parse_match_overview_stats(items: list[dict[str, any]]) -> MatchOverviewStats:
    """
    Parse match overview statistics.
    """
    mapping = {item.get("key", ""): parse_statistic_item(item) for item in items if item}
    return MatchOverviewStats(
        ball_possession=mapping.get("ballPossession", StatisticItem()),
        expected_goals=mapping.get("expectedGoals", StatisticItem()),
        big_chance_created=mapping.get("bigChanceCreated", StatisticItem()),
        total_shots_on_goal=mapping.get("totalShotsOnGoal", StatisticItem()),
        goalkeeper_saves=mapping.get("goalkeeperSaves", StatisticItem()),
        corner_kicks=mapping.get("cornerKicks", StatisticItem()),
        fouls=mapping.get("fouls", StatisticItem()),
        passes=mapping.get("passes", StatisticItem()),
        total_tackle=mapping.get("totalTackle", StatisticItem()),
        free_kicks=mapping.get("freeKicks", StatisticItem()),
        yellow_cards=mapping.get("yellowCards", StatisticItem()),
    )


@dataclass
class ShotsStats:
    """
    The shots statistics class.
    """

    total_shots_on_goal: StatisticItem = field(default_factory=StatisticItem)
    shots_on_goal: StatisticItem = field(default_factory=StatisticItem)
    hit_woodwork: StatisticItem = field(default_factory=StatisticItem)
    shots_off_goal: StatisticItem = field(default_factory=StatisticItem)
    blocked_scoring_attempt: StatisticItem = field(default_factory=StatisticItem)
    total_shots_inside_box: StatisticItem = field(default_factory=StatisticItem)
    total_shots_outside_box: StatisticItem = field(default_factory=StatisticItem)


def parse_shots_stats(items: list[dict[str, any]]) -> ShotsStats:
    """
    Parse shots statistics.
    """
    mapping = {item.get("key", ""): parse_statistic_item(item) for item in items if item}
    return ShotsStats(
        total_shots_on_goal=mapping.get("totalShotsOnGoal", StatisticItem()),
        shots_on_goal=mapping.get("shotsOnGoal", StatisticItem()),
        hit_woodwork=mapping.get("hitWoodwork", StatisticItem()),
        shots_off_goal=mapping.get("shotsOffGoal", StatisticItem()),
        blocked_scoring_attempt=mapping.get("blockedScoringAttempt", StatisticItem()),
        total_shots_inside_box=mapping.get("totalShotsInsideBox", StatisticItem()),
        total_shots_outside_box=mapping.get("totalShotsOutsideBox", StatisticItem()),
    )


@dataclass
class AttackStats:
    """
    The attack statistics class.
    """

    big_chance_scored: StatisticItem = field(default_factory=StatisticItem)
    big_chance_missed: StatisticItem = field(default_factory=StatisticItem)
    touches_in_opp_box: StatisticItem = field(default_factory=StatisticItem)
    fouled_final_third: StatisticItem = field(default_factory=StatisticItem)
    offsides: StatisticItem = field(default_factory=StatisticItem)


def parse_attack_stats(items: list[dict[str, any]]) -> AttackStats:
    """
    Parse attack statistics.
    """
    mapping = {item.get("key", ""): parse_statistic_item(item) for item in items if item}
    return AttackStats(
        big_chance_scored=mapping.get("bigChanceScored", StatisticItem()),
        big_chance_missed=mapping.get("bigChanceMissed", StatisticItem()),
        touches_in_opp_box=mapping.get("touchesInOppBox", StatisticItem()),
        fouled_final_third=mapping.get("fouledFinalThird", StatisticItem()),
        offsides=mapping.get("offsides", StatisticItem()),
    )


@dataclass
class PassesStats:
    """
    The passes statistics class.
    """

    accurate_passes: StatisticItem = field(default_factory=StatisticItem)
    throw_ins: StatisticItem = field(default_factory=StatisticItem)
    final_third_entries: StatisticItem = field(default_factory=StatisticItem)
    final_third_phase_statistic: StatisticItem = field(default_factory=StatisticItem)
    accurate_long_balls: StatisticItem = field(default_factory=StatisticItem)
    accurate_cross: StatisticItem = field(default_factory=StatisticItem)


def parse_passes_stats(items: list[dict[str, any]]) -> PassesStats:
    """
    Parse passes statistics.
    """
    mapping = {item.get("key", ""): parse_statistic_item(item) for item in items if item}
    return PassesStats(
        accurate_passes=mapping.get("accuratePasses", StatisticItem()),
        throw_ins=mapping.get("throwIns", StatisticItem()),
        final_third_entries=mapping.get("finalThirdEntries", StatisticItem()),
        final_third_phase_statistic=mapping.get("finalThirdPhaseStatistic", StatisticItem()),
        accurate_long_balls=mapping.get("accurateLongBalls", StatisticItem()),
        accurate_cross=mapping.get("accurateCross", StatisticItem()),
    )


@dataclass
class DuelsStats:
    """
    The duels statistics class.
    """

    duel_won_percent: StatisticItem = field(default_factory=StatisticItem)
    dispossessed: StatisticItem = field(default_factory=StatisticItem)
    ground_duels_percentage: StatisticItem = field(default_factory=StatisticItem)
    aerial_duels_percentage: StatisticItem = field(default_factory=StatisticItem)
    dribbles_percentage: StatisticItem = field(default_factory=StatisticItem)


def parse_duels_stats(items: list[dict[str, any]]) -> DuelsStats:
    """
    Parse duels statistics.
    """
    mapping = {item.get("key", ""): parse_statistic_item(item) for item in items if item}
    return DuelsStats(
        duel_won_percent=mapping.get("duelWonPercent", StatisticItem()),
        dispossessed=mapping.get("dispossessed", StatisticItem()),
        ground_duels_percentage=mapping.get("groundDuelsPercentage", StatisticItem()),
        aerial_duels_percentage=mapping.get("aerialDuelsPercentage", StatisticItem()),
        dribbles_percentage=mapping.get("dribblesPercentage", StatisticItem()),
    )


@dataclass
class DefendingStats:
    """
    The defending statistics class.
    """

    won_tackle_percent: StatisticItem = field(default_factory=StatisticItem)
    total_tackle: StatisticItem = field(default_factory=StatisticItem)
    interception_won: StatisticItem = field(default_factory=StatisticItem)
    ball_recovery: StatisticItem = field(default_factory=StatisticItem)
    total_clearance: StatisticItem = field(default_factory=StatisticItem)


def parse_defending_stats(items: list[dict[str, any]]) -> DefendingStats:
    """
    Parse defending statistics.
    """
    mapping = {item.get("key", ""): parse_statistic_item(item) for item in items if item}
    return DefendingStats(
        won_tackle_percent=mapping.get("wonTacklePercent", StatisticItem()),
        total_tackle=mapping.get("totalTackle", StatisticItem()),
        interception_won=mapping.get("interceptionWon", StatisticItem()),
        ball_recovery=mapping.get("ballRecovery", StatisticItem()),
        total_clearance=mapping.get("totalClearance", StatisticItem()),
    )


@dataclass
class GoalkeepingStats:
    """
    The goalkeeping statistics class.
    """

    goalkeeper_saves: StatisticItem = field(default_factory=StatisticItem)
    goals_prevented: StatisticItem = field(default_factory=StatisticItem)
    goal_kicks: StatisticItem = field(default_factory=StatisticItem)


def parse_goalkeeping_stats(items: list[dict[str, any]]) -> GoalkeepingStats:
    """
    Parse goalkeeping statistics.
    """
    mapping = {item.get("key", ""): parse_statistic_item(item) for item in items if item}
    return GoalkeepingStats(
        goalkeeper_saves=mapping.get("goalkeeperSaves", StatisticItem()),
        goals_prevented=mapping.get("goalsPrevented", StatisticItem()),
        goal_kicks=mapping.get("goalKicks", StatisticItem()),
    )


@dataclass
class PeriodStats:
    """
    The period statistics class.
    """

    match_overview: MatchOverviewStats = field(default_factory=MatchOverviewStats)
    shots: ShotsStats = field(default_factory=ShotsStats)
    attack: AttackStats = field(default_factory=AttackStats)
    passes: PassesStats = field(default_factory=PassesStats)
    duels: DuelsStats = field(default_factory=DuelsStats)
    defending: DefendingStats = field(default_factory=DefendingStats)
    goalkeeping: GoalkeepingStats = field(default_factory=GoalkeepingStats)


def parse_period_stats(groups: list[dict[str, any]]) -> PeriodStats:
    """
    Parse period statistics.
    """
    group_mapping = {str(group.get("groupName", "")).lower(): group for group in groups if group}
    return PeriodStats(
        match_overview=parse_match_overview_stats(
            group_mapping.get("match overview", {}).get("statisticsItems", [])
        ),
        shots=parse_shots_stats(
            group_mapping.get("shots", {}).get("statisticsItems", [])
        ),
        attack=parse_attack_stats(
            group_mapping.get("attack", {}).get("statisticsItems", [])
        ),
        passes=parse_passes_stats(
            group_mapping.get("passes", {}).get("statisticsItems", [])
        ),
        duels=parse_duels_stats(
            group_mapping.get("duels", {}).get("statisticsItems", [])
        ),
        defending=parse_defending_stats(
            group_mapping.get("defending", {}).get("statisticsItems", [])
        ),
        goalkeeping=parse_goalkeeping_stats(
            group_mapping.get("goalkeeping", {}).get("statisticsItems", [])
        ),
    )


@dataclass
class WinProbability:
    """
    The win probability class.
    """

    home: float = field(default=0.0)
    draw: float = field(default=0.0)
    away: float = field(default=0.0)


@dataclass
class MatchStats:
    """
    The match statistics class.
    """

    all: Optional[PeriodStats] = field(default=None)
    first_half: Optional[PeriodStats] = field(default=None)
    second_half: Optional[PeriodStats] = field(default=None)
    lineups: Optional[Lineups] = field(default=None)
    win_probability: Optional[WinProbability] = field(default=None)


def parse_match_probabilities(data: dict[str, any]) -> WinProbability:
    """
    Parse match probabilities.
    """
    if not data:
        return WinProbability()
    return WinProbability(
        home=data.get("homeWin", 0.0),
        draw=data.get("draw", 0.0),
        away=data.get("awayWin", 0.0),
    )


def _parse_livescore_stats(data: dict[str, any]) -> MatchStats:
    """
    Internal parser dedicated to converting LiveScore's 'Stat' arrays 
    into unified PeriodStats schemas safely.
    """
    match_stats = MatchStats(win_probability=WinProbability())
    
    # LiveScore stores rows inside a nested 'Stat' list or directly as fields
    stat_rows = data.get("Stat", [])
    if not stat_rows and "Stat" in data.get("SPrd", [{}])[0]: # Periodic check
        stat_rows = data["SPrd"][0].get("Stat", [])

    # Map layout strings to match internal dataclass configurations
    # LiveScore Key Map -> SofaScore Metric equivalent
    ls_map = {
        "BallPossession": "ballPossession",
        "ShotsOn": "shotsOnGoal",
        "ShotsOff": "shotsOffGoal",
        "BlockedShots": "blockedScoringAttempt",
        "Corners": "cornerKicks",
        "Fouls": "fouls",
        "YellowCards": "yellowCards",
        "Saves": "goalkeeperSaves"
    }

    overview_items = []
    shots_items = []

    for row in stat_rows:
        ls_key = row.get("Type")
        if ls_key in ls_map:
            sofa_key = ls_map[ls_key]
            try:
                h_val = float(row.get("Value1", 0.0))
                a_val = float(row.get("Value2", 0.0))
            except (ValueError, TypeError):
                h_val, a_val = 0.0, 0.0

            stat_item = {
                "key": sofa_key,
                "statisticsType": sofa_key,
                "homeValue": h_val,
                "awayValue": a_val,
                "homeTotal": None,
                "awayTotal": None
            }

            if ls_key in ["BallPossession", "Corners", "Fouls", "YellowCards", "Saves"]:
                overview_items.append(stat_item)
            if ls_key in ["ShotsOn", "ShotsOff", "BlockedShots"]:
                shots_items.append(stat_item)
                # Synergize 'ShotsOn' to total metrics if applicable
                if ls_key == "ShotsOn":
                    stat_item_total = stat_item.copy()
                    stat_item_total["key"] = "totalShotsOnGoal"
                    stat_item_total["statisticsType"] = "totalShotsOnGoal"
                    overview_items.append(stat_item_total)
                    shots_items.append(stat_item_total)

    # Build and link the parsed context to 'all' match time representation
    period_stats = PeriodStats(
        match_overview=parse_match_overview_stats(overview_items),
        shots=parse_shots_stats(shots_items)
    )
    match_stats.all = period_stats
    return match_stats


def parse_match_stats(
    data: any, win_probabilities: dict[str, any]
) -> MatchStats:
    """
    Parse match statistics handling either SofaScore or LiveScore input signatures.

    Args:
        data: The statistics payload from the network.
        win_probabilities (Dict[str, Any]): The win probabilities payload.

    Returns:
        MatchStats: The parsed match object model.
    """
    # 1. Check if incoming structure belongs to LiveScore payload types
    if isinstance(data, dict) and ("Stat" in data or "SPrd" in data):
        return _parse_livescore_stats(data)

    # 2. Process default SofaScore logic arrays
    match_stats = MatchStats()
    match_stats.win_probability = parse_match_probabilities(win_probabilities)
    
    if not data or not isinstance(data, list):
        return match_stats
        
    for stat in data:
        if not stat:
            continue
        period = stat.get("period", "").upper()
        groups = stat.get("groups", [])
        period_stats = parse_period_stats(groups)
        if period == "ALL":
            match_stats.all = period_stats
        elif period == "1ST":
            match_stats.first_half = period_stats
        elif period == "2ND":
            match_stats.second_half = period_stats

    return match_stats
