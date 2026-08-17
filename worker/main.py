# worker/main.py
"""
Orchestration supervisor engine managing thread execution,
health assertions, signal traps, and Prometheus telemetry metrics exposition.
INTEGRATED WITH: Dynamic Percentage Staking Engine (10, 15, 25, 40, 60, 90)
"""

import time
import signal
import sys
import os
import logging
from prometheus_client import start_http_server

# Import core loop routines and internal application memory states
from bot import (
    run_bot_cycle,
    SLEEP_TIME,
    initialize_bot_services,
    shutdown_bot,
    send_telegram,
    LOCAL_TRACKED_MATCHES,
    # NEW: Staking engine imports
    set_staking_engine,
    get_staking_engine,
    get_staking_stats,
    get_staking_status_message,
    enable_staking,
    reset_staking_engine,
    STAKE_SEQUENCE,
)

# Import the Staking Engine
from staking_engine import StakingEngine

# Import shared metric counters to expose and manipulate state updates
from metrics import CYCLE_COUNTER, MATCHES_TRACKED_GAUGE, API_FAILURES

# Setup isolated logger namespace for supervisor context tracking
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    handlers=[logging.FileHandler("bot_activity.log"), logging.StreamHandler()]
)
logger = logging.getLogger("BetBot.Supervisor")

# --- CONSTRAINTS ---
WATCHDOG_LIMIT = 300
REBOOT_LIMIT = 86400
HEARTBEAT_LIMIT = 3600
STATUS_UPDATE_INTERVAL = 30  # Send staking status every 30 cycles
METRICS_PORT = int(os.getenv("PORT", 8000))

RUNNING = True
LAST_REBOOT = time.time()
LAST_HEARTBEAT = time.time()
CYCLE_COUNT = 0

# ============================================================
# GLOBAL STAKING ENGINE
# ============================================================
staking_engine = None

# Constants for staking engine configuration (matches staking_engine internal values)
MAX_CONSECUTIVE_LOSSES = 3  # This matches the internal value in StakingEngine

# --------------------------------------------------
# SIGNAL TRAP HANDLERS
# --------------------------------------------------
def handle_shutdown_signal(signum, frame):
    global RUNNING
    logger.warning(f"⚠️ OS Termination interrupt captured ({signum}). Setting loop exit parameters...")
    RUNNING = False

# --------------------------------------------------
# STAKING ENGINE STATUS REPORTING
# --------------------------------------------------
def send_staking_status():
    """Send a status update about the staking engine via Telegram."""
    if staking_engine:
        status_msg = staking_engine.get_status_message()
        send_telegram(status_msg)
    else:
        send_telegram("⚠️ Staking engine not initialized.")

def send_enhanced_heartbeat():
    """Send an enhanced heartbeat with staking statistics."""
    if staking_engine:
        stats = staking_engine.get_stats()
        heartbeat_msg = (
            f"💓 **Heartbeat Pulse:**\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 Cached Matches: {len(LOCAL_TRACKED_MATCHES)}\n"
            f"💰 Current Stake: {stats['current_stake']}\n"
            f"📈 Step: {stats['current_step']+1}/{len(STAKE_SEQUENCE)}\n"
            f"✅ Wins: {stats['total_wins']}\n"
            f"❌ Losses: {stats['total_losses']}\n"
            f"📊 Win Rate: {stats['win_rate']}\n"
            f"📈 Profit: {stats['total_profit']}\n"
            f"💰 Bankroll: {stats['current_bankroll']}\n"
            f"🔥 Streak: {stats['current_streak']}\n"
            f"⏸️ Paused: {stats['is_paused']}\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔄 {staking_engine.get_current_step_display()}"
        )
        send_telegram(heartbeat_msg)
    else:
        send_telegram(f"💓 **Heartbeat Pulse:** Bot Status: Active\n📊 Cached Matches: {len(LOCAL_TRACKED_MATCHES)}")

# --------------------------------------------------
# SYSTEM RESTORATION ROUTINES
# --------------------------------------------------
def execute_safe_recovery_handshake() -> bool:
    logger.warning("🔄 Initiating service recovery loop execution...")
    send_telegram("⚠️ Supervisor Core: Initiating automatic service layer recovery sequence...")
    API_FAILURES.inc()

    try:
        shutdown_bot()
    except Exception as e:
        logger.error(f"Error dropping active services during recovery context: {e}")

    retry_count = 0
    while RUNNING:
        retry_count += 1
        logger.info(f"Attempting full platform re-mount sequence step #{retry_count}...")
        if initialize_bot_services():
            logger.info("✅ Platform modules successfully recovered.")
            send_telegram("✅ Supervisor Core: Service recovery completed. Bot is back online.")

            # Re-attach staking engine after recovery
            if staking_engine:
                set_staking_engine(staking_engine)
                logger.info(f"📊 Staking engine re-attached: {staking_engine.get_current_step_display()}")

            return True
        time.sleep(30)
    return False

def can_safely_reboot() -> bool:
    if not LOCAL_TRACKED_MATCHES:
        return True
    active_matches = [fid for fid, s in LOCAL_TRACKED_MATCHES.items() if s.get('active', False)]
    return len(active_matches) == 0

# --------------------------------------------------
# APPLICATION RUNTIME ORCHESTRATION ENTRY
# --------------------------------------------------
def main():
    global RUNNING, LAST_REBOOT, LAST_HEARTBEAT, CYCLE_COUNT, staking_engine

    logger.info(f"🚀 INITIALIZING SUPERVISOR MANAGER ASSET PROCESS. PID={os.getpid()}")

    # ============================================================
    # INITIALIZE STAKING ENGINE
    # ============================================================
    initial_bankroll = float(os.getenv("INITIAL_BANKROLL", "1000"))
    staking_engine = StakingEngine(initial_bankroll)
    set_staking_engine(staking_engine)

    logger.info(f"📊 Dynamic Percentage Staking Engine loaded.")
    logger.info(f"📊 Sequence: {STAKE_SEQUENCE}")
    logger.info(f"💰 Initial Bankroll: ${initial_bankroll:.2f}")
    # FIXED: Use the constant MAX_CONSECUTIVE_LOSSES instead of accessing staking_engine attribute
    logger.info(f"⚠️ Pause after {MAX_CONSECUTIVE_LOSSES} consecutive losses.")

    # Attach kernel operational interrupt triggers
    signal.signal(signal.SIGINT, handle_shutdown_signal)
    signal.signal(signal.SIGTERM, handle_shutdown_signal)

    # 📊 START THE PROMETHEUS METRICS ENDPOINT SERVER
    try:
        start_http_server(METRICS_PORT)
        logger.info(f"📊 Prometheus telemetry instrumentation pipeline online at port :{METRICS_PORT}/metrics")
    except Exception as metrics_ex:
        logger.critical(f"💥 Failed to lock Prometheus HTTP socket port allocation: {metrics_ex}")

    # Core Startup Routine
    if not initialize_bot_services():
        logger.critical("💥 Initial core component initialization failed! Terminating Supervisor process.")
        sys.exit(1)

    # Send startup messages
    send_telegram(
        "🚀 **BetBot Daemon Supervisor Online**\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "📊 **Dynamic Percentage Staking Engine Active**\n"
        f"🔄 Sequence: {' → '.join('$'+str(s) for s in STAKE_SEQUENCE)}\n"
        f"💰 Initial Bankroll: ${initial_bankroll:.2f}\n"
        # FIXED: Use the constant MAX_CONSECUTIVE_LOSSES
        f"⚠️ Safety: Pause after {MAX_CONSECUTIVE_LOSSES} consecutive losses.\n"
        "━━━━━━━━━━━━━━━━━━━━━"
    )

    # Send initial staking status
    time.sleep(2)
    send_staking_status()

    # Main loop
    while RUNNING:
        cycle_start_time = time.time()
        CYCLE_COUNTER.inc()
        CYCLE_COUNT += 1

        try:
            # Execute business logic queries
            run_bot_cycle()

            # Push live cache data structure updates to Prometheus Gauge
            MATCHES_TRACKED_GAUGE.set(len(LOCAL_TRACKED_MATCHES))

            # Watchdog Execution Time Limit Assertion
            elapsed_cycle_time = time.time() - cycle_start_time
            if elapsed_cycle_time > WATCHDOG_LIMIT:
                logger.error(f"🚨 Watchdog breached: Process execution took {elapsed_cycle_time:.2f}s.")
                if not execute_safe_recovery_handshake():
                    break

            # Smart Maintenance Window Assertion
            if time.time() - LAST_REBOOT > REBOOT_LIMIT:
                if can_safely_reboot():
                    logger.warning("Scheduled maintenance window verified open. Executing restart execution pass...")
                    if execute_safe_recovery_handshake():
                        LAST_REBOOT = time.time()
                else:
                    LAST_REBOOT += 300  # Shift evaluation window forward 5 minutes

            # Enhanced Telegram Heartbeat Status Update
            if time.time() - LAST_HEARTBEAT > HEARTBEAT_LIMIT:
                send_enhanced_heartbeat()
                LAST_HEARTBEAT = time.time()

            # Send staking status update every STATUS_UPDATE_INTERVAL cycles
            if CYCLE_COUNT % STATUS_UPDATE_INTERVAL == 0:
                send_staking_status()

        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received. Shutting down...")
            RUNNING = False
            break

        except Exception as e:
            logger.error(f"💥 Top level supervisor loop runtime exception failure: {e}", exc_info=True)
            API_FAILURES.inc()
            time.sleep(15)

        finally:
            if RUNNING:
                # Calculate processing execution latency to keep loop sleep iterations perfectly consistent
                execution_latency = time.time() - cycle_start_time
                dynamic_sleep = max(1.0, SLEEP_TIME - execution_latency)
                time.sleep(dynamic_sleep)

    # ============================================================
    # CLEAN EXIT PATH
    # ============================================================
    logger.warning("🛑 Closing application loops. Freeing structural process parameters...")

    # Send final staking summary
    if staking_engine:
        final_msg = staking_engine.get_status_message()
        final_msg = f"🛑 **Bot Shutdown - Final Summary**\n{final_msg}"
        send_telegram(final_msg)

    try:
        shutdown_bot()
    except Exception as e:
        logger.error(f"Error handling system breakdown operations: {e}")

    send_telegram("🛑 **BetBot Daemon Supervisor Offline**")
    logger.info("🛑 Bot shutdown complete.")


if __name__ == "__main__":
    main()
