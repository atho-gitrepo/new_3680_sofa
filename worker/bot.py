import requests
import os
import json
import time
import logging
from datetime import datetime, timedelta
import firebase_admin
from firebase_admin import credentials, firestore
from esd.sofascore import SofascoreClient, EntityType

# ================= GLOBALS =================
SOFASCORE_CLIENT = None
firebase_manager = None
LOCAL_TRACKED_MATCHES = {}

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("FootballBettingBot")

API_KEY = os.getenv("API_KEY", "DUMMY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "DUMMY")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "DUMMY")
FIREBASE_CREDENTIALS_JSON_STRING = os.getenv("FIREBASE_CREDENTIALS_JSON", "")

SLEEP_TIME = 60
MINUTES_REGULAR_BET = [36, 37]
BET_TYPE_REGULAR = "regular"
STATUS_LIVE = ['LIVE', '1H', '2H', 'ET', 'P']
STATUS_HALFTIME = 'HT'
STATUS_FINISHED = ['FT', 'AET', 'PEN']

# ================= FIREBASE =================

class FirebaseManager:
    def __init__(self, credentials_json_string):
        self.db = None
        self._unresolved_bets_cache = {}

        if not credentials_json_string:
            logger.warning("Firebase disabled.")
            return

        cred = credentials.Certificate(json.loads(credentials_json_string))
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
        self.db = firestore.client()
        logger.info("Firebase initialized")

    # -------- GLOBAL LOCK --------
    def has_any_unresolved_bet(self) -> bool:
        if not self.db:
            return False
        try:
            docs = self.db.collection('unresolved_bets').limit(1).get()
            return len(docs) > 0
        except Exception as e:
            logger.error(f"has_any_unresolved_bet error: {e}")
            return False

    # -------- PER MATCH --------
    def is_bet_unresolved(self, match_id):
        if not self.db:
            return False
        match_id = str(match_id)

        if match_id in self._unresolved_bets_cache:
            return True

        doc = self.db.collection('unresolved_bets').document(match_id).get()
        if doc.exists:
            self._unresolved_bets_cache[match_id] = doc.to_dict()
            return True
        return False

    def get_unresolved_bet_data(self, match_id):
        if not self.db:
            return None
        match_id = str(match_id)

        if match_id in self._unresolved_bets_cache:
            return self._unresolved_bets_cache[match_id]

        doc = self.db.collection('unresolved_bets').document(match_id).get()
        if doc.exists:
            self._unresolved_bets_cache[match_id] = doc.to_dict()
            return doc.to_dict()
        return None

    def add_unresolved_bet(self, match_id, data):
        if not self.db:
            return
        match_id = str(match_id)
        data['placed_at'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        self.db.collection('unresolved_bets').document(match_id).set(data)
        self._unresolved_bets_cache[match_id] = data

    def move_to_resolved(self, match_id, bet_info, outcome):
        if not self.db:
            return False
        match_id = str(match_id)
        bet_info['outcome'] = outcome
        bet_info['resolved_at'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        self.db.collection('resolved_bets').document(match_id).set(bet_info)
        self.db.collection('unresolved_bets').document(match_id).delete()
        self._unresolved_bets_cache.pop(match_id, None)
        return True


# ================= INIT =================

def initialize_services():
    global firebase_manager, SOFASCORE_CLIENT

    firebase_manager = FirebaseManager(FIREBASE_CREDENTIALS_JSON_STRING)

    SOFASCORE_CLIENT = SofascoreClient()
    SOFASCORE_CLIENT.initialize()

    send_telegram("🚀 Bot started")
    return True


# ================= TELEGRAM =================

def send_telegram(msg):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}
    )


# ================= CORE LOGIC =================

def place_regular_bet(state, fixture_id, score, match_info):
    # 🔒 GLOBAL LOCK
    if firebase_manager.has_any_unresolved_bet():
        logger.info(f"GLOBAL LOCK: skipping {fixture_id}")
        state['36_bet_placed'] = True
        LOCAL_TRACKED_MATCHES[fixture_id] = state
        return

    # Per-match safety
    if firebase_manager.is_bet_unresolved(fixture_id):
        state['36_bet_placed'] = True
        LOCAL_TRACKED_MATCHES[fixture_id] = state
        return

    if score in ['1-1', '2-2', '3-3']:
        state['36_bet_placed'] = True
        state['36_score'] = score
        LOCAL_TRACKED_MATCHES[fixture_id] = state

        firebase_manager.add_unresolved_bet(fixture_id, {
            "match_name": match_info['match_name'],
            "league": match_info['league'],
            "country": match_info['country'],
            "bet_type": BET_TYPE_REGULAR,
            "36_score": score,
            "fixture_id": fixture_id
        })

        send_telegram(
            f"⏱️ **36' ALERT**\n"
            f"{match_info['match_name']}\n"
            f"🏆 {match_info['league']} | 🌍 {match_info['country']}\n"
            f"🔢 Score: {score}"
        )


def check_ht_result(state, fixture_id, score, match_info):
    bet = firebase_manager.get_unresolved_bet_data(fixture_id)
    if not bet:
        return

    outcome = "win" if score == bet.get("36_score") else "loss"

    firebase_manager.move_to_resolved(fixture_id, bet, outcome)

    send_telegram(
        f"📊 **HT RESULT**\n"
        f"{match_info['match_name']}\n"
        f"HT Score: {score}\n"
        f"Result: {'✅ WIN' if outcome == 'win' else '❌ LOSS'}"
    )

    LOCAL_TRACKED_MATCHES.pop(fixture_id, None)


def process_live_match(match):
    fixture_id = str(match.id)
    minute = match.total_elapsed_minutes
    status = match.status.description.upper()

    if fixture_id not in LOCAL_TRACKED_MATCHES:
        LOCAL_TRACKED_MATCHES[fixture_id] = {'36_bet_placed': False}

    state = LOCAL_TRACKED_MATCHES[fixture_id]

    score = f"{match.home_score.current}-{match.away_score.current}"
    match_info = {
        "match_name": f"{match.home_team.name} vs {match.away_team.name}",
        "league": match.tournament.name,
        "country": match.tournament.category.name
    }

    if status == '1ST HALF' and minute in MINUTES_REGULAR_BET and not state['36_bet_placed']:
        place_regular_bet(state, fixture_id, score, match_info)

    if status == 'HALFTIME':
        check_ht_result(state, fixture_id, score, match_info)


def run_cycle():
    matches = SOFASCORE_CLIENT.get_events(live=True)
    for match in matches:
        process_live_match(match)


# ================= MAIN =================

if __name__ == "__main__":
    if initialize_services():
        while True:
            run_cycle()
            time.sleep(SLEEP_TIME)