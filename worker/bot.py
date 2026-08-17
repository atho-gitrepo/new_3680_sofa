"""
Core business strategy processing engine.
Evaluates live match metrics against staking parameters and logs execution telemetry.
Hybrid version engineered to parse both object-oriented feeds and dictionary-based LiveScore payloads.
INTEGRATED WITH: Dynamic Percentage Staking Engine (10, 15, 25, 40, 60, 90)
"""

import requests
import os
import json
import time
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any
import firebase_admin
from firebase_admin import credentials, firestore
from esd.sofascore import SofascoreClient

# Import shared metrics registry to prevent circular imports
from metrics import STATE_LOCKS, BET_TRIGGERS, API_FAILURES

# Import the Staking Engine
from staking_engine import StakingEngine, STAKE_SEQUENCE

logger = logging.getLogger("BetBot.ExecutionEngine")

# --- PARAMETERS & ENV EXTRACTION ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_TOKEN_HERE")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID_HERE")
FIREBASE_CREDENTIALS = os.getenv("FIREBASE_CREDENTIALS_JSON", "")

# ============================================================
# STAKING ENGINE CONFIGURATION
# ============================================================
# These are now managed by the staking engine
ORIGINAL_STAKE = 10.0
MAX_CHASE_LEVEL = 3

# Timing parameters
MINUTES_REGULAR_BET = [35, 36, 37]
SLEEP_TIME = 55  # Default fallback sleep time between monitoring cycles

AMATEUR_KEYWORDS = ['amateur', 'youth', 'reserves', 'u18', 'u17', 'u16', 'u19', 'u22', 'u23', 'u21', 'u20', 'college']

PREDICT_START_MIN = 30
PRE_WARM_WINDOW = (34, 38)
MEMORY_PRUNE_TIMEOUT = 5400

# --- VOLATILE MEMORY CACHE MAP ---
LOCAL_TRACKED_MATCHES = {}

# --- GLOBAL STAKING ENGINE INSTANCE ---
_staking_engine: Optional[StakingEngine] = None
_staking_enabled: bool = True  # Set to False to disable staking engine and use fixed stake

# --- FIXED GEOGRAPHICAL FLAG MAP ---
COUNTRY_FLAGS = {
    "iceland": "🇮🇸", "argentina": "🇦🇷", "england": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "germany": "🇩🇪",
    "spain": "🇪🇸", "italy": "🇮🇹", "france": "🇫🇷", "brazil": "🇧🇷",
    "malaysia": "🇲🇾", "belarus": "🇧🇾", "faroe islands": "🇫🇴",
    "netherlands": "🇳🇱", "portugal": "🇵🇹", "belgium": "🇧🇪", "turkey": "🇹🇷",
    "russia": "🇷🇺", "ukraine": "🇺🇦", "scotland": "🏴󠁧󠁢󠁳󠁣󠁴󠁿", "switzerland": "🇨🇭",
    "austria": "🇦🇹", "denmark": "🇩🇰", "sweden": "🇸🇪", "norway": "🇳🇴",
    "greece": "🇬🇷", "croatia": "🇭🇷", "poland": "🇵🇱", "united states": "🇺🇸",
    "mexico": "🇲🇽", "australia": "🇦🇺", "japan": "🇯🇵", "south korea": "🇰🇷",
    "saudi arabia": "🇸🇦", "qatar": "🇶🇦", "uae": "🇦🇪", "china": "🇨🇳",
    "egypt": "🇪🇬", "nigeria": "🇳🇬", "south africa": "🇿🇦", "chile": "🇨🇱",
    "colombia": "🇨🇴", "peru": "🇵🇪", "uruguay": "🇺🇾", "paraguay": "🇵🇾",
    "ecuador": "🇪🇨", "venezuela": "🇻🇪", "bolivia": "🇧🇴", "costarica": "🇨🇷",
    "finland": "🇫🇮", "world": "🌍", "turkiye": "🇹🇷"
}

# =========================
# STAKING ENGINE MANAGEMENT
# =========================

def set_staking_engine(engine: StakingEngine) -> None:
    """
    Set the staking engine instance for use in the bot.
    Called by main.py during initialization.
    """
    global _staking_engine
    _staking_engine = engine
    logger.info(f"✅ Staking Engine attached to bot.")
    logger.info(f"📊 Sequence: {STAKE_SEQUENCE}")

def get_staking_engine() -> Optional[StakingEngine]:
    """Get the current staking engine instance."""
    return _staking_engine

def enable_staking(enable: bool = True) -> None:
    """Enable or disable the staking engine."""
    global _staking_enabled
    _staking_enabled = enable
    status = "enabled" if enable else "disabled"
    logger.info(f"📊 Staking engine {status}.")
    send_telegram(f"📊 Staking engine {status}.")

def get_staking_stats() -> Dict:
    """Get current staking statistics from the engine."""
    if _staking_engine:
        return _staking_engine.get_stats()
    return {
        "total_bets": 0,
        "total_wins": 0,
        "total_losses": 0,
        "win_rate": "0%",
        "total_staked": "$0.00",
        "total_profit": "$0.00",
        "roi": "0%",
        "current_bankroll": "$0.00",
        "peak_bankroll": "$0.00",
        "max_drawdown": "$0.00",
        "current_step": 0,
        "current_stake": f"${ORIGINAL_STAKE}",
        "is_paused": False,
        "consecutive_losses": 0,
        "current_streak": 0,
        "max_win_streak": 0,
        "max_loss_streak": 0,
    }

def reset_staking_engine() -> None:
    """Reset the staking engine to initial state."""
    global _staking_engine
    if _staking_engine:
        _staking_engine.reset()
        logger.info("🔄 Staking engine reset.")
        send_telegram("🔄 Staking engine reset to initial state.")

def get_staking_status_message() -> str:
    """Generate a formatted status message for the staking engine."""
    if _staking_engine:
        return _staking_engine.get_status_message()
    return "⚠️ Staking engine not initialized."

def get_current_stake() -> float:
    """
    Get the current stake from the staking engine.
    If staking is disabled or engine not available, returns ORIGINAL_STAKE.
    Returns 0 if paused.
    """
    if not _staking_enabled or not _staking_engine:
        return ORIGINAL_STAKE
    
    stake = _staking_engine.get_current_stake()
    # If paused (stake = 0), fall back to ORIGINAL_STAKE
    if stake == 0:
        logger.info("⏸️ Staking engine paused. Using original stake.")
        return ORIGINAL_STAKE
    
    return float(stake)

def get_current_step() -> int:
    """Get the current step from the staking engine."""
    if _staking_engine:
        return _staking_engine.current_step
    return 0

def record_bet_result(is_win: bool, match_info: Optional[Dict] = None) -> Optional[Dict]:
    """
    Record a bet result in the staking engine.
    Returns the result dictionary from the engine.
    """
    if _staking_engine:
        return _staking_engine.record_result(is_win, match_info)
    return None

# =========================
# FIREBASE CONFIGURATION
# =========================

class FirebaseManager:
    def __init__(self, creds_json):
        self.creds_json = creds_json
        self.db = None
        self._connect()

    def _connect(self):
        if not self.creds_json:
            logger.error("❌ Firebase Credentials missing from environment variables!")
            return False
        try:
            cred_dict = json.loads(self.creds_json)
            cred = credentials.Certificate(cred_dict)
            if not firebase_admin._apps:
                firebase_admin.initialize_app(cred)
            self.db = firestore.client()
            logger.info("✅ Firebase Connection Successfully Established.")
            return True
        except Exception as e:
            logger.exception(f"❌ Firebase Initialization Error: {e}")
            self.db = None
            return False

    def _ensure_connection(self) -> bool:
        if self.db is not None:
            return True
        return self._connect()

    def is_state_locked(self) -> bool:
        if not self._ensure_connection():
            return True
        try:
            unresolved_docs = self.db.collection('unresolved_bets').limit(1).get()
            return len(unresolved_docs) > 0
        except Exception as e:
            logger.error(f"❌ Error checking Firebase state lock: {e}")
            return True

    def get_last_resolved_bet(self) -> dict | None:
        if not self._ensure_connection():
            return None
        try:
            query = self.db.collection('resolved_bets')\
                .order_by('resolution_timestamp', direction=firestore.Query.DESCENDING)\
                .limit(1).get()
            for doc in query:
                return doc.to_dict()
            return None
        except Exception as e:
            logger.exception(f"❌ Error pulling last resolved bet: {e}")
            return None

    def add_unresolved_bet(self, match_id: str, data: dict):
        placed_time = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        data['placed_at'] = placed_time
        if not self._ensure_connection():
            logger.critical(f"❌ Transmit Blocked: Database offline. Drop ID {match_id}!")
            return
        try:
            self.db.collection('unresolved_bets').document(str(match_id)).set(data)
            logger.info(f"✅ Document successfully written to 'unresolved_bets' for ID {match_id}")
        except Exception as e:
            logger.exception(f"❌ Critical: Failed to save unresolved bet for ID {match_id}: {e}")

    def get_unresolved_bet(self, match_id: str) -> dict | None:
        if not self._ensure_connection():
            return None
        try:
            doc = self.db.collection('unresolved_bets').document(str(match_id)).get()
            return doc.to_dict() if doc.exists else None
        except Exception as e:
            logger.error(f"❌ Error downloading unresolved document {match_id}: {e}")
            return None

    def move_to_resolved(self, match_id: str, data: dict, outcome: str) -> bool:
        resolved_time = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        data.update({
            'outcome': outcome,
            'resolved_at': resolved_time,
            'resolution_timestamp': firestore.SERVER_TIMESTAMP
        })
        if not self._ensure_connection():
            return False
        try:
            self.db.collection('resolved_bets').document(str(match_id)).set(data)
            self.db.collection('unresolved_bets').document(str(match_id)).delete()
            return True
        except Exception as e:
            logger.exception(f"❌ Error during database migration lifecycle for Match ID {match_id}: {e}")
            return False

# =========================
# SYSTEM UTILITY AGENTS
# =========================

def send_telegram(msg: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'text': msg, 'parse_mode': 'Markdown'}, timeout=15)
    except Exception as e:
        logger.error(f"❌ Network error sending Telegram webhook event: {e}")

# ============================================================
# FIXED: calculate_stake() - Now correctly uses Staking Engine
# ============================================================

def calculate_stake() -> tuple[float, int]:
    """
    Calculate the stake using the Dynamic Percentage staking engine.
    Returns (stake, sequence_number) for compatibility with existing code.
    """
    global _staking_engine, _staking_enabled

    # If staking engine is enabled, use it
    if _staking_enabled and _staking_engine:
        stake = _staking_engine.get_current_stake()
        
        # If paused (stake = 0), fall back to ORIGINAL_STAKE
        if stake == 0:
            logger.info("⏸️ Staking engine paused. Using original stake.")
            return ORIGINAL_STAKE, 1
        
        # Get the current step for sequence tracking (step + 1 for display)
        step = _staking_engine.current_step + 1
        return float(stake), step

    # Fallback: Use original stake (backward compatibility)
    last = firebase_manager.get_last_resolved_bet()
    if not last or last.get('outcome') == 'win':
        return ORIGINAL_STAKE, 1

    seq = last.get('match_sequence', 1)
    if seq < MAX_CHASE_LEVEL:
        return float(ORIGINAL_STAKE * (2**seq)), seq + 1

    logger.error(f"🚨 MAX CHASE TIER HIT ({MAX_CHASE_LEVEL}). Hard reset back to sequence base configurations.")
    return ORIGINAL_STAKE, 1

def prune_volatile_cache_leaks():
    current_time = time.time()
    stale_keys = [
        fid for fid, state in LOCAL_TRACKED_MATCHES.items()
        if current_time - state.get('last_seen', 0.0) > MEMORY_PRUNE_TIMEOUT
    ]
    for key in stale_keys:
        LOCAL_TRACKED_MATCHES.pop(key, None)
    if stale_keys:
        logger.info(f"🧹 Automated Memory Clean: Evicted {len(stale_keys)} stale match contexts from memory maps.")

# ==========================================
# HYBRID PARSING WRAPPER FOR GEOGRAPHY
# ==========================================

def extract_hybrid_geography(match) -> tuple[str, str, str]:
    """
    Resolves league and country data structures across both
    Sofascore object types and LiveScore payload mappings.
    Returns: (league_name, country_name, country_slug)
    """
    # 1. Handle object-oriented payload formats (Sofascore)
    if hasattr(match, 'tournament'):
        league = match.tournament.name
        country_name = match.tournament.category.name if match.tournament.category else "World"
        country_slug = getattr(match.tournament.category, 'slug', country_name.lower())
        return league, country_name, country_slug

    # 2. Handle structural dictionary payload formats (LiveScore)
    if isinstance(match, dict):
        tournament_name = "Unknown League"

        # Try Stg (Stage) data first
        if "Stg" in match and isinstance(match["Stg"], dict):
            stage = match["Stg"]
            tournament_name = (
                stage.get("Snm") or
                stage.get("CompN") or
                stage.get("Nm") or
                "Unknown League"
            )

            if tournament_name == "Unknown League":
                tournament_name = match.get("Snm") or match.get("CompN") or "Unknown League"

        if tournament_name == "Unknown League":
            tournament_name = (
                match.get("Snm") or
                match.get("CompN") or
                match.get("league") or
                match.get("tournament") or
                "Unknown League"
            )

        country_name = "World"
        country_slug = "world"

        if "Stg" in match and isinstance(match["Stg"], dict):
            stage = match["Stg"]
            country_name = (
                stage.get("Cnm") or
                stage.get("Rgn") or
                stage.get("Country") or
                "World"
            )
            country_slug = country_name.lower()

        if country_name == "World":
            country_name = (
                match.get("Cnm") or
                match.get("country") or
                "World"
            )
            country_slug = country_name.lower()

        return tournament_name, country_name, country_slug

    return "Unknown League", "World", "world"

# =========================
# CORE EVALUATION PIPELINE
# =========================

def process_match(match):
    # Safe fallback lookup for Unique IDs and Match Titles
    fid = str(match.id) if hasattr(match, 'id') else str(match.get('match_id') or match.get('id') or match.get('Eid', ''))

    if hasattr(match, 'home_team'):
        match_name = f"{match.home_team.name} vs {match.away_team.name}"
    else:
        match_name = match.get('match_name') or f"{match.get('home_name', 'Home')} vs {match.get('away_name', 'Away')}"

    league, country, country_slug = extract_hybrid_geography(match)
    full_info = f"{league} {country}"

    if any(keyword.lower() in full_info.lower() for keyword in AMATEUR_KEYWORDS):
        logger.debug(f"⏭️ Skipping amateur match: {match_name} ({full_info})")
        return

    if hasattr(match, 'status'):
        status = match.status.description.upper()
        score = f"{match.home_score.current}-{match.away_score.current}"
    else:
        status = str(match.get('status_string') or match.get('status') or match.get('Eps', '')).upper()
        score = f"{match.get('home_score', 0)}-{match.get('away_score', 0)}"

    live_pitch_minute = None
    is_first_half_phase = False

    if status.isdigit():
        live_pitch_minute = int(status)
        if live_pitch_minute <= 45:
            is_first_half_phase = True
    elif status in ['HT', 'HALFTIME', 'HALF']:
        live_pitch_minute = 45
        is_first_half_phase = True
    elif '1ST' in status:
        is_first_half_phase = True
        live_pitch_minute = getattr(match, 'total_elapsed_minutes', match.get('total_elapsed_minutes', 35))

    if live_pitch_minute is None or live_pitch_minute < PREDICT_START_MIN:
        return

    logger.info(f"🔍 Match verification: {match_name} | Real Min: {live_pitch_minute}' | Score: {score} | League: {league} | Country: {country}")

    state = LOCAL_TRACKED_MATCHES.get(fid, {
        'bet_placed': False,
        'last_seen': time.time(),
        'active': False
    })
    state['last_seen'] = time.time()

    if PRE_WARM_WINDOW[0] <= live_pitch_minute <= PRE_WARM_WINDOW[1]:
        state['active'] = True

    LOCAL_TRACKED_MATCHES[fid] = state

    # --- PHASE 1: EVALUATE PLACEMENT ---
    if is_first_half_phase and (live_pitch_minute in MINUTES_REGULAR_BET) and not state['bet_placed']:
        if firebase_manager.is_state_locked():
            STATE_LOCKS.inc()
            logger.warning(f"🚫 Qualification blocked for '{match_name}'. Active DB lock present.")
        else:
            if score in ['1-1', '2-2', '2-0', '0-2']:
                logger.warning(f"⚡ QUALIFIED: Firing placement routine for {match_name} at score {score}")
                
                # Get stake and step from staking engine
                stake, seq = calculate_stake()
                
                # Get current step for display
                current_step = _staking_engine.current_step if _staking_engine else 0
                
                flag_emoji = COUNTRY_FLAGS.get(country_slug.lower(), COUNTRY_FLAGS.get(country.lower(), "🌍"))

                step_display = ""
                if _staking_engine:
                    step_display = f" | Step {current_step + 1}/{len(STAKE_SEQUENCE)}"

                data = {
                    'match_name': match_name,
                    'league': league,
                    'country': country,
                    'country_slug': country_slug,
                    '36_score': score,
                    'stake': stake,
                    'match_sequence': seq,
                    'bet_type': 'regular',
                    'staking_step': current_step + 1 if _staking_engine else 0,
                    'staking_sequence': STAKE_SEQUENCE if _staking_engine else [],
                }
                firebase_manager.add_unresolved_bet(fid, data)
                BET_TRIGGERS.inc()

                # Enhanced clean Telegram string notification alert layout
                send_telegram(
                    f"🎯 **BET PLACED (Match {seq})**\n"
                    f"⏱ Min: {live_pitch_minute}' | {match_name}\n"
                    f"{flag_emoji} {country} | 🏆 {league}\n"
                    f"🔢 Score: {score}\n"
                    f"💰 Stake: ${stake:.2f}{step_display}"
                )

        state['bet_placed'] = True
        LOCAL_TRACKED_MATCHES[fid] = state

    # --- PHASE 2: HALFTIME RESOLUTION ---
    elif status in ['HT', 'HALFTIME', 'HALF']:
        unresolved = firebase_manager.get_unresolved_bet(fid)
        if unresolved:
            trigger_score = unresolved.get('36_score')
            outcome = 'win' if score == trigger_score else 'loss'

            db_league = unresolved.get('league', league)
            db_country = unresolved.get('country', country)
            db_slug = unresolved.get('country_slug', country_slug)
            flag_emoji = COUNTRY_FLAGS.get(db_slug.lower(), COUNTRY_FLAGS.get(db_country.lower(), "🌍"))

            stake = unresolved.get('stake', 0)

            # --- Record result in staking engine ---
            if _staking_engine:
                is_win = (outcome == 'win')
                match_info = {
                    'match_name': match_name,
                    'league': db_league,
                    'country': db_country,
                    'score': score,
                    'trigger_score': trigger_score,
                    'stake': stake,
                }
                result = _staking_engine.record_result(is_win, match_info)
                
                # Get updated staking engine status for the message
                step_display = f"Step {_staking_engine.current_step + 1}/{len(STAKE_SEQUENCE)}"
                
                # Get the NEXT stake for display
                next_stake = _staking_engine.get_current_stake()
                if next_stake == 0:
                    next_stake_display = "⏸️ PAUSED"
                else:
                    next_stake_display = f"Next: ${next_stake:.2f}"
                
                bankroll_display = f" | 💰 Bankroll: ${_staking_engine.current_bankroll:.2f}"
                profit_display = f" | 📈 Profit: ${_staking_engine.total_profit:.2f}"
            else:
                step_display = f"Step {seq}/{len(STAKE_SEQUENCE)}" if seq else ""
                next_stake_display = ""
                bankroll_display = ""
                profit_display = ""

            firebase_manager.move_to_resolved(fid, unresolved, outcome)

            # Build the result message with proper stake display
            result_msg = (
                f"{'✅ WIN' if outcome == 'win' else '❌ LOSS'} **HT Settlement**\n"
                f"⏱ 45' | {match_name}\n"
                f"{flag_emoji} {db_country} | 🏆 {db_league}\n"
                f"🔢 Score: {score} (Target: {trigger_score})\n"
                f"💰 Stake: ${stake:.2f}"
            )
            
            if step_display:
                result_msg += f" | {step_display}"
            
            if _staking_engine and _staking_engine.is_paused:
                pause_remaining = int(_staking_engine.pause_until - time.time())
                if pause_remaining > 0:
                    minutes = pause_remaining // 60
                    seconds = pause_remaining % 60
                    result_msg += f" | ⏸️ PAUSED for {minutes}m {seconds}s"
            
            if bankroll_display:
                result_msg += bankroll_display
            if profit_display:
                result_msg += profit_display

            send_telegram(result_msg)
            LOCAL_TRACKED_MATCHES.pop(fid, None)

# =========================
# DRIVER LAYER INTERFACES
# =========================

# Initialize global Firebase manager
firebase_manager = None
SOFASCORE_CLIENT = None

def initialize_bot_services() -> bool:
    global firebase_manager, SOFASCORE_CLIENT
    firebase_manager = FirebaseManager(FIREBASE_CREDENTIALS)
    try:
        SOFASCORE_CLIENT = SofascoreClient()
        SOFASCORE_CLIENT.initialize()

        # Log staking engine status
        if _staking_engine:
            logger.info(f"📊 Staking Engine active: {_staking_engine.get_current_step_display()}")
            logger.info(f"📊 Sequence: {STAKE_SEQUENCE}")
        else:
            logger.info("📊 Staking Engine not attached. Using fixed stake.")

        return True
    except Exception as e:
        logger.exception(f"❌ Failed to instantiate data engine driver context: {e}")
        API_FAILURES.inc()
        return False

def shutdown_bot():
    global SOFASCORE_CLIENT
    if SOFASCORE_CLIENT:
        try:
            SOFASCORE_CLIENT.close()
        except Exception as e:
            logger.error(f"Error shutting down client: {e}")

def run_bot_cycle():
    if not SOFASCORE_CLIENT:
        return
    try:
        events = SOFASCORE_CLIENT.get_events(live=True)
        if not events:
            logger.debug("No live events found in current cycle.")
            return
        for m in events:
            try:
                process_match(m)
            except Exception as inner_ex:
                logger.error(f"Error checking single event match node: {inner_ex}")
        prune_volatile_cache_leaks()
    except Exception as e:
        logger.error(f"Ingestion lifecycle exception: {e}")
