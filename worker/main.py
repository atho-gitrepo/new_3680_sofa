from bot import run_bot_once, SLEEP_TIME
import time
from datetime import datetime
import logging

# Set up logging for the main executor (optional, but good practice)
logger = logging.getLogger("MainExecutor")

# Use the interval defined in the bot logic file
CHECK_INTERVAL = SLEEP_TIME

def main():
    print("🚀 Football Betting Bot Executor Started")

    while True:
        try:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🤖 Starting bot cycle...")
            run_bot_once()
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✅ Cycle complete.")
            
        except Exception as e:
            # Use the logger defined in the bot or a local print for critical error
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ❌ CRITICAL ERROR in main loop: {e}")
            
        finally:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 💤 Sleeping for {CHECK_INTERVAL} seconds...\n")
            time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
