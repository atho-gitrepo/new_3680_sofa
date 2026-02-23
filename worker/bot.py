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
    handlers=[logging.FileHandler("bot_detailed.log"), logging.StreamHandler()]
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
# 🟢 FIREBASE MANAGER
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
            logger.info("✅ Firebase initialized.")
        except Exception as e:
            logger.error(f"❌ Firebase Init Failed: {e}", exc_info=True)

    def is_state_locked(self) -> bool:
        if not self.db: return False
        try:
            docs = self.db.collection('unresolved_bets').limit(1).get()
            return len(docs) > 0
        except: return False

    def is_bet_unresolved(self, match_id: str) -> bool:
        if not self.db: return False
        try:
            doc = self.db.collection('unresolved_bets').document(str(match_id)).get()
            return doc.exists
        except: return False

    def get_last_resolved_bet(self):
        if not self.db: return None
        try:
            query = self.db.collection('resolved_bets').order_by(
                'resolution_timestamp', direction=firestore.Query.DESCENDING
            ).limit(1).get()
            for doc in query: return doc.to_dict()
            return None
        except: return None

    def get_unresolved_bet_data(self, match_id: str):
        if not self.db: return None
        try:
            doc = self.db.collection('unresolved_bets').document(str(match_id)).get()
            return doc.to_dict() if doc.exists else None
        except: return None

    def add_unresolved_bet(self, match_id, data):
        if not self.db: return
        try:
            data['placed_at'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            self.db.collection('unresolved_bets').document(str(match_id)).set(data)
        except Exception as e: logger.error(f"Error adding bet: {e}")

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
        except Exception as e: logger.error(f"Error resolving: {e}"); return False

# =========================================================
# 🟢 BOT LOGIC
# =========================================================

def calculate_next_stake():
    last_bet = firebase_manager.get_last_resolved_bet()
    if not last_bet or last_bet.get('outcome') == 'win':
        return ORIGINAL_STAKE, 1
    
    last_seq = last_bet.get('match_sequence', 1)
    if last_seq < MAX_CHASE_LEVEL:
        new_seq = last_seq + 1
        new_stake = ORIGINAL_STAKE * (2 ** (new_seq - 1))
        return float(new_stake), new_seq
    return ORIGINAL_STAKE, 1

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        r = requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'text': msg, 'parse_mode': 'Markdown'}, timeout=10)
        return r.status_code == 200
    except: return False

def place_regular_bet(state, fixture_id, score, match_info):
    if firebase_manager.is_state_locked():
        if not state.get('lock_logged'):
            logger.warning(f"🚫 LOCKED: Skipping {match_info['match_name']}")
            state['lock_logged'] = True
        return

    if score in ['1-1', '2-2', '3-3']:
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
        label = "RECOVERY" if sequence > 1 else "INITIAL"
        msg = f"🎯 **{label} | Match {sequence}**\n⏱️ **36' - {match_info['match_name']}**\n🔢 Score: **{score}**\n💰 **Stake: ${stake:.2f}**"
        send_telegram(msg)
        state['36_bet_placed'] = True
    else:
        state['36_bet_placed'] = True

def check_ht_result(state, fixture_id, score, match_info):
    unresolved_data = firebase_manager.get_unresolved_bet_data(fixture_id)
    if not unresolved_data: return
    target = unresolved_data.get('36_score')
    outcome = 'win' if score == target else 'loss'
    emoji = "✅ WIN" if outcome == 'win' else "❌ LOSS"
    if firebase_manager.move_to_resolved(fixture_id, unresolved_data, outcome):
        send_telegram(f"{emoji} **HT: {match_info['match_name']}**\n🔢 HT Score: **{score}**\n🔓 System Unlocked.")
        if fixture_id in LOCAL_TRACKED_MATCHES: del LOCAL_TRACKED_MATCHES[fixture_id]

def process_live_match(match):
    fixture_id = str(match.id)
    league_name = match.tournament.name
    category_name = match.tournament.category.name
    full_text = f"{league_name} {category_name}".lower()

    if not any(k.lower() in league_name.lower() for k in ALLOWED_LEAGUES):
        if any(k.lower() in full_text for k in EXCLUDED_LEAGUES + AMATEUR_KEYWORDS): return

    minute = match.total_elapsed_minutes 
    status_desc = match.status.description.upper()
    status = '1H' if '1ST' in status_desc else STATUS_HALFTIME if 'HALFTIME' in status_desc else 'OTHER'
    score = f"{match.home_score.current}-{match.away_score.current}"

    state = LOCAL_TRACKED_MATCHES.get(fixture_id) or {'36_bet_placed': False, 'lock_logged': False}
    LOCAL_TRACKED_MATCHES[fixture_id] = state

    match_info = {'match_name': f"{match.home_team.name} vs {match.away_team.name}", 
                  'league_name': league_name, 'country': category_name}

    if status == '1H' and minute in MINUTES_REGULAR_BET and not state['36_bet_placed']:
        place_regular_bet(state, fixture_id, score, match_info)
    elif status == STATUS_HALFTIME and firebase_manager.is_bet_unresolved(fixture_id):
        check_ht_result(state, fixture_id, score, match_info)

def initialize_bot_services():
    global firebase_manager, SOFASCORE_CLIENT
    firebase_manager = FirebaseManager(FIREBASE_CREDENTIALS_JSON_STRING)
    try:
        SOFASCORE_CLIENT = SofascoreClient()
        SOFASCORE_CLIENT.initialize()
        return True
    except: return False

def shutdown_bot():
    if SOFASCORE_CLIENT: SOFASCORE_CLIENT.close()

def run_bot_cycle():
    if not SOFASCORE_CLIENT: return
    try:
        live_matches = SOFASCORE_CLIENT.get_events(live=True)
        for match in live_matches: process_live_match(match)
    except Exception as e: logger.error(f"Cycle Error: {e}")
