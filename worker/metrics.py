# metrics.py
"""
Central telemetry registry for Prometheus tracking.
Isolated to prevent circular import locks between main.py and bot.py.
"""
from prometheus_client import Counter, Gauge

# --- CORE TELEMETRY METRICS ---
CYCLE_COUNTER = Counter(
    "betbot_execution_cycles_total", 
    "Total number of supervisor monitoring cycles run"
)

MATCHES_TRACKED_GAUGE = Gauge(
    "betbot_tracked_matches_active", 
    "Current number of matches monitored in cache memory"
)

API_FAILURES = Counter(
    "betbot_api_requests_failed_total", 
    "Total number of network scrape exceptions or timeouts caught"
)

STATE_LOCKS = Counter(
    "betbot_state_lock_rejections_total", 
    "Total evaluations skipped due to an active Firestore DB sequence lock"
)

BET_TRIGGERS = Counter(
    "betbot_wagers_placed_total", 
    "Total bet placements successfully dispatched to the database engine"
)