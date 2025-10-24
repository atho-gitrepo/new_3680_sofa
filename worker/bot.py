import requests
import os
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional # 🟢 NEW: Added typing imports
import firebase_admin
from firebase_admin import credentials, firestore
# Correct import structure for your local library
# 🟢 UPDATED: Import the new types and parser
from esd.sofascore import (
    SofascoreClient, 
    EntityType, 
    TeamTournamentStats, 
    parse_team_tournament_stats
) 

# --- GLOBAL VARIABLES ---
SOFASCORE_CLIENT = None 
firebase_manager = None 
# 🟢 ENHANCEMENT: New in-memory store for tracking live match state
LOCAL_TRACKED_MATCHES = {} 
# 🟢 NEW: Cache for expensive, semi-static API calls (Team Tournament Stats)
TEAM_STATS_CACHE: Dict[str, TeamTournamentStats] = {}

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("FootballBettingBot")

# Load environment variables
API_KEY = os.getenv("API_KEY") 
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
FIREBASE_CREDENTIALS_JSON_STRING = os.getenv("FIREBASE_CREDENTIALS_JSON")

# --- CONSTANTS ---
SLEEP_TIME = 60
FIXTURE_API_INTERVAL = 900
MINUTES_REGULAR_BET = [36, 37]
BET_TYPE_REGULAR = 'regular'
STATUS_LIVE = ['LIVE', '1H', '2H', 'ET', 'P']
STATUS_HALFTIME = 'HT'
STATUS_FINISHED = ['FT', 'AET', 'PEN'] 
MAX_FETCH_RETRIES = 3 
BET_RESOLUTION_WAIT_MINUTES = 180 

# --- 🟢 UPDATED FILTER CONSTANTS ---
# Max total goals averaged (Scored + Conceded) for the team over the season
MAX_GOAL_AVERAGE: float = 2.38
AMATEUR_KEYWORDS = [
    'amateur', 'youth', 'reserve', 'friendly', 'u23', 'u21', 'u19', 
    'liga de reservas', 'division b', 'm-league', 'liga pro','u17'
]
# -------------------------------

# =========================================================
# 📌 INITIALIZATION FUNCTIONS
# =========================================================

class FirebaseManager:
    """Manages all interactions with the Firebase Firestore database."""
    def __init__(self, credentials_json_string):
        self.db = None
        # Initialize an empty cache for quick local lookups within one cycle
        self._unresolved_bets_cache = {} 
        try:
            logger.info("Initializing Firebase...")
            if not credentials_json_string:
                logger.warning("FIREBASE_CREDENTIALS_JSON is empty. Skipping Firebase initialization.")
                return

            cred_dict = json.loads(credentials_json_string)
            cred = credentials.Certificate(cred_dict)
            if not firebase_admin._apps:
                firebase_admin.initialize_app(cred)
            self.db = firestore.client()
            logger.info("Firebase initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {e}")
            self.db = None
            raise
    
    # --- EFFICIENT LOOKUP METHODS (OPTIMIZED) ---
    def is_bet_unresolved(self, match_id: int or str) -> bool:
        """Checks for an unresolved bet using a direct document lookup."""
        if not self.db: return False
        match_id_str = str(match_id)
        
        # 1. Check local cache first (for speed within the same bot cycle)
        if match_id_str in self._unresolved_bets_cache:
            return True
            
        # 2. Perform a direct Firestore lookup (minimal read operation)
        try:
            doc_ref = self.db.collection('unresolved_bets').document(match_id_str)
            doc = doc_ref.get() # Single document read (1 read operation)
            if doc.exists:
                # Update cache if found in Firestore
                self._unresolved_bets_cache[match_id_str] = doc.to_dict()
                return True
            return False
        except Exception as e:
            logger.error(f"Firestore Error during is_bet_unresolved: {e}")
            return False

    def get_unresolved_bet_data(self, match_id: int or str) -> dict or None:
        """Retrieves an unresolved bet's data."""
        if not self.db: return None
        match_id_str = str(match_id)

        # 1. Check local cache first
        if match_id_str in self._unresolved_bets_cache:
            return self._unresolved_bets_cache.get(match_id_str)

        # 2. Perform a direct Firestore lookup (minimal read operation)
        try:
            doc_ref = self.db.collection('unresolved_bets').document(match_id_str)
            doc = doc_ref.get()
            if doc.exists:
                data = doc.to_dict()
                # Update cache and return
                self._unresolved_bets_cache[match_id_str] = data
                return data
            return None
        except Exception as e:
            logger.error(f"Firestore Error during get_unresolved_bet_data: {e}")
            return None
    # --- END EFFICIENT LOOKUP METHODS ---
            
    def get_stale_unresolved_bets(self, minutes_to_wait=BET_RESOLUTION_WAIT_MINUTES):
        if not self.db: return {}
        try:
            # Performs a full scan, but runs only once every FIXTURE_API_INTERVAL (~15 min)
            bets = self.db.collection('unresolved_bets').stream()
            stale_bets = {}
            time_threshold = datetime.utcnow() - timedelta(minutes=minutes_to_wait)
            
            for doc in bets:
                bet_info = doc.to_dict()
                
                # Check for bet types that need final resolution (currently only 32_over is blocked)
                # Since the regular bet resolves at HT, we only need to check bets that persist past HT.
                if bet_info.get('bet_type') not in [BET_TYPE_REGULAR]:
                    placed_at_str = bet_info.get('placed_at')
                    if placed_at_str:
                        try:
                            placed_at_dt = datetime.strptime(placed_at_str, '%Y-%m-%d %H:%M:%S')
                            if placed_at_dt < time_threshold:
                                stale_bets[doc.id] = bet_info
                        except ValueError:
                            logger.warning(f"Could not parse placed_at timestamp for bet {doc.id}")
                            continue
            return stale_bets
        except Exception as e:
            logger.error(f"Firestore Error during get_stale_unresolved_bets: {e}")
            return {}

    def add_unresolved_bet(self, match_id, data):
        if not self.db: return
        match_id_str = str(match_id)
        try:
            data['placed_at'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            self.db.collection('unresolved_bets').document(match_id_str).set(data)
            # Update cache when a bet is added
            self._unresolved_bets_cache[match_id_str] = data 
        except Exception as e:
            logger.error(f"Firestore Error during add_unresolved_bet: {e}")

    def move_to_resolved(self, match_id, bet_info, outcome):
        if not self.db: return False
        match_id_str = str(match_id)
        try:
            resolved_data = {
                **bet_info,
                'outcome': outcome,
                'resolved_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                'resolution_timestamp': firestore.SERVER_TIMESTAMP
            } 
            self.db.collection('resolved_bets').document(match_id_str).set(resolved_data)
            self.db.collection('unresolved_bets').document(match_id_str).delete()
            # Clear from cache when a bet is resolved
            self._unresolved_bets_cache.pop(match_id_str, None) 
            return True
        except Exception as e:
            logger.error(f"Firestore Error during move_to_resolved: {e}")
            return False

    def get_last_api_call(self):
        if not self.db: return None
        try:
            doc = self.db.collection('config').document('api_tracker').get()
            data = doc.to_dict()
            if data and 'last_resolution_api_call' in data:
                return data['last_resolution_api_call']
            return None
        except Exception as e:
            logger.error(f"Firestore Error during get_last_api_call: {e}")
            return None

    def update_last_api_call(self):
        if not self.db: return
        try:
            timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            self.db.collection('config').document('api_tracker').set({
                'last_resolution_api_call': timestamp
            }, merge=True)
        except Exception as e:
            logger.error(f"Firestore Error during update_last_api_call: {e}")


def initialize_sofascore_client():
    """
    Initializes and sets the global SOFASCORE_CLIENT object.
    """
    global SOFASCORE_CLIENT
    
    if SOFASCORE_CLIENT is not None: 
        logger.info("Sofascore client already initialized.")
        return True 

    logger.info("Attempting to initialize Sofascore client...")
    try:
        # Assuming SofascoreClient is the wrapper for SofascoreService
        SOFASCORE_CLIENT = SofascoreClient()
        SOFASCORE_CLIENT.initialize() 
        logger.info("Sofascore client successfully initialized.")
        return True
    except Exception as e:
        logger.critical(f"FATAL: SofascoreClient failed to initialize. Error: {e}", exc_info=True)
        SOFASCORE_CLIENT = None
        return False

def initialize_bot_services():
    """Initializes all external services (Firebase and Sofascore Client)."""
    global firebase_manager

    logger.info("Initializing Football Betting Bot services...")
    
    # 1. Initialize Firebase Manager
    try:
        firebase_manager = FirebaseManager(FIREBASE_CREDENTIALS_JSON_STRING)
    except Exception:
        logger.critical("Bot cannot proceed. Firebase initialization failed.")
        return False
        
    if firebase_manager is None or not firebase_manager.db:
         logger.critical("Bot cannot proceed. Firebase initialization failed.")
         return False

    # 2. Initialize the Sofascore Client
    if not initialize_sofascore_client():
        logger.critical("Bot cannot proceed. Sofascore client initialization failed.")
        return False
        
    logger.info("All bot services initialized successfully.")
    send_telegram("🚀 Football Betting Bot Initialized Successfully! Starting monitoring.")
    return True
    
def shutdown_bot():
    """Closes the Sofascore client resources gracefully. Crucial for Playwright stability."""
    global SOFASCORE_CLIENT
    if SOFASCORE_CLIENT:
        SOFASCORE_CLIENT.close()
        logger.info("Sofascore Client resources closed.")

# =========================================================
# 🏃 CORE LOGIC FUNCTIONS
# =========================================================

def send_telegram(msg, max_retries=3):
    """Send Telegram message with retry mechanism"""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning(f"Telegram credentials missing. Message not sent: {msg}")
        return False
        
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    # Use Markdown for richer presentation
    data = {'chat_id': TELEGRAM_CHAT_ID, 'text': msg, 'parse_mode': 'Markdown'} 
    
    for attempt in range(max_retries):
        try:
            response = requests.post(url, data=data, timeout=10)
            if response.status_code == 200:
                return True
            else:
                logger.error(f"Telegram error (attempt {attempt + 1}): {response.status_code} - {response.text}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Network Error sending Telegram message (attempt {attempt + 1}): {e}")
        
        if attempt < max_retries - 1:
            time.sleep(2 ** attempt)
    
    return False

def get_live_matches():
    """Fetch ONLY live matches using the Sofascore client."""
    if not SOFASCORE_CLIENT:
        logger.error("Sofascore client is not initialized.")
        return []
    try:
        live_events = SOFASCORE_CLIENT.get_events(live=True)
        logger.info(f"Fetched {len(live_events)} live matches.")
        return live_events
    except Exception as e:
        logger.error(f"Sofascore API Error fetching live matches: {e}")
        return []
        
# 🟢 NEW: Function to fetch and cache team goal averages
def get_team_goal_averages(team_id: int, tournament_id: int) -> Optional[TeamTournamentStats]:
    """
    Fetches the team's season-long average goals for a specific league, using a cache.
    """
    global TEAM_STATS_CACHE
    cache_key = f"{team_id}-{tournament_id}"

    if cache_key in TEAM_STATS_CACHE:
        return TEAM_STATS_CACHE[cache_key]

    if not SOFASCORE_CLIENT or not team_id or not tournament_id:
        logger.warning(f"Cannot fetch stats: Client not initialized or missing IDs: Team {team_id}, Tournament {tournament_id}")
        return None

    # Fetch raw data from SofascoreClient (delegates to SofascoreService)
    raw_stats_data = SOFASCORE_CLIENT.get_team_tournament_stats(team_id, tournament_id)

    if raw_stats_data:
        try:
            # Parse the raw data using the new parser
            stats = parse_team_tournament_stats(team_id, tournament_id, raw_stats_data)
            TEAM_STATS_CACHE[cache_key] = stats
            return stats
        except Exception as e:
            logger.error(f"Error parsing stats for Team {team_id} (Tournament {tournament_id}): {e}")
            return None
    else:
        logger.warning(f"No raw stats data returned for Team {team_id} in Tournament {tournament_id}.")
        return None

# ... (get_finished_match_details and robust_get_finished_match_details remain the same) ...
def get_finished_match_details(sofascored_id):
    """
    Fetches the full event details for a match ID using the active Sofascore client.
    """
    if not SOFASCORE_CLIENT: 
        logger.error("Sofascore client is not initialized.")
        return None
    
    sofascored_id = int(sofascored_id) 
    
    try:
        match_data = SOFASCORE_CLIENT.get_event(sofascored_id)
        
        # Check if the returned object is the correct type and has the ID
        if match_data and match_data.id == sofascored_id:
            return match_data
        
        logger.warning(f"Failed to fetch event {sofascored_id} via get_event. Returned data was invalid or mismatched ID.")
        return None
        
    except Exception as e:
        # Log the specific error from the API call
        logger.error(f"Sofascore Client Error fetching finished event {sofascored_id}: {e}")
        return None

def robust_get_finished_match_details(sofascored_id):
    """
    Wrapper to attempt fetching match details with retries and client refresh on persistent failure.
    """
    global SOFASCORE_CLIENT
    
    for attempt in range(MAX_FETCH_RETRIES):
        result = get_finished_match_details(sofascored_id)
        if result:
            if attempt > 0:
                logger.info(f"Successfully fetched {sofascored_id} on attempt {attempt + 1}.")
            return result
        
        if attempt == MAX_FETCH_RETRIES - 1:
            logger.error(f"Permanent failure fetching {sofascored_id} after {MAX_FETCH_RETRIES} attempts. Attempting full client restart.")
            try:
                if SOFASCORE_CLIENT:
                    SOFASCORE_CLIENT.close()
                    SOFASCORE_CLIENT = None 
                initialize_sofascore_client()
                final_result = get_finished_match_details(sofascored_id)
                if final_result:
                    logger.info(f"Successfully fetched {sofascored_id} after client restart.")
                    return final_result
            except Exception as e:
                logger.critical(f"FATAL: Client restart failed for {sofascored_id}: {e}")
            
        
        logger.warning(f"Failed to fetch final data for Sofascore ID {sofascored_id}. Retrying in {2 ** attempt}s (Attempt {attempt + 1}/{MAX_FETCH_RETRIES}).")
        time.sleep(2 ** attempt)
        
    return None


# 🟢 UPDATED: place_regular_bet function (no change required, relies on filtering in process_live_match)
def place_regular_bet(state, fixture_id, score, match_info):
    """Handles placing the initial 36' bet."""
    
    # 🟢 OPTIMIZED: Use direct lookup instead of full collection scan
    if firebase_manager.is_bet_unresolved(fixture_id):
        logger.info(f"Regular bet already exists in 'unresolved_bets' for fixture {fixture_id}. Skipping placement and Telegram message.")
        # Ensure the tracked state is marked as placed to stop re-checking in subsequent runs
        if not state.get('36_bet_placed'):
            state['36_bet_placed'] = True
            # 🟢 MODIFIED: Update the local store
            LOCAL_TRACKED_MATCHES[fixture_id] = state 
        return

    if score in ['1-1', '2-2', '3-3']:
        state['36_bet_placed'] = True
        state['36_score'] = score
        # 🟢 MODIFIED: Update the local store
        LOCAL_TRACKED_MATCHES[fixture_id] = state 

        unresolved_data = {
            'match_name': match_info['match_name'],
            'placed_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
            'league': match_info['league_name'],
            'country': match_info['country'],
            'league_id': match_info['league_id'],
            'bet_type': BET_TYPE_REGULAR,
            '36_score': score,
            'fixture_id': fixture_id,
            'sofascored_id': fixture_id 
        }
        firebase_manager.add_unresolved_bet(fixture_id, unresolved_data)
        
        message = (
            f"⏱️ **36' - {match_info['match_name']}**\n"
            f"🌍 {match_info['country']} | 🏆 {match_info['league_name']}\n"
            f"🔢 Score: {score}\n"
            f"🎯 Correct Score Bet Placed for Half Time"
        )
        send_telegram(message)
    else:
        state['36_bet_placed'] = True
        # 🟢 MODIFIED: Update the local store
        LOCAL_TRACKED_MATCHES[fixture_id] = state 


# ... (check_ht_result remains the same) ...
def check_ht_result(state, fixture_id, score, match_info):
    """Checks the result of all placed bets at halftime, skipping 32' over bets."""
    
    current_score = score
    # 🟢 OPTIMIZED: Use targeted getter function
    unresolved_bet_data = firebase_manager.get_unresolved_bet_data(fixture_id) 

    if unresolved_bet_data:
        bet_type = unresolved_bet_data.get('bet_type')
        outcome = None
        message = ""

        # 🟢 Use corrected league/country info from the 'unresolved_bet_data' 
        country_name = unresolved_bet_data.get('country', 'N/A') 
        league_name = unresolved_bet_data.get('league', 'N/A')
        
        if bet_type == BET_TYPE_REGULAR:
            bet_score = unresolved_bet_data.get('36_score', 'N/A')
            outcome = 'win' if current_score == bet_score else 'loss'
            
            if outcome == 'win':
                message = (
                    f"✅ **HT Result: {match_info['match_name']}**\n"
                    f"🌍 {country_name} | 🏆 {league_name}\n"
                    f"🔢 HT Score: **{current_score}**\n"
                    f"🎯 Bet Score: **{bet_score}**\n"
                    f"🎉 36' Bet WON"
                )
            else:
                message = (
                    f"❌ **HT Result: {match_info['match_name']}**\n"
                    f"🌍 {country_name} | 🏆 {league_name}\n"
                    f"🔢 HT Score: **{current_score}**\n"
                    f"🎯 Bet Score: **{bet_score}**\n"
                    f"🔁 36' Bet LOST"
                )
            
        if outcome:
            firebase_manager.move_to_resolved(fixture_id, unresolved_bet_data, outcome)
            send_telegram(message)
    
    # 🟢 MODIFIED: Clean up the local tracked match store
    if not firebase_manager.is_bet_unresolved(fixture_id):
        if fixture_id in LOCAL_TRACKED_MATCHES:
            del LOCAL_TRACKED_MATCHES[fixture_id]
            logger.info(f"Cleaned up local tracking for fixture {fixture_id}.")


def process_live_match(match):
    """
    Processes a single live match using the Sofascore object structure,
    applying both the amateur/youth filter and the MAX_GOAL_AVERAGE filter.
    """
    fixture_id = str(match.id) # Ensure ID is string for dictionary key
    match_name = f"{match.home_team.name} vs {match.away_team.name}"
    tournament = match.tournament
    
    # =========================================================
    # 1. AMATEUR TOURNAMENT FILTER LOGIC
    # =========================================================
    category_name = tournament.category.name if hasattr(tournament, 'category') and tournament.category else ''
    
    # Concatenate ALL relevant names into a single string for comprehensive filtering
    full_filter_text = (
        f"{tournament.name} "
        f"{category_name} "
        f"{match.home_team.name} "
        f"{match.away_team.name}"
    ).lower()

    if any(keyword in full_filter_text for keyword in AMATEUR_KEYWORDS):
        cleaned_text = full_filter_text.replace('\n', ' ')
        logger.info(f"Skipping amateur/youth league based on keyword found in: {cleaned_text}")
        return # Skip this match

    # =========================================================
    # 2. 🟢 NEW: MAX GOAL AVERAGE FILTER LOGIC
    # =========================================================
    
    home_team_id = match.home_team.id
    away_team_id = match.away_team.id
    league_id = tournament.id

    # a) Get stats for the home team
    home_stats = get_team_goal_averages(home_team_id, league_id)
    if home_stats and home_stats.total_average_goals >= MAX_GOAL_AVERAGE:
        logger.info(
            f"Skipping match {match_name}: Home team avg goals ({home_stats.total_average_goals:.2f}) "
            f"is >= {MAX_GOAL_AVERAGE}"
        )
        return

    # b) Get stats for the away team
    away_stats = get_team_goal_averages(away_team_id, league_id)
    if away_stats and away_stats.total_average_goals >= MAX_GOAL_AVERAGE:
        logger.info(
            f"Skipping match {match_name}: Away team avg goals ({away_stats.total_average_goals:.2f}) "
            f"is >= {MAX_GOAL_AVERAGE}"
        )
        return
        
    if not home_stats or not away_stats:
        # If we can't get reliable stats for both teams, log a warning and skip
        logger.warning(
            f"Skipping match {match_name}: Could not retrieve reliable average goal stats for both teams. "
            "Might be missing data for a new season or a niche league."
        )
        return
    
    logger.info(
        f"Goal Averages OK for {match_name}: "
        f"Home: {home_stats.total_average_goals:.2f}, "
        f"Away: {away_stats.total_average_goals:.2f} (Max: {MAX_GOAL_AVERAGE})"
    )
    
    # =========================================================

    minute = match.total_elapsed_minutes 
    status_description = match.status.description.upper()
    status = 'N/A' 
    
    if '1ST HALF' in status_description: status = '1H'
    elif '2ND HALF' in status_description: status = '2H'
    elif 'HALFTIME' in status_description: status = STATUS_HALFTIME
    elif 'FINISHED' in status_description or 'ENDED' in status_description or 'CANCELLED' in status_description: status = 'FT'
    elif status_description in STATUS_LIVE: status = status_description

    home_goals = match.home_score.current
    away_goals = match.away_score.current
    score = f"{home_goals}-{away_goals}"
    
    if status.upper() not in STATUS_LIVE and status.upper() != STATUS_HALFTIME: return
    if minute is None and status.upper() not in [STATUS_HALFTIME]: return
    
    # 🟢 ENHANCEMENT: Use the global in-memory store instead of Firestore for tracked matches
    state = LOCAL_TRACKED_MATCHES.get(fixture_id) or {
        '36_bet_placed': False,
        '36_score': None,
    }
    # 🟢 Store or update the initial/current state in the local store
    LOCAL_TRACKED_MATCHES[fixture_id] = state

    match_info = {
        'match_name': match_name,
        'league_name': tournament.name if hasattr(match, 'tournament') else 'N/A',
        'country': tournament.category.name if hasattr(match, 'tournament') and hasattr(tournament, 'category') else 'N/A', 
        'league_id': league_id
    }
        
    if status.upper() == '1H' and minute in MINUTES_REGULAR_BET and not state.get('36_bet_placed'):
        place_regular_bet(state, fixture_id, score, match_info)
        
    elif status.upper() == STATUS_HALFTIME and firebase_manager.is_bet_unresolved(fixture_id): # OPTIMIZED
        # Only check HT result if an unresolved bet exists (to avoid unnecessary HT checks)
        check_ht_result(state, fixture_id, score, match_info)
        
    # 🟢 MODIFIED: Clean up the local tracked match if it's finished and all bets are resolved/cleared
    if status in STATUS_FINISHED and not firebase_manager.is_bet_unresolved(fixture_id): # OPTIMIZED
        if fixture_id in LOCAL_TRACKED_MATCHES:
            del LOCAL_TRACKED_MATCHES[fixture_id]
            logger.info(f"Cleaned up local tracking for finished fixture {fixture_id}.")


def check_and_resolve_stale_bets():
    """
    Checks and resolves old, unresolved bets by fetching their final status.
    """
    stale_bets = firebase_manager.get_stale_unresolved_bets(BET_RESOLUTION_WAIT_MINUTES)
    if not stale_bets:
        return
    
    last_call_str = firebase_manager.get_last_api_call()
    last_call_dt = None
    if last_call_str:
        try:
            last_call_dt = datetime.strptime(last_call_str, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            logger.warning("Could not parse last_resolution_api_call timestamp. Proceeding with API call.")

    time_since_last_call = (datetime.utcnow() - last_call_dt).total_seconds() if last_call_dt else FIXTURE_API_INTERVAL + 1
    
    if time_since_last_call < FIXTURE_API_INTERVAL:
        logger.info(f"Skipping FT resolution API call. Last call was {int(time_since_last_call)}s ago. Next in {int(FIXTURE_API_INTERVAL - time_since_last_call)}s.")
        return

    logger.info(f"Initiating FT resolution API calls for {len(stale_bets)} stale bets.")
    successful_api_call = False
    
    for match_id, bet_info in stale_bets.items():
        # Get the stored Sofascore ID for lookup
        sofascored_id = bet_info.get('sofascored_id', match_id) 

        # Use the robust fetcher with the Sofascore ID
        match_data = robust_get_finished_match_details(sofascored_id)
        
        if not match_data:
            logger.warning(f"Failed to fetch final data for fixture {match_id} (Sofascore ID: {sofascored_id}). Will retry on next interval.")
            continue
        
        successful_api_call = True 

        # Check the status from the reliably fetched match_data
        status_description = match_data.status.description.upper()
        
        if 'FINISHED' in status_description or 'ENDED' in status_description:
            # Use the final score from the reliably fetched match_data
            final_score = f"{match_data.home_score.current or 0}-{match_data.away_score.current or 0}"
            match_name = bet_info.get('match_name', f"Match {match_id}")
            bet_type = bet_info.get('bet_type', 'unknown')
            
            # 🟢 Retrieve the corrected info from Firebase
            country_name = bet_info.get('country', 'N/A') 
            league_name = bet_info.get('league', 'N/A') 
            
            outcome = None
            message = ""

            # The logic to resolve bets at Full Time (if you add new bet types later) would go here.
            
            if outcome and outcome != 'error':
                if send_telegram(message):
                    firebase_manager.move_to_resolved(match_id, bet_info, outcome)
                    # 🟢 MODIFIED: Clean up the local tracked match if it still exists
                    if match_id in LOCAL_TRACKED_MATCHES:
                        del LOCAL_TRACKED_MATCHES[match_id] 
                    time.sleep(1)
        
        else:
            logger.info(f"Match {match_id} is stale but not yet finished. Current status: {status_description}. Retrying later.")

    if successful_api_call:
        firebase_manager.update_last_api_call()
        
def run_bot_cycle():
    """Run one complete cycle of the bot"""
    logger.info("Starting bot cycle...")
    
    if not SOFASCORE_CLIENT or not firebase_manager or not firebase_manager.db:
        logger.error("Services are not initialized. Skipping cycle.")
        return
        
    live_matches = get_live_matches() 
    
    for match in live_matches:
        process_live_match(match)
    
    check_and_resolve_stale_bets()
    
    logger.info(f"Bot cycle completed. Currently tracking {len(LOCAL_TRACKED_MATCHES)} matches locally.")

if __name__ == "__main__":
    if initialize_bot_services():
        try:
            while True:
                run_bot_cycle()
                logger.info(f"Sleeping for {SLEEP_TIME} seconds...")
                time.sleep(SLEEP_TIME)
        except KeyboardInterrupt:
            logger.info("Bot shutting down due to user interrupt.")
        except Exception as e:
            logger.critical(f"FATAL UNHANDLED ERROR IN MAIN LOOP: {e}", exc_info=True)
            send_telegram(f"❌ CRITICAL BOT ERROR: {e}. Check logs immediately!")
        finally:
            shutdown_bot()
            logger.info("Bot terminated.")
