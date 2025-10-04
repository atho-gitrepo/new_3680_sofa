import requests
import os
import json
import time
import logging
from datetime import datetime, timedelta
import firebase_admin
from firebase_admin import credentials, firestore
import esd 

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
# NOTE: API_KEY is kept for context but is not used by the esd library.
API_KEY = os.getenv("API_KEY") 
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
FIREBASE_CREDENTIALS_JSON_STRING = os.getenv("FIREBASE_CREDENTIALS_JSON")

# --- CONSTANTS ---
SLEEP_TIME = 90
FIXTURE_API_INTERVAL = 900 # 900 seconds (15 minutes) interval for fixture result API call
MINUTES_REGULAR_BET = [35, 36, 37]
MINUTES_32_MINUTE_BET = [31, 32, 33]
MINUTES_80_MINUTE_BET = [79, 80, 81]
BET_TYPE_REGULAR = 'regular'
BET_TYPE_32_OVER = '32_over' 
BET_TYPE_80_MINUTE = '80_minute'
STATUS_LIVE = ['LIVE', '1H', '2H', 'ET', 'P']
STATUS_HALFTIME = 'HT'
STATUS_FINISHED = ['FT', 'AET', 'PEN'] # Used for internal status cleanup/resolution check
BET_SCORES_80_MINUTE = ['3-1','2-0']

# --- NEW: Initialize Sofascore Client (Global object for reuse) ---
try:
    SOFASCORE_CLIENT = esd.SofascoreClient()
except Exception as e:
    logger.error(f"Failed to initialize SofascoreClient: {e}")
    SOFASCORE_CLIENT = None

class FirebaseManager:
    """Manages all interactions with the Firebase Firestore database."""
    def __init__(self, credentials_json_string):
        try:
            logger.info("Initializing Firebase...")
            if not credentials_json_string:
                logger.warning("FIREBASE_CREDENTIALS_JSON is empty. Skipping Firebase initialization.")
                self.db = None
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

    # Note: All Firebase methods should check if self.db is not None
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
        """
        Retrieves unresolved bets from Firestore that were placed more than `minutes_to_wait` ago.
        This is primarily used to ensure FT resolution for 80' bets and 32' Over bets.
        """
        try:
            bets = self.db.collection('unresolved_bets').stream()
            stale_bets = {}
            time_threshold = datetime.utcnow() - timedelta(minutes=minutes_to_wait)
            
            for doc in bets:
                bet_info = doc.to_dict()
                # Only process bets requiring FT resolution here
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
            # Add a timestamp when the bet was placed
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
            # Use a unique ID based on match and timestamp since this is an append operation
            doc_id = f"{match_id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
            self.db.collection('resolved_bets').document(doc_id).set(resolved_data)
            return True
        except Exception as e:
            logger.error(f"Firestore Error during add_to_resolved_bets: {e}")
            return False

    # Methods to track the last successful resolution API call time
    def get_last_api_call(self):
        """Retrieves the last successful resolution API call time."""
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
        """Updates the last successful resolution API call time to now."""
        if not self.db: return
        try:
            timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            self.db.collection('config').document('api_tracker').set({
                'last_resolution_api_call': timestamp
            }, merge=True)
        except Exception as e:
            logger.error(f"Firestore Error during update_last_api_call: {e}")

# Initialize Firebase
try:
    firebase_manager = FirebaseManager(FIREBASE_CREDENTIALS_JSON_STRING)
except Exception as e:
    logger.critical(f"Critical Firebase initialization error: {e}")
    if not firebase_manager.db:
        logger.warning("Continuing bot execution with disabled Firebase functionality.")

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

# --- API Interaction Functions (Sofascore/esd) ---

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
    Fetches the full event details for a match ID, used primarily for finished matches.
    It uses the search method to look up a specific event by its ID.
    
    Returns: The esd.sofascore.Event object if found, otherwise None.
    """
    if not SOFASCORE_CLIENT: return None
    
    try:
        # Search for the match by its ID
        # esd.SofascoreClient.search expects a string for the query
        match_list = SOFASCORE_CLIENT.search(
            str(fixture_id), 
            entity=esd.sofascore.EntityType.EVENT
        )
        
        # Filter the result to ensure we get the exact match
        for match in match_list:
            if match.id == int(fixture_id):
                return match
        
        return None
    except Exception as e:
        logger.error(f"Error fetching finished match details for {fixture_id}: {e}")
        return None

# --- Betting Logic Functions ---

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
        send_telegram(f"⏱️ 36' - {match_info['match_name']}\n🏆 {match_info['league_name']} ({match_info['country']})\n🔢 Score: {score}\n🎯 Correct Score Bet Placed for Half Time")
    else:
        state['36_bet_placed'] = True
        firebase_manager.update_tracked_match(fixture_id, state)

def place_32_over_bet(state, fixture_id, score, match_info):
    """Handles placing the 32' over bet if score is 0-1 or 1-0."""
    
    # Check for qualifying scores: 0-1, or 1-0
    qualifying_scores = ['0-1', '1-0']
    
    if score in qualifying_scores:
        # The bet is always "Over 2.5"
        over_line = 2.5 
        
        # Update the state to indicate a 32' bet has been placed
        state['32_bet_placed'] = True
        firebase_manager.update_tracked_match(fixture_id, state)

        # Prepare and add unresolved bet data to Firebase
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
        
        # Send Telegram notification
        send_telegram(f"⏱️ 32' - {match_info['match_name']}\n🏆 {match_info['league_name']} ({match_info['country']})\n🔢 Score: {score}\n🎯 Bet Placed: Total Goals **Over {over_line}**for Full Time")
    else:
        # Also mark as placed to avoid re-checking on every loop
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

        if bet_type == BET_TYPE_REGULAR:
            # Get the score the bet was placed on
            bet_score = unresolved_bet_data.get('36_score', 'N/A')
            
            # Logic for 36' correct score bet
            outcome = 'win' if current_score == bet_score else 'loss'
            
            # MODIFIED: Include both current_score (HT score) and bet_score
            if outcome == 'win':
                message = (
                    f"✅ HT Result: {match_info['match_name']}\n"
                    f"🏆 {match_info['league_name']} ({match_info['country']})\n"
                    f"🔢 HT Score: **{current_score}**\n"
                    f"🎯 Bet Score: **{bet_score}**\n"
                    f"🎉 36' Bet WON"
                )
            else:
                message = (
                    f"❌ HT Result: {match_info['match_name']}\n"
                    f"🏆 {match_info['league_name']} ({match_info['country']})\n"
                    f"🔢 HT Score: **{current_score}**\n"
                    f"🎯 Bet Score: **{bet_score}**\n"
                    f"🔁 36' Bet LOST"
                )
            
        elif bet_type == BET_TYPE_32_OVER:
            # Explicitly skip resolution for 32' over bet at halftime
            logger.info(f"Skipping HT resolution for 32' Over bet on fixture {fixture_id}. Awaiting FT.")
            return # Exit without resolving the bet
            
        if outcome:
            firebase_manager.move_to_resolved(fixture_id, unresolved_bet_data, outcome)
            send_telegram(message)
    
    # Only delete tracked match if we've resolved a bet (regular) or found no bet
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
        send_telegram(f"⏱️ 80' - {match_info['match_name']}\n🏆 {match_info['league_name']} ({match_info['country']})\n🔢 Score: {score}\n🎯 80' Correct Score Bet Placed for Full Time")
    else:
        state['80_bet_placed'] = True
        firebase_manager.update_tracked_match(fixture_id, state)

def process_live_match(match):
    """
    Processes a single live match using the Sofascore object structure.
    """
    # Extract data from the new 'esd' match object
    fixture_id = match.id
    match_name = f"{match.home_team.name} vs {match.away_team.name}"
    
    # Status and Time
    minute = match.total_elapsed_minutes 
    status_description = match.status.description.upper()
    
    # Map the status description to your existing STATUS_LIVE, STATUS_HALFTIME, etc.
    status = 'N/A' # Default status
    if '1ST HALF' in status_description:
        status = '1H'
    elif '2ND HALF' in status_description:
        status = '2H'
    elif 'HALFTIME' in status_description:
        status = STATUS_HALFTIME # 'HT'
    elif 'FINISHED' in status_description or 'ENDED' in status_description or 'CANCELLED' in status_description:
         status = 'FT'
    # Fallback for other status like "ET", "PEN", etc., which might be covered by STATUS_LIVE
    elif status_description in STATUS_LIVE:
        status = status_description

    # Scores
    home_goals = match.home_score.current
    away_goals = match.away_score.current
    score = f"{home_goals}-{away_goals}"
    
    # Basic filter checks
    if status.upper() not in STATUS_LIVE and status.upper() != STATUS_HALFTIME:
        return
    if minute is None and status.upper() not in [STATUS_HALFTIME]:
        return
    
    state = firebase_manager.get_tracked_match(fixture_id) or {
        '36_bet_placed': False,
        '32_bet_placed': False, 
        '80_bet_placed': False,
        '36_score': None,
        '80_score': None,
    }
    
    # Extract league info from the nested esd objects
    match_info = {
        'match_name': match_name,
        'league_name': match.tournament.name if hasattr(match, 'tournament') else 'N/A',
        'country': match.tournament.category.name if hasattr(match, 'tournament') and hasattr(match.tournament, 'category') else 'N/A',
        'league_id': match.tournament.id if hasattr(match, 'tournament') else 'N/A'
    }
        
    # 1. 32' Over 2.5 Bet
    if status.upper() == '1H' and minute in MINUTES_32_MINUTE_BET and not state.get('32_bet_placed'):
        place_32_over_bet(state, fixture_id, score, match_info) 
        
    # 2. 36' Regular Bet
    elif status.upper() == '1H' and minute in MINUTES_REGULAR_BET and not state.get('36_bet_placed'):
        place_regular_bet(state, fixture_id, score, match_info)
        
    # 3. Halftime Resolution (for 36' bets)
    elif status.upper() == STATUS_HALFTIME and firebase_manager.get_unresolved_bets().get(str(fixture_id)):
        check_ht_result(state, fixture_id, score, match_info)
        
    # 4. 80' Bet
    elif status.upper() == '2H' and minute in MINUTES_80_MINUTE_BET and not state.get('80_bet_placed'):
        place_80_minute_bet(state, fixture_id, score, match_info)
    
    # If the match is finished and there are no unresolved bets, delete the tracked match state
    if status in STATUS_FINISHED and not firebase_manager.get_unresolved_bets().get(str(fixture_id)):
        firebase_manager.delete_tracked_match(fixture_id)


def check_and_resolve_stale_bets():
    """
    Checks and resolves old, unresolved bets by fetching their final status using the search method.
    This function handles 80' bets and 32' Over bets that require FT resolution.
    """
    stale_bets = firebase_manager.get_stale_unresolved_bets()
    if not stale_bets:
        return
    
    # --- TIME-GATE LOGIC ---
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
        # Use the new function to fetch the event object containing final score/status
        match_data = get_finished_match_details(match_id)
        
        if not match_data:
            logger.warning(f"Failed to fetch final data for fixture {match_id}. Will retry on next interval.")
            continue
        
        # Mark successful API call to update timestamp after the loop
        successful_api_call = True 

        # Extract final status and score from the Event object
        status_description = match_data.status.description.upper()
        
        # We only resolve if the match is truly finished
        if 'FINISHED' in status_description or 'ENDED' in status_description:
            # The final score is always the current score when the match is finished
            final_score = f"{match_data.home_score.current or 0}-{match_data.away_score.current or 0}"
            
            match_name = bet_info.get('match_name', f"Match {match_id}")
            bet_type = bet_info.get('bet_type', 'unknown')
            outcome = None
            message = ""

            if bet_type == BET_TYPE_80_MINUTE:
                # Logic for 80' correct score bet
                bet_score = bet_info.get('80_score')
                outcome = 'win' if final_score == bet_score else 'loss'
                message = f"🏁 FINAL RESULT - 80' Bet\n⚽ {match_name}\n🔢 Final Score: {final_score}\n🎯 Bet on 80' Score: {bet_score}\n📊 Outcome: {'✅ WON' if outcome == 'win' else '❌ LOST'}"

            elif bet_type == BET_TYPE_32_OVER:
                # Logic for 32' Over 2.5 bet
                over_line = bet_info.get('over_line') # Should be 2.5
                try:
                    home_goals, away_goals = map(int, final_score.split('-'))
                    total_goals = home_goals + away_goals
                    
                    if total_goals > over_line:
                        outcome = 'win'
                    elif total_goals < over_line:
                        outcome = 'loss'
                    else: 
                        outcome = 'push' # Unlikely in this case, but good practice
                        
                    message = f"🏁 FINAL RESULT - 32' Over Bet\n⚽ {match_name}\n🔢 Final Score: {final_score}\n🎯 Bet: Over {over_line}\n📊 Outcome: {'✅ WON' if outcome == 'win' else '❌ LOST' if outcome == 'loss' else '➖ PUSH'}"
                except ValueError:
                    outcome = 'error'
                    message = f"⚠️ FINAL RESULT: {match_name}\n❌ Bet could not be resolved due to score format issue."

            if outcome and outcome != 'error':
                if send_telegram(message):
                    # Move to resolved collection and delete from unresolved
                    firebase_manager.move_to_resolved(match_id, bet_info, outcome)
                    # Also delete the match from tracked_matches state as it's finished
                    firebase_manager.delete_tracked_match(match_id) 
                time.sleep(1)
        
        else:
            logger.info(f"Match {match_id} is stale but not yet finished. Current status: {status_description}. Retrying later.")


    # Update API call time only if at least one fixture was successfully fetched.
    if successful_api_call:
        firebase_manager.update_last_api_call()

def run_bot_once():
    """Run one complete cycle of the bot"""
    logger.info("Starting bot cycle...")
    
    # Use the new Sofascore API function
    live_matches = get_live_matches() 
    
    for match in live_matches:
        process_live_match(match)
    
    # Check and resolve finished bets
    check_and_resolve_stale_bets()
    
    logger.info("Bot cycle completed.")

if __name__ == "__main__":
    logger.info("Starting Football Betting Bot")
    # Initial startup message
    send_telegram("🚀 Football Betting Bot Started Successfully! Monitoring live games (via Sofascore API).")
    
    while True:
        try:
            run_bot_once()
        except Exception as e:
            error_msg = f"❌ CRITICAL ERROR: {str(e)}"
            logger.critical(error_msg, exc_info=True)
            send_telegram(error_msg[:300])
        finally:
            time.sleep(SLEEP_TIME)
