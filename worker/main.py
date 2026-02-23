import time
import signal
import sys
import logging
from datetime import datetime
from bot import run_bot_cycle, SLEEP_TIME, initialize_bot_services, shutdown_bot

logger = logging.getLogger("MainExecutor")
logger.setLevel(logging.INFO)

RUNNING = True
CHECK_INTERVAL = SLEEP_TIME

def signal_handler(signum, frame):
    global RUNNING
    logger.warning(f"[{datetime.now()}] Signal {signum} received. Initiating graceful shutdown...")
    RUNNING = False

def main():
    print("🚀 Football Betting Bot Executor Started")
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    if not initialize_bot_services():
        print(f"[{datetime.now()}] ❌ FATAL: Bot services failed to initialize.")
        sys.exit(1)
    
    while RUNNING:
        try:
            print(f"[{datetime.now()}] 🤖 Starting bot cycle...")
            run_bot_cycle() 
            print(f"[{datetime.now()}] ✅ Cycle complete.")
            
        except Exception as e:
            print(f"[{datetime.now()}] ⚠️ ERROR: {e}")
            logger.critical(f"Unexpected error: {e}", exc_info=True)
            
        finally:
            if RUNNING: 
                print(f"[{datetime.now()}] 💤 Sleeping for {CHECK_INTERVAL} seconds...\n")
                time.sleep(CHECK_INTERVAL)

    logger.info("Shutting down bot resources...")
    shutdown_bot()
    sys.exit(0)

if __name__ == "__main__":
    main()

