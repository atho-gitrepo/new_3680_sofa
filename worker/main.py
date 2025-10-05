# main.py

import time
from datetime import datetime
import logging
import sys
# Import the run function, the sleep time constant, and the initialization function
from bot import run_bot_once, SLEEP_TIME, initialize_bot_services

# Use a separate logger for the executor
logger = logging.getLogger("MainExecutor")
# Set level for console output
logger.setLevel(logging.INFO)

# Use the interval defined in the bot logic file
CHECK_INTERVAL = SLEEP_TIME

def main():
    print("🚀 Football Betting Bot Executor Started")
    
    # 1. ONE-TIME SERVICE INITIALIZATION (CRITICAL)
    if not initialize_bot_services():
        # Initialization function logs the error internally.
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ❌ FATAL: Bot services failed to initialize. Check bot.log. Exiting.")
        sys.exit(1) # Exit immediately if initialization fails
    
    # 2. MAIN EXECUTION LOOP
    while True:
        try:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🤖 Starting bot cycle...")
            # Call the core logic function from bot.py
            run_bot_once()
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✅ Cycle complete.")
            
        except Exception as e:
            # Catch unexpected errors during the cycle that run_bot_once didn't handle
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ⚠️ UNEXPECTED CRITICAL ERROR in main loop: {e}")
            logger.critical(f"Unexpected error in cycle: {e}", exc_info=True)
            
        finally:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 💤 Sleeping for {CHECK_INTERVAL} seconds...\n")
            time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
