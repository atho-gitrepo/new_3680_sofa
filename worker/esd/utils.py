"""
Utility functions for Sofascore bot (safe version - Playwright only)
"""

import re
import time
import json
import logging
from datetime import datetime
from playwright.sync_api import Page

logger = logging.getLogger(__name__)

# --------------------------------------------------
# DATE HELPERS
# --------------------------------------------------

def get_today() -> str:
    """Return current date as YYYY-MM-DD"""
    return time.strftime("%Y-%m-%d")


def current_year(shift: int = 0) -> int:
    """Return current year with optional shift"""
    return datetime.now().year + shift


def get_yesterday() -> str:
    """Return yesterday's date as YYYY-MM-DD"""
    from datetime import timedelta
    return (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")


def get_tomorrow() -> str:
    """Return tomorrow's date as YYYY-MM-DD"""
    from datetime import timedelta
    return (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")


def format_date_for_livescore(date_str: str) -> str:
    """Convert YYYY-MM-DD to YYYYMMDD for Livescore API"""
    return date_str.replace("-", "")


# --------------------------------------------------
# STRING UTILS
# --------------------------------------------------

def camel_to_snake(name: str) -> str:
    """Convert camelCase to snake_case"""
    return re.sub(
        r"([a-z0-9])([A-Z])",
        r"\1_\2",
        re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    ).lower()


def clean_text(text: str) -> str:
    """Clean text by removing extra whitespace"""
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text).strip()


def normalize_team_name(name: str) -> str:
    """Normalize a team name for comparison"""
    if not name:
        return ""
    
    name = name.lower()
    suffixes = [' fc', ' f.c.', ' united', ' city', ' athletic', ' club', ' c.f.', ' cf']
    for suffix in suffixes:
        if name.endswith(suffix):
            name = name[:-len(suffix)]
    
    return clean_text(name)


# --------------------------------------------------
# SAFE JSON FETCH (PLAYWRIGHT ONLY)
# --------------------------------------------------

def get_json(page: Page, url: str, timeout: int = 30000) -> dict:
    """
    Fetch JSON safely using Playwright (ANTI-BLOCK VERSION)

    Args:
        page (Page): Playwright page instance (REQUIRED)
        url (str): API URL
        timeout (int): request timeout

    Returns:
        dict: parsed JSON response

    Raises:
        RuntimeError: if blocked or invalid response
    """

    if page is None:
        raise RuntimeError("❌ Playwright page is required (direct API disabled)")

    try:
        # Navigate safely
        page.goto(url, timeout=timeout, wait_until="domcontentloaded")

        content = page.content()

        # 🚨 Detect blocking
        if any(x in content.lower() for x in ["access denied", "forbidden", "cloudflare"]):
            raise RuntimeError("🚫 Blocked by Sofascore")

        # Extract JSON text
        text = page.evaluate("() => document.body.innerText")

        if not text:
            raise RuntimeError("❌ Empty response body")

        # Parse JSON
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            raise RuntimeError("❌ Invalid JSON response")

        # Optional API error handling
        if isinstance(data, dict) and "error" in data:
            logger.warning(f"Sofascore API error: {data['error']}")
            return {}

        return data

    except Exception as e:
        logger.error(f"get_json error: {e}")
        raise


def safe_get_json(page: Page, url: str, retries: int = 3, timeout: int = 30000) -> dict | None:
    """
    Fetch JSON with retries and error handling
    
    Args:
        page (Page): Playwright page instance
        url (str): API URL
        retries (int): Number of retry attempts
        timeout (int): Request timeout in milliseconds
        
    Returns:
        dict | None: Parsed JSON or None if all retries fail
    """
    for attempt in range(retries):
        try:
            return get_json(page, url, timeout)
        except Exception as e:
            logger.warning(f"Attempt {attempt + 1}/{retries} failed: {e}")
            if attempt < retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                logger.error(f"All {retries} attempts failed for URL: {url}")
                return None
    return None


# --------------------------------------------------
# VALIDATION
# --------------------------------------------------

def is_available_date(date: str, pattern: str = r"^\d{2}-\d{2}-\d{4}$") -> bool:
    """
    Validate date format (DD-MM-YYYY by default)
    
    Args:
        date (str): Date string to validate
        pattern (str): Regex pattern to match (default: DD-MM-YYYY)
        
    Returns:
        bool: True if valid, False otherwise
        
    Raises:
        ValueError: If date format is invalid
    """
    date_pattern = re.compile(pattern)

    if date_pattern.match(date):
        try:
            datetime.strptime(date, "%d-%m-%Y")
            return True
        except ValueError:
            raise ValueError(f"Invalid date: {date}. Must be a valid date.")
    else:
        raise ValueError(f"Invalid date format: {date}. Expected format: DD-MM-YYYY")


def is_valid_event_id(event_id) -> bool:
    """Check if an event ID is valid"""
    if not event_id:
        return False
    try:
        int(event_id)
        return True
    except (ValueError, TypeError):
        return False


# --------------------------------------------------
# DICTIONARY UTILS
# --------------------------------------------------

def safe_get(data: dict, key: str, default=None):
    """Safely get a value from a dictionary"""
    if not data or not isinstance(data, dict):
        return default
    return data.get(key, default)


def safe_get_nested(data: dict, keys: list, default=None):
    """Safely get a nested value from a dictionary"""
    if not data or not isinstance(data, dict):
        return default
    
    current = data
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    
    return current


def merge_dicts(dict1: dict, dict2: dict) -> dict:
    """Merge two dictionaries, with dict2 taking precedence"""
    if not dict1:
        return dict2.copy() if dict2 else {}
    if not dict2:
        return dict1.copy() if dict1 else {}
    
    result = dict1.copy()
    result.update(dict2)
    return result


# --------------------------------------------------
# LIST UTILS
# --------------------------------------------------

def chunk_list(lst: list, chunk_size: int) -> list:
    """Split a list into chunks of specified size"""
    if not lst or chunk_size <= 0:
        return []
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


# --------------------------------------------------
# MISC UTILS
# --------------------------------------------------

def retry_on_failure(func, max_retries: int = 3, delay: int = 1, *args, **kwargs):
    """Retry a function on failure with exponential backoff"""
    import time
    
    last_exception = None
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            if attempt < max_retries - 1:
                time.sleep(delay * (attempt + 1))
    
    if last_exception:
        raise last_exception
    return None