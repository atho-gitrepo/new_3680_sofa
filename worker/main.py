# main.py
# The primary execution and loop control for the Football Betting Bot with GRACEFUL SHUTDOWN.

import time
import signal
import sys
import logging
from datetime import datetime
# Import all necessary functions and constants from the bot logic file
from bot import run_bot_cycle, SLEEP_TIME, initialize_bot_services, shutdown_bot

# Set up logger for the executor
logger = logging.getLogger("MainExecutor")
logger.setLevel(logging.INFO)

# Global flag to control the loop and signal shutdown
RUNNING = True
CHECK_INTERVAL = SLEEP_TIME

def signal_handler(signum, frame):
    """
    Handles OS signals (like SIGTERM from Railway) for graceful shutdown.
    Sets the global RUNNING flag to False to break the main loop.
    """
    global RUNNING
    logger.warning(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Signal {signum} received. Initiating graceful shutdown...")
    RUNNING = False

def main():
    """
    Initializes services, runs the main bot loop, and ensures resource cleanup.
    """
    print("🚀 Football Betting Bot Executor Started")
    
    # 1. Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler) # OS/Container stop signal (CRITICAL for Playwright cleanup)
    
    # 2. ONE-TIME SERVICE INITIALIZATION
    if not initialize_bot_services():
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ❌ FATAL: Bot services failed to initialize. Exiting.")
        sys.exit(1)
    
    # 3. MAIN EXECUTION LOOP
    while RUNNING:
        try:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🤖 Starting bot cycle...")
            # Using the revised run_bot_cycle which is safer than run_bot_once
            run_bot_cycle() 
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✅ Cycle complete.")
            
        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ⚠️ UNEXPECTED CRITICAL ERROR in main loop: {e}")
            logger.critical(f"Unexpected error in cycle: {e}", exc_info=True)
            
        finally:
            if RUNNING: 
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 💤 Sleeping for {CHECK_INTERVAL} seconds...\n")
                time.sleep(CHECK_INTERVAL)

    # 4. GRACEFUL SHUTDOWN
    logger.info(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Shutting down bot resources...")
    shutdown_bot()
    logger.info(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Bot successfully shut down.")
    sys.exit(0)

if __name__ == "__main__":
    main()
