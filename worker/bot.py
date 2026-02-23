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

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("bot.log"), logging.StreamHandler()]
)
logger = logging.getLogger("FootballBettingBot")

# --- ENVIRONMENT & CONFIG ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "DUMMY_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "DUMMY_CHAT_ID")
FIREBASE_CREDENTIALS_JSON_STRING = os.getenv("FIREBASE_CREDENTIALS_JSON", "") 

# --- STAKING PARAMETERS ---
ORIGINAL_STAKE = 10.0  # Base amount
MAX_CHASE_LEVEL = 4     # Sequence stops after Match 4

# --- CONSTANTS ---
SLEEP_TIME = 60
MINUTES_REGULAR_BET = [36, 37]
BET_TYPE_REGULAR = 'regular'
STATUS_HALFTIME = 'HT'
BET_RESOLUTION_WAIT_MINUTES = 180 

# --- FILTER CONFIGURATION ---
ALLOWED_LEAGUES_WITH_COUNTRY = [
    'Campeonato Brasileiro Série A', 'Segunda Division, Apertura', 
    'Copa do Brasil', 'Premier League'
]

EXCLUDED_COUNTRIES_OR_LEAGUES = [
    'USA', 'Poland', 'Mexico', 'Wales', 'Portugal', 'Denmark', 'Malta', 
    'Germany', 'Hungary', 'Sweden', 'Serbia', 'Switzerland', 'Cyprus', 
    'El Salvador', 'Lithuania', 'Honduras', 'Chile', 'Norway', 'England', 
    'England Amateur', 'Iceland', 'Seychelles', 'Hong Kong 2nd Division', 
    'Primera División Reserve, Apertura', 'U19 PAF Ligi', 'U17 CONCACAF Championship', 
    'Bosnia & Herzegovina', 'Italy Series D', 'Colombia', 'Jordan Reserve League', 
    'División Profesional', 'Mumbai Premier League', 'Serie C', '3. Liga'
]

AMATEUR_KEYWORDS = [
    'amateur', 'youth', 'reserves', 'friendly', 'u23', 'u21', 'u19', 'u17',
    'liga de reservas', 'division b', 'm-league', 'liga pro',
    'women', 'regional league', 'college', 'ncaa', 'promotion d’honneur'
]

# =========================================================
# 🟢 FIREBASE MANAGER (WITH STATE-LOCK & STAKING)
# =========================================================

class FirebaseManager:
    def __init__(self, credentials_json_string):
        self.db = None
        try:
            if not credentials_json_string: return
            cred_dict = json.loads(credentials_json_string)
            cred = credentials.Certificate(cred_dict)
            if not firebase_admin._apps:
                firebase_admin.initialize_app(cred)
            self.db = firestore.client()
            logger.info("Firebase initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {e}")

    def has_active_bet(self) -> bool:
        """STATE-LOCK: Checks if any bet is currently unresolved."""
        if not self.db: return False
        try:
            docs = self.db.collection('unresolved_bets').limit(1).get()
            return len(docs) > 0
        except Exception as e:
            logger.error(f"Error checking active bets: {e}")
            return False

    def get_last_resolved_bet(self):
        """Gets the most recent resolved bet to determine the next stake."""
        if not self.db: return None
        try:
            query = self.db.collection('resolved_bets').order_by(
                'resolution_timestamp', direction=firestore.Query.DESCENDING
            ).limit(1).get()
            for doc in query:
                return doc.to_dict()
            return None
        except Exception as e:
            logger.error(f"Error fetching last resolved bet: {e}")
            return None

    def is_bet_unresolved(self, match_id: str) -> bool:
        if not self.db: return False
        doc = self.db.collection('unresolved_bets').document(str(match_id)).get()
        return doc.exists

    def get_unresolved_bet_data(self, match_id: str):
        if not self.db: return None
        doc = self.db.collection('unresolved_bets').document(str(match_id)).get()
        return doc.to_dict() if doc.exists else None

    def add_unresolved_bet(self, match_id, data):
        if not self.db: return
        data['placed_at'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        self.db.collection('unresolved_bets').document(str(match_id)).set(data)

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
            logger.error(f"Firestore Error: {e}")
            return False

# =========================================================
# 🟢 STAKING LOGIC (DYNAMIC RECOVERY)
# =========================================================

def get_next_staking_params():
    """
    Calculates stake: $Stake = Original \times 2^{(Level-1)}$
    Returns: (stake_amount, match_sequence_number)
    """
    last_bet = firebase_manager.get_last_resolved_bet()
    
    if not last_bet or last_bet.get('outcome') == 'win':
        return ORIGINAL_STAKE, 1

    last_seq = last_bet.get('match_sequence', 1)
    
    if last_seq < MAX_CHASE_LEVEL:
        new_seq = last_seq + 1
        new_stake = ORIGINAL_STAKE * (2 ** (new_seq - 1))
        return float(new_stake), new_seq
    
    return ORIGINAL_STAKE, 1

# =========================================================
# 🏃 CORE LOGIC FUNCTIONS
# =========================================================

def send_telegram(msg):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'text': msg, 'parse_mode': 'Markdown'}, timeout=10)
        return True
    except Exception as e:
        logger.error(f"Telegram failed: {e}")
        return False

def place_regular_bet(state, fixture_id, score, match_info):
    """Handles Singleton Lock and Recovery Stake alert."""
    
    # 1. STATE-LOCK CHECK
    if firebase_manager.has_active_bet():
        if not state.get('lock_logged'):
            logger.info(f"State-Lock Active: Ignoring {match_info['match_name']}")
            state['lock_logged'] = True
        return

    if score in ['1-1', '2-2', '3-3']:
        # 2. CALCULATE STAKE
        stake, sequence = get_next_staking_params()

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
        
        type_label = "RECOVERY CHASE" if sequence > 1 else "INITIAL BET"
        message = (
            f"🎯 **{type_label} | Match {sequence}**\n"
            f"⏱️ **36' - {match_info['match_name']}**\n"
            f"🌍 {match_info['country']} | 🏆 {match_info['league_name']}\n"
            f"🔢 Current Score: **{score}**\n"
            f"💰 **Suggested Stake: ${stake:.22}**"
        )
        send_telegram(message)
        state['36_bet_placed'] = True
    else:
        state['36_bet_placed'] = True

def check_ht_result(state, fixture_id, score, match_info):
    unresolved_data = firebase_manager.get_unresolved_bet_data(fixture_id)
    if not unresolved_data: return

    outcome = 'win' if score == unresolved_data.get('36_score') else 'loss'
    emoji = "✅ WIN" if outcome == 'win' else "❌ LOSS"
    
    msg = (
        f"{emoji} **HT Result: {match_info['match_name']}**\n"
        f"🔢 HT Score: **{score}**\n"
        f"🔓 *State Unlocked for next alert.*"
    )
    
    if firebase_manager.move_to_resolved(fixture_id, unresolved_data, outcome):
        send_telegram(msg)
        if fixture_id in LOCAL_TRACKED_MATCHES:
            del LOCAL_TRACKED_MATCHES[fixture_id]

def process_live_match(match):
    fixture_id = str(match.id)
    league_name = match.tournament.name
    category_name = match.tournament.category.name
    full_text = f"{league_name} {category_name}".lower()

    # Filtering Hierarchy
    is_allowed = any(k.lower() in league_name.lower() for k in ALLOWED_LEAGUES_WITH_COUNTRY)
    if not is_allowed:
        if any(k.lower() in full_text for k in EXCLUDED_COUNTRIES_OR_LEAGUES): return
        if any(k.lower() in full_text for k in AMATEUR_KEYWORDS): return

    minute = match.total_elapsed_minutes 
    status_desc = match.status.description.upper()
    status = '1H' if '1ST' in status_desc else STATUS_HALFTIME if 'HALFTIME' in status_desc else 'FT'
    score = f"{match.home_score.current}-{match.away_score.current}"

    state = LOCAL_TRACKED_MATCHES.get(fixture_id) or {'36_bet_placed': False, 'lock_logged': False}
    LOCAL_TRACKED_MATCHES[fixture_id] = state

    match_info = {'match_name': f"{match.home_team.name} vs {match.away_team.name}", 
                  'league_name': league_name, 'country': category_name}

    if status == '1H' and minute in MINUTES_REGULAR_BET and not state['36_bet_placed']:
        place_regular_bet(state, fixture_id, score, match_info)
    elif status == STATUS_HALFTIME and firebase_manager.is_bet_unresolved(fixture_id):
        check_ht_result(state, fixture_id, score, match_info)

# =========================================================
# ⚙️ INITIALIZATION
# =========================================================

def initialize_bot_services():
    global firebase_manager, SOFASCORE_CLIENT
    firebase_manager = FirebaseManager(FIREBASE_CREDENTIALS_JSON_STRING)
    try:
        SOFASCORE_CLIENT = SofascoreClient()
        SOFASCORE_CLIENT.initialize()
        return True
    except Exception as e:
        logger.critical(f"Client Init Error: {e}")
        return False

def shutdown_bot():
    if SOFASCORE_CLIENT:
        SOFASCORE_CLIENT.close()

def run_bot_cycle():
    if not SOFASCORE_CLIENT: return
    try:
        live_matches = SOFASCORE_CLIENT.get_events(live=True)
        for match in live_matches:
            process_live_match(match)
    except Exception as e:
        logger.error(f"Cycle Error: {e}")
