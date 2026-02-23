import time
import signal
import sys
import logging
from datetime import datetime
from bot import run_bot_cycle, SLEEP_TIME, initialize_bot_services, shutdown_bot, send_telegram

logger = logging.getLogger("MainExecutor")
logger.setLevel(logging.INFO)

RUNNING = True
CHECK_INTERVAL = SLEEP_TIME
LAST_HEARTBEAT = 0
HEARTBEAT_INTERVAL = 1800

def signal_handler(signum, frame):
    global RUNNING
    logger.warning(f"[{datetime.now()}] Signal {signum} received. Initiating shutdown...")
    RUNNING = False

def main():
    global LAST_HEARTBEAT
    print("🚀 Football Betting Bot Executor Started")
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    if not initialize_bot_services():
        print(f"[{datetime.now()}] ❌ FATAL: Bot services failed to initialize.")
        sys.exit(1)
    
    send_telegram("🚀 **Bot Online & Monitoring**\nSystem initialized. State-Lock and Martingale Recovery active.")
    
    while RUNNING:
        try:
            run_bot_cycle() 
            
            current_time = time.time()
            if current_time - LAST_HEARTBEAT > HEARTBEAT_INTERVAL:
                send_telegram("💓 **Heartbeat**: Bot is actively scanning live matches...")
                LAST_HEARTBEAT = current_time
            
        except Exception as e:
            logger.critical(f"Unexpected error: {e}", exc_info=True)
            
        finally:
            if RUNNING: time.sleep(CHECK_INTERVAL)

    send_telegram("🛑 **Bot Offline**: System shutting down.")
    shutdown_bot()
    sys.exit(0)

if __name__ == "__main__":
    main()
