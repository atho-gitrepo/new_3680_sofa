# main.py

import time
from datetime import datetime
import logging
import sys
# Import the run function, the sleep time constant, and the initialization function
from bot import run_bot_once, SLEEP_TIME, initialize_bot_services

# Use a separate logger for the executor
logger = logging.getLogger("MainExecutor")
logger.setLevel(logging.INFO)

# Use the interval defined in the bot logic file
CHECK_INTERVAL = SLEEP_TIME

def main():
    print("🚀 Football Betting Bot Executor Started")
    
    # 1. CRITICAL STEP: ONE-TIME SERVICE INITIALIZATION
    # This must be done before the while loop!
    if not initialize_bot_services():
        # This block executes if Firebase or Sofascore failed to set up.
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ❌ FATAL: Bot services failed to initialize. Check bot.log for details. Exiting.")
        sys.exit(1) 
    
    # 2. MAIN EXECUTION LOOP
    while True:
        try:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🤖 Starting bot cycle...")
            run_bot_once()
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✅ Cycle complete.")
            
        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ⚠️ UNEXPECTED CRITICAL ERROR in main loop: {e}")
            logger.critical(f"Unexpected error in cycle: {e}", exc_info=True)
            
        finally:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 💤 Sleeping for {CHECK_INTERVAL} seconds...\n")
            time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
