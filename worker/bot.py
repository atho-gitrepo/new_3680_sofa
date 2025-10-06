# bot.py

import requests
import os
import json
import time
import logging
from datetime import datetime, timedelta
import firebase_admin
from firebase_admin import credentials, firestore
# Correct import structure for your local library
from esd.sofascore import SofascoreClient, EntityType 

# --- GLOBAL VARIABLES ---
SOFASCORE_CLIENT = None 
firebase_manager = None 

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
SLEEP_TIME = 90
FIXTURE_API_INTERVAL = 900
MINUTES_REGULAR_BET = [35, 36, 37]
MINUTES_32_MINUTE_BET = [31, 32, 33]
MINUTES_80_MINUTE_BET = [79, 80, 81]
BET_TYPE_REGULAR = 'regular'
BET_TYPE_32_OVER = '32_over' 
BET_TYPE_80_MINUTE = '80_minute'
STATUS_LIVE = ['LIVE', '1H', '2H', 'ET', 'P']
STATUS_HALFTIME = 'HT'
STATUS_FINISHED = ['FT', 'AET', 'PEN'] 
BET_SCORES_80_MINUTE = ['3-1','2-0']
MAX_FETCH_RETRIES = 3 # New constant for retries

# =========================================================
# 📌 INITIALIZATION FUNCTIONS
# =========================================================

class FirebaseManager:
    """Manages all interactions with the Firebase Firestore database."""
    def __init__(self, credentials_json_string):
        self.db = None
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
            
    def get_tracked_match(self, match_id):
        if not self.db: return None
        try:
            doc = self.db.collection('tracked_matches').document(str(match_id)).get()
            return doc.to_dict() if doc.exists else None
        except Exception as e:
            logger.error(f"Firestore Error during get_tracked_match: {e}")
            return None

    def update_tracked_match(self, match_id, data):
        if not self.db: return
        try:
            self.db.collection('tracked_matches').document(str(match_id)).set(data, merge=True)
        except Exception as e:
            logger.error(f"Firestore Error during update_tracked_match: {e}")
            
    def delete_tracked_match(self, match_id):
        if not self.db: return
        try:
            self.db.collection('tracked_matches').document(str(match_id)).delete()
        except Exception as e:
            logger.error(f"Firestore Error during delete_tracked_match: {e}")

    def get_unresolved_bets(self):
        if not self.db: return {}
        try:
            bets = self.db.collection('unresolved_bets').stream()
            result = {doc.id: doc.to_dict() for doc in bets}
            return result
        except Exception as e:
            logger.error(f"Firestore Error during get_unresolved_bets: {e}")
            return {}
    
    def get_stale_unresolved_bets(self, minutes_to_wait=20):
        if not self.db: return {}
        try:
            bets = self.db.collection('unresolved_bets').stream()
            stale_bets = {}
            time_threshold = datetime.utcnow() - timedelta(minutes=minutes_to_wait)
            
            for doc in bets:
                bet_info = doc.to_dict()
                if bet_info.get('bet_type') in [BET_TYPE_80_MINUTE, BET_TYPE_32_OVER]: 
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
        try:
            data['placed_at'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            self.db.collection('unresolved_bets').document(str(match_id)).set(data)
        except Exception as e:
            logger.error(f"Firestore Error during add_unresolved_bet: {e}")

    def move_to_resolved(self, match_id, bet_info, outcome):
        if not self.db: return False
        try:
            resolved_data = {
                **bet_info,
                'outcome': outcome,
                'resolved_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                'resolution_timestamp': firestore.SERVER_TIMESTAMP
            } 
            self.db.collection('resolved_bets').document(str(match_id)).set(resolved_data)
            self.db.collection('unresolved_bets').document(str(match_id)).delete()
            return True
        except Exception as e:
            logger.error(f"Firestore Error during move_to_resolved: {e}")
            return False

    def add_to_resolved_bets(self, match_id, bet_info, outcome):
        if not self.db: return False
        try:
            resolved_data = {
                **bet_info,
                'outcome': outcome,
                'resolved_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                'resolution_timestamp': firestore.SERVER_TIMESTAMP
            }
            doc_id = f"{match_id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
            self.db.collection('resolved_bets').document(doc_id).set(resolved_data)
            return True
        except Exception as e:
            logger.error(f"Firestore Error during add_to_resolved_bets: {e}")
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
    Initializes and sets the global SOFASCORE_CLIENT object, 
    ensuring a fresh instance is created if needed.
    """
    global SOFASCORE_CLIENT
    
    # If client exists and is marked as initialized (by an internal flag, if possible), skip.
    # We rely on the client's internal state to prevent re-initialization.
    if SOFASCORE_CLIENT is not None: 
        logger.info("Sofascore client already initialized.")
        return True 

    logger.info("Attempting to initialize Sofascore client...")
    try:
        # Initialize the client. This will launch Playwright/setup API client.
        SOFASCORE_CLIENT = SofascoreClient()
        # Call the explicit initialization if it's not done in __init__
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
    data = {'chat_id': TELEGRAM_CHAT_ID, 'text': msg}
    
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

def get_finished_match_details(fixture_id):
    """
    Fetches the full event details for a match ID using the active Sofascore client.
    This is the core, single-attempt fetch function.
    """
    if not SOFASCORE_CLIENT: 
        logger.error("Sofascore client is not initialized.")
        return None
    
    try:
        match_list = SOFASCORE_CLIENT.search(
            str(fixture_id), 
            entity=EntityType.EVENT
        )
        
        for match in match_list:
            if match.id == int(fixture_id):
                return match
        
        # This could indicate a data not found issue, not a connection issue.
        logger.warning(f"Search for fixture {fixture_id} returned no matching event ID.")
        return None
    except Exception as e:
        # Catch any Playwright/Network error from the underlying service.
        logger.error(f"Sofascore Client Search Error for {fixture_id}: {e}")
        return None

def robust_get_finished_match_details(fixture_id):
    """
    Wrapper to attempt fetching match details with retries and client refresh on persistent failure.
    (This is the function we made robust against transient errors.)
    """
    global SOFASCORE_CLIENT
    
    for attempt in range(MAX_FETCH_RETRIES):
        result = get_finished_match_details(fixture_id)
        if result:
            if attempt > 0:
                logger.info(f"Successfully fetched {fixture_id} on attempt {attempt + 1}.")
            return result
        
        # If it's the last attempt and we still failed, try a full client restart
        if attempt == MAX_FETCH_RETRIES - 1:
            logger.error(f"Permanent failure fetching {fixture_id} after {MAX_FETCH_RETRIES} attempts. Attempting full client restart.")
            try:
                if SOFASCORE_CLIENT:
                    SOFASCORE_CLIENT.close()
                    SOFASCORE_CLIENT = None # Ensure global is cleared
                initialize_sofascore_client()
                # Try one last time after restart
                final_result = get_finished_match_details(fixture_id)
                if final_result:
                    logger.info(f"Successfully fetched {fixture_id} after client restart.")
                    return final_result
            except Exception as e:
                logger.critical(f"FATAL: Client restart failed for {fixture_id}: {e}")
            
        
        logger.warning(f"Failed to fetch final data for fixture {fixture_id}. Retrying in {2 ** attempt}s (Attempt {attempt + 1}/{MAX_FETCH_RETRIES}).")
        time.sleep(2 ** attempt)
        
    return None

def place_regular_bet(state, fixture_id, score, match_info):
    """Handles placing the initial 36' bet."""
    if score in ['1-1', '2-2', '3-3']:
        state['36_bet_placed'] = True
        state['36_score'] = score
        firebase_manager.update_tracked_match(fixture_id, state)
        unresolved_data = {
            'match_name': match_info['match_name'],
            'placed_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
            'league': match_info['league_name'],
            'country': match_info['country'],
            'league_id': match_info['league_id'],
            'bet_type': BET_TYPE_REGULAR,
            '36_score': score,
            'fixture_id': fixture_id
        }
        firebase_manager.add_unresolved_bet(fixture_id, unresolved_data)
        
        # 🟢 UPDATED TEMPLATE with country
        message = (
            f"⏱️ 36' - {match_info['match_name']}\n"
            f"🌍 {match_info['country']}\n"
            f"🏆 {match_info['league_name']}\n"
            f"🔢 Score: {score}\n"
            f"🎯 Correct Score Bet Placed for Half Time"
        )
        send_telegram(message)
    else:
        state['36_bet_placed'] = True
        firebase_manager.update_tracked_match(fixture_id, state)

def place_32_over_bet(state, fixture_id, score, match_info):
    """Handles placing the 32' over bet if score is 0-1 or 1-0."""
    
    qualifying_scores = ['0-1', '1-0']
    
    if score in qualifying_scores:
        over_line = 2.5 
        state['32_bet_placed'] = True
        firebase_manager.update_tracked_match(fixture_id, state)
        unresolved_data = {
            'match_name': match_info['match_name'],
            'placed_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
            'league': match_info['league_name'],
            'country': match_info['country'],
            'league_id': match_info['league_id'],
            'bet_type': BET_TYPE_32_OVER, 
            '32_score': score,
            'over_line': over_line,
            'fixture_id': fixture_id
        }
        firebase_manager.add_unresolved_bet(fixture_id, unresolved_data)
        
        # 🟢 UPDATED TEMPLATE with country
        telegram_message = (
            f"⏱️ 32' - {match_info['match_name']}\n"
            f"🌍 {match_info['country']}\n"
            f"🏆 {match_info['league_name']}\n"
            f"🔢 Score: {score}\n"
            f"🎯 Bet Placed: Total Goals **Over {over_line}**for Full Time"
        )
        send_telegram(telegram_message)
    else:
        state['32_bet_placed'] = True
        firebase_manager.update_tracked_match(fixture_id, state)

def check_ht_result(state, fixture_id, score, match_info):
    """Checks the result of all placed bets at halftime, skipping 32' over bets."""
    
    current_score = score
    unresolved_bet_data = firebase_manager.get_unresolved_bets().get(str(fixture_id))

    if unresolved_bet_data:
        bet_type = unresolved_bet_data.get('bet_type')
        outcome = None
        message = ""

        country_name = unresolved_bet_data.get('country', 'N/A') # Get country from Firebase data
        
        if bet_type == BET_TYPE_REGULAR:
            bet_score = unresolved_bet_data.get('36_score', 'N/A')
            outcome = 'win' if current_score == bet_score else 'loss'
            
            if outcome == 'win':
                # 🟢 UPDATED TEMPLATE with country
                message = (
                    f"✅ HT Result: {match_info['match_name']}\n"
                    f"🌍 {country_name}\n"
                    f"🏆 {match_info['league_name']}\n"
                    f"🔢 HT Score: **{current_score}**\n"
                    f"🎯 Bet Score: **{bet_score}**\n"
                    f"🎉 36' Bet WON"
                )
            else:
                # 🟢 UPDATED TEMPLATE with country
                message = (
                    f"❌ HT Result: {match_info['match_name']}\n"
                    f"🌍 {country_name}\n"
                    f"🏆 {match_info['league_name']}\n"
                    f"🔢 HT Score: **{current_score}**\n"
                    f"🎯 Bet Score: **{bet_score}**\n"
                    f"🔁 36' Bet LOST"
                )
            
        elif bet_type == BET_TYPE_32_OVER:
            logger.info(f"Skipping HT resolution for 32' Over bet on fixture {fixture_id}. Awaiting FT.")
            return 
            
        if outcome:
            firebase_manager.move_to_resolved(fixture_id, unresolved_bet_data, outcome)
            send_telegram(message)
    
    if unresolved_bet_data is None or (unresolved_bet_data.get('bet_type') == BET_TYPE_REGULAR and outcome):
        firebase_manager.delete_tracked_match(fixture_id)

def place_80_minute_bet(state, fixture_id, score, match_info):
    """Handles placing the new 80' bet."""
    if score in BET_SCORES_80_MINUTE:
        state['80_bet_placed'] = True
        state['80_score'] = score
        firebase_manager.update_tracked_match(fixture_id, state)
        unresolved_data = {
            'match_name': match_info['match_name'],
            'placed_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
            'league': match_info['league_name'],
            'country': match_info['country'],
            'league_id': match_info['league_id'],
            'bet_type': BET_TYPE_80_MINUTE,
            '80_score': score,
            'fixture_id': fixture_id
        }
        firebase_manager.add_unresolved_bet(fixture_id, unresolved_data)
        
        # 🟢 UPDATED TEMPLATE with country
        message = (
            f"⏱️ 80' - {match_info['match_name']}\n"
            f"🌍 {match_info['country']}\n"
            f"🏆 {match_info['league_name']}\n"
            f"🔢 Score: {score}\n"
            f"🎯 80' Correct Score Bet Placed for Full Time"
        )
        send_telegram(message)
    else:
        state['80_bet_placed'] = True
        firebase_manager.update_tracked_match(fixture_id, state)

def process_live_match(match):
    """
    Processes a single live match using the Sofascore object structure.
    """
    fixture_id = match.id
    match_name = f"{match.home_team.name} vs {match.away_team.name}"
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
    
    state = firebase_manager.get_tracked_match(fixture_id) or {
        '36_bet_placed': False,
        '32_bet_placed': False, 
        '80_bet_placed': False,
        '36_score': None,
        '80_score': None,
    }
    
    match_info = {
        'match_name': match_name,
        'league_name': match.tournament.name if hasattr(match, 'tournament') else 'N/A',
        # Correctly extracting the country name (category)
        'country': match.tournament.category.name if hasattr(match, 'tournament') and hasattr(match.tournament, 'category') else 'N/A', 
        'league_id': match.tournament.id if hasattr(match, 'tournament') else 'N/A'
    }
        
    if status.upper() == '1H' and minute in MINUTES_32_MINUTE_BET and not state.get('32_bet_placed'):
        place_32_over_bet(state, fixture_id, score, match_info) 
        
    elif status.upper() == '1H' and minute in MINUTES_REGULAR_BET and not state.get('36_bet_placed'):
        place_regular_bet(state, fixture_id, score, match_info)
        
    elif status.upper() == STATUS_HALFTIME and firebase_manager.get_unresolved_bets().get(str(fixture_id)):
        check_ht_result(state, fixture_id, score, match_info)
        
    elif status.upper() == '2H' and minute in MINUTES_80_MINUTE_BET and not state.get('80_bet_placed'):
        place_80_minute_bet(state, fixture_id, score, match_info)
    
    if status in STATUS_FINISHED and not firebase_manager.get_unresolved_bets().get(str(fixture_id)):
        firebase_manager.delete_tracked_match(fixture_id)


def check_and_resolve_stale_bets():
    """
    Checks and resolves old, unresolved bets by fetching their final status.
    Uses the robust fetching wrapper for resilience.
    """
    stale_bets = firebase_manager.get_stale_unresolved_bets()
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
        # *** CHANGED: Use the robust function here ***
        match_data = robust_get_finished_match_details(match_id)
        
        if not match_data:
            logger.warning(f"Failed to fetch final data for fixture {match_id}. Will retry on next interval.")
            continue
        
        successful_api_call = True 

        status_description = match_data.status.description.upper()
        
        if 'FINISHED' in status_description or 'ENDED' in status_description:
            final_score = f"{match_data.home_score.current or 0}-{match_data.away_score.current or 0}"
            match_name = bet_info.get('match_name', f"Match {match_id}")
            bet_type = bet_info.get('bet_type', 'unknown')
            country_name = bet_info.get('country', 'N/A') # Get country from Firebase data
            outcome = None
            message = ""

            if bet_type == BET_TYPE_80_MINUTE:
                bet_score = bet_info.get('80_score')
                outcome = 'win' if final_score == bet_score else 'loss'
                # 🟢 UPDATED TEMPLATE with country
                message = (
                    f"🏁 FINAL RESULT - 80' Bet\n"
                    f"⚽ {match_name}\n"
                    f"🌍 {country_name}\n"
                    f"🔢 Final Score: {final_score}\n"
                    f"🎯 Bet on 80' Score: {bet_score}\n"
                    f"📊 Outcome: {'✅ WON' if outcome == 'win' else '❌ LOST'}"
                )

            elif bet_type == BET_TYPE_32_OVER:
                over_line = bet_info.get('over_line')
                try:
                    home_goals, away_goals = map(int, final_score.split('-'))
                    total_goals = home_goals + away_goals
                    
                    if total_goals > over_line: outcome = 'win'
                    elif total_goals < over_line: outcome = 'loss'
                    else: outcome = 'push'
                        
                    # 🟢 UPDATED TEMPLATE with country
                    message = (
                        f"🏁 FINAL RESULT - 32' Over Bet\n"
                        f"⚽ {match_name}\n"
                        f"🌍 {country_name}\n"
                        f"🔢 Final Score: {final_score}\n"
                        f"🎯 Bet: Over {over_line}\n"
                        f"📊 Outcome: {'✅ WON' if outcome == 'win' else '❌ LOST' if outcome == 'loss' else '➖ PUSH'}"
                    )
                except ValueError:
                    outcome = 'error'
                    message = f"⚠️ FINAL RESULT: {match_name}\n❌ Bet could not be resolved due to score format issue."

            if outcome and outcome != 'error':
                if send_telegram(message):
                    firebase_manager.move_to_resolved(match_id, bet_info, outcome)
                    firebase_manager.delete_tracked_match(match_id) 
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
    
    logger.info("Bot cycle completed.")
# -----------------------------------------------------------
# Note: NO 'if __name__ == "__main__":' BLOCK in bot.py
# -----------------------------------------------------------
