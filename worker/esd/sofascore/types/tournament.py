"""
This module contains the dataclasses for the tournament data.
"""

from dataclasses import dataclass, field

# --- NEW CATEGORY DATACLASS (Holds Country Info) ---
@dataclass
class Category:
    """
    Category dataclass, which holds the country information.
    """
    id: int = field(default=None)
    name: str = field(default=None) # This is the field that contains the Country Name (e.g., 'England')
    slug: str = field(default=None)


def parse_category(data: dict) -> Category:
    """
    Parse category data.

    Args:
        data (dict): Category data.

    Returns:
        Category: Category dataclass
    """
    return Category(
        id=data.get("id", None),
        name=data.get("name", None),
        slug=data.get("slug", None),
    )
# ----------------------------------------------------


@dataclass
class Tournament:
    """
    Tournament dataclass.
    """

    id: int = field(default=None)
    name: str = field(default=None)
    slug: str = field(default=None)
    # primaryColorHex: str
    # secondaryColorHex: str
    category: Category = field(default_factory=Category)
    userCount: int = field(default=0) # 🟢 UNCOMMENTED/ADDED for filtering
    # displayInverseHomeAwayTeams: bool


def parse_tournament(data: dict) -> Tournament:
    """
    Parse tournament data.

    Args:
        data (dict): Tournament data.

    Returns:
        Tournament: Tournament dataclass
    """
    return Tournament(
        id=data.get("id", None),
        name=data.get("name", None),
        slug=data.get("slug", None),
        # primaryColorHex=data.get("primaryColorHex"),
        # secondaryColorHex=data.get("secondaryColorHex"),
        category=parse_category(data.get("category", {})),
        userCount=data.get("userCount", 0), # 🟢 UNCOMMENTED/ADDED with default value
        # displayInverseHomeAwayTeams=data.get("displayInverseHomeAwayTeams"),
    )


def parse_tournaments(data: dict) -> list[Tournament]:
    """
    Parse tournament data.

    Args:
        data (dict): Tournament data.

    Returns:
        list[Tournament]: List of Tournament dataclass
    """
    return [parse_tournament(tournament) for tournament in data]
