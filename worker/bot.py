import requests
import os
import json
import time
import logging
from datetime import datetime, timedelta
import firebase_admin
from firebase_admin import credentials, firestore
from esd.sofascore import SofascoreClient, EntityType 

# --- GLOBAL VARIABLES ---
SOFASCORE_CLIENT = None 
firebase_manager = None 
LOCAL_TRACKED_MATCHES = {} 

# --- LOGGING CONFIGURATION ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    handlers=[
        logging.FileHandler("bot_detailed.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("BetBot")

# --- CONFIGURATION ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "DUMMY_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "DUMMY_CHAT_ID")
FIREBASE_CREDENTIALS_JSON_STRING = os.getenv("FIREBASE_CREDENTIALS_JSON", "") 

# --- STAKING SETTINGS ---
ORIGINAL_STAKE = 10.0
MAX_CHASE_LEVEL = 4

# --- CONSTANTS ---
SLEEP_TIME = 60
MINUTES_REGULAR_BET = [36, 37]
BET_TYPE_REGULAR = 'regular'
STATUS_HALFTIME = 'HT'

# --- FILTER LISTS ---
ALLOWED_LEAGUES = ['Campeonato Brasileiro Série A', 'Segunda Division, Apertura', 'Copa do Brasil', 'Premier League']
EXCLUDED_LEAGUES = ['USA', 'Poland', 'Mexico', 'Wales', 'Portugal', 'Denmark', 'Malta', 'Germany', 'Hungary', 'Sweden', 'Serbia', 'Switzerland', 'Cyprus', 'El Salvador', 'Lithuania', 'Honduras', 'Chile', 'Norway', 'England', 'England Amateur', 'Iceland', 'Seychelles', 'Hong Kong 2nd Division', 'Primera División Reserve, Apertura', 'U19 PAF Ligi', 'U17 CONCACAF Championship', 'Bosnia & Herzegovina', 'Italy Series D', 'Colombia', 'Jordan Reserve League', 'División Profesional', 'Mumbai Premier League', 'Serie C', '3. Liga']
AMATEUR_KEYWORDS = ['amateur', 'youth', 'reserves', 'friendly', 'u23', 'u21', 'u19', 'u17', 'liga pro', 'women', 'college', 'ncaa']

# =========================================================
# 🟢 FIREBASE MANAGER (WITH DETAILED LOGGING)
# =========================================================

class FirebaseManager:
    def __init__(self, credentials_json_string):
        self.db = None
        try:
            logger.info("Initializing Firebase connection...")
            if not credentials_json_string:
                logger.error("FIREBASE_CREDENTIALS_JSON_STRING is missing!")
                return
            cred_dict = json.loads(credentials_json_string)
            cred = credentials.Certificate(cred_dict)
            if not firebase_admin._apps:
                firebase_admin.initialize_app(cred)
            self.db = firestore.client()
            logger.info("✅ Firebase initialized and connected.")
        except Exception as e:
            logger.error(f"❌ Firebase Init Failed: {e}", exc_info=True)

    def is_state_locked(self) -> bool:
        """STATE-LOCK: Check if an unresolved bet exists."""
        if not self.db: return False
        try:
            docs = self.db.collection('unresolved_bets').limit(1).get()
            locked = len(docs) > 0
            if locked:
                logger.debug("State-Lock Check: [LOCKED] Active bet found.")
            else:
                logger.debug("State-Lock Check: [CLEAR] No active bets.")
            return locked
        except Exception as e:
            logger.error(f"Error checking state lock: {e}")
            return False

    def get_last_resolved_bet(self):
        """Fetch history for Martingale logic."""
        if not self.db: return None
        try:
            logger.debug("Fetching last resolved bet for staking logic...")
            query = self.db.collection('resolved_bets').order_by(
                'resolution_timestamp', direction=firestore.Query.DESCENDING
            ).limit(1).get()
            for doc in query:
                data = doc.to_dict()
                logger.info(f"Last bet found: {data.get('match_name')} | Outcome: {data.get('outcome')}")
                return data
            logger.info("No betting history found in Firebase.")
            return None
        except Exception as e:
            logger.error(f"Error fetching history: {e}")
            return None

    def add_unresolved_bet(self, match_id, data):
        if not self.db: return
        try:
            logger.info(f"Writing unresolved bet to Firebase: {match_id} ({data['match_name']})")
            data['placed_at'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            self.db.collection('unresolved_bets').document(str(match_id)).set(data)
        except Exception as e:
            logger.error(f"Error adding unresolved bet: {e}")

    def move_to_resolved(self, match_id, bet_info, outcome):
        if not self.db: return False
        try:
            logger.info(f"Resolving bet {match_id} as {outcome.upper()}")
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
            logger.error(f"Error resolving bet: {e}")
            return False

# =========================================================
# 🟢 STAKING & LOGIC (WITH DETAILED LOGGING)
# =========================================================

def calculate_next_stake():
    """Martingale calculation with logging."""
    logger.info("Calculating next stake amount based on history...")
    last_bet = firebase_manager.get_last_resolved_bet()
    
    if not last_bet:
        logger.info(f"Start of sequence: Match 1 | Stake: ${ORIGINAL_STAKE}")
        return ORIGINAL_STAKE, 1

    last_outcome = last_bet.get('outcome', 'win').lower()
    last_seq = last_bet.get('match_sequence', 1)

    if last_outcome == 'win':
        logger.info("Result was WIN. Resetting sequence to Match 1.")
        return ORIGINAL_STAKE, 1
    
    if last_seq < MAX_CHASE_LEVEL:
        new_seq = last_seq + 1
        new_stake = ORIGINAL_STAKE * (2 ** (new_seq - 1))
        logger.warning(f"Result was LOSS. Recovery Step: Match {new_seq} | New Stake: ${new_stake}")
        return float(new_stake), new_seq
    else:
        logger.error("MAX CHASE LEVEL REACHED. Resetting to Match 1 to preserve bankroll.")
        return ORIGINAL_STAKE, 1

def place_regular_bet(state, fixture_id, score, match_info):
    """Log the alert flow and state lock."""
    logger.info(f"Evaluating alert for: {match_info['match_name']} (Score: {score})")
    
    # 1. Check State-Lock
    if firebase_manager.is_state_locked():
        if not state.get('lock_logged'):
            logger.warning(f"🚫 ALERT SUPPRESSED: System is locked by an unresolved bet. Skipping {match_info['match_name']}.")
            state['lock_logged'] = True
        return

    # 2. Check Score Criteria
    if score in ['1-1', '2-2', '3-3']:
        logger.info(f"✅ Criteria met for {match_info['match_name']}. Processing stake...")
        stake, sequence = calculate_next_stake()

        unresolved_data = {
            'match_name': match_info['match_name'],
            'league': match_info['league_name'],
            'country': match_info['country'],
            'bet_type': BET_TYPE_REGULAR,
            '36_score': score,
            'fixture_id': fixture_id,
            'stake': stake,
            'match_sequence': sequence
        }
        
        firebase_manager.add_unresolved_bet(fixture_id, unresolved_data)
        
        label = "RECOVERY CHASE" if sequence > 1 else "INITIAL BET"
        message = (
            f"🎯 **{label} | Match {sequence}**\n"
            f"⏱️ **36' - {match_info['match_name']}**\n"
            f"🌍 {match_info['country']} | 🏆 {match_info['league_name']}\n"
            f"🔢 Score: **{score}**\n"
            f"💰 **Stake: ${stake:.2f}**"
        )
        if send_telegram(message):
            logger.info(f"📡 Telegram alert sent for {match_info['match_name']}")
        state['36_bet_placed'] = True
    else:
        logger.info(f"Match {match_info['match_name']} score {score} does not match draw criteria. Skipping.")
        state['36_bet_placed'] = True

def check_ht_result(state, fixture_id, score, match_info):
    """Log resolution details."""
    logger.info(f"Match {match_info['match_name']} reached Halftime. Checking result...")
    unresolved_data = firebase_manager.get_unresolved_bet_data(fixture_id)
    if not unresolved_data: 
        logger.warning(f"No unresolved bet data found in Firebase for {fixture_id} at HT.")
        return

    target_score = unresolved_data.get('36_score')
    outcome = 'win' if score == target_score else 'loss'
    
    logger.info(f"Resolution for {match_info['match_name']}: HT Score {score} vs Target {target_score} -> Result: {outcome.upper()}")
    
    emoji = "✅ WIN" if outcome == 'win' else "❌ LOSS"
    msg = (
        f"{emoji} **HT Result: {match_info['match_name']}**\n"
        f"🔢 HT Score: **{score}** (Target: {target_score})\n"
        f"🔓 **State Unlocked.**"
    )
    
    if firebase_manager.move_to_resolved(fixture_id, unresolved_data, outcome):
        send_telegram(msg)
        if fixture_id in LOCAL_TRACKED_MATCHES:
            del LOCAL_TRACKED_MATCHES[fixture_id]
            logger.info(f"Local state cleared for {fixture_id}.")

def process_live_match(match):
    """Detailed filtering logs."""
    fixture_id = str(match.id)
    league_name = match.tournament.name
    category_name = match.tournament.category.name
    full_text = f"{league_name} {category_name}".lower()

    # FILTERING LOGS
    is_allowed = any(k.lower() in league_name.lower() for k in ALLOWED_LEAGUES)
    if not is_allowed:
        if any(k.lower() in full_text for k in EXCLUDED_LEAGUES):
            logger.debug(f"Filtered (Blacklist): {league_name} ({category_name})")
            return
        if any(k.lower() in full_text for k in AMATEUR_KEYWORDS):
            logger.debug(f"Filtered (Amateur): {league_name} ({category_name})")
            return

    minute = match.total_elapsed_minutes 
    status_desc = match.status.description.upper()
    
    # Map status
    if '1ST' in status_desc: status = '1H'
    elif 'HALFTIME' in status_desc: status = STATUS_HALFTIME
    else: status = 'OTHER'

    score = f"{match.home_score.current}-{match.away_score.current}"

    state = LOCAL_TRACKED_MATCHES.get(fixture_id) or {'36_bet_placed': False, 'lock_logged': False}
    LOCAL_TRACKED_MATCHES[fixture_id] = state

    match_info = {
        'match_name': f"{match.home_team.name} vs {match.away_team.name}", 
        'league_name': league_name, 
        'country': category_name
    }

    if status == '1H' and minute in MINUTES_REGULAR_BET and not state['36_bet_placed']:
        place_regular_bet(state, fixture_id, score, match_info)
    elif status == STATUS_HALFTIME and firebase_manager.is_bet_unresolved(fixture_id):
        check_ht_result(state, fixture_id, score, match_info)

# =========================================================
# ⚙️ SYSTEM WRAPPERS
# =========================================================

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        r = requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'text': msg, 'parse_mode': 'Markdown'}, timeout=10)
        return r.status_code == 200
    except Exception as e:
        logger.error(f"Telegram error: {e}")
        return False

def initialize_bot_services():
    global firebase_manager, SOFASCORE_CLIENT
    logger.info("System Booting...")
    firebase_manager = FirebaseManager(FIREBASE_CREDENTIALS_JSON_STRING)
    try:
        SOFASCORE_CLIENT = SofascoreClient()
        SOFASCORE_CLIENT.initialize()
        logger.info("Sofascore Client Initialized.")
        return True
    except Exception as e:
        logger.critical(f"Sofascore Init Failed: {e}")
        return False

def shutdown_bot():
    if SOFASCORE_CLIENT:
        logger.info("Closing Sofascore Client...")
        SOFASCORE_CLIENT.close()

def run_bot_cycle():
    if not SOFASCORE_CLIENT: return
    try:
        logger.info("--- Starting Live Match Scan ---")
        live_matches = SOFASCORE_CLIENT.get_events(live=True)
        logger.info(f"Found {len(live_matches)} matches in live feed.")
        for match in live_matches:
            process_live_match(match)
        logger.info("--- Scan Cycle Finished ---")
    except Exception as e:
        logger.error(f"Fatal Cycle Error: {e}", exc_info=True)
