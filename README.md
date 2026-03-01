⚽ BetBot Pro: Automated Live-Sports Martingale Engine
BetBot Pro is a high-performance, automated betting bot designed to execute a specific "Minute 36" strategy using real-time data from Sofascore. It leverages a cloud-synced Martingale (Chase) system to manage stakes and maximize recovery.
🚀 Key Features
 * Real-Time Analytics: Integrates with SofascoreClient to monitor live match stats, scores, and elapsed time with sub-minute latency.
 * The "Minute 36" Strategy: Automatically triggers bets when specific scoreline conditions are met during the critical 36'-37' window of the first half.
 * Intelligent Martingale Engine: Features a built-in MAX_CHASE_LEVEL logic. If a bet loses, the bot automatically calculates the recovery stake for the next match, scaling up to 4 levels (2^n scaling).
 * Cloud State Management: Powered by Google Firebase. The bot maintains a "Global Lock" state, ensuring it never places overlapping bets and keeps your bankroll protected.
 * Instant Telegram Alerts: Get real-time push notifications for every bet placed, HT results, and win/loss outcomes directly to your phone.
 * Advanced League Filtering: Pre-configured with "Safe Leagues" (Série A, Premier League) and an "Amateur Filter" to avoid high-risk youth or friendly matches.
🛠 Technical Architecture
The bot is built for 24/7 uptime and data integrity:
| Component | Description |
|---|---|
| Data Source | Sofascore API (Live match events & status) |
| Database | Firestore (Tracks unresolved_bets vs resolved_bets) |
| Logic | Python-based state machine with logging for audit trails |
| Notification | Telegram Bot API (Markdown formatted alerts) |
📋 Strategy Logic
The bot follows a strict professional betting protocol:
 * Scan: Monitors live matches in ALLOWED_LEAGUES.
 * Filter: Excludes matches containing keywords like u19, reserves, or friendly.
 * Trigger: At Minute 36, if the score is a draw (e.g., 1-1, 2-2), it initiates a "Regular Bet."
 * Chase: If the result doesn't hold at Half Time (HT), the bot prepares a Level 2 stake for the next qualifying match.
⚙️ Configuration & Setup
1. Environment Variables
Secure your bot by setting the following environment variables:
export TELEGRAM_TOKEN="your_bot_token"
export TELEGRAM_CHAT_ID="your_chat_id"
export FIREBASE_CREDENTIALS_JSON='{"your": "firebase_json"}'

2. Customizing Filters
You can easily modify ALLOWED_LEAGUES and MAX_CHASE_LEVEL in the settings section of the code to match your risk appetite.
# Default Settings
ORIGINAL_STAKE = 10.0
MAX_CHASE_LEVEL = 4

📈 Commercial Potential
This bot is a "Plug-and-Play" solution for:
 * Betting Syndicate Owners: Scalable architecture to manage multiple accounts.
 * SaaS Developers: Use this as a backend for a "Betting Signals" subscription service.
 * Algorithmic Traders: A foundation for more complex Poisson distribution or Expected Goals (xG) models.
⚠️ Disclaimer
Calculated risk is still risk. This software is for educational and entertainment purposes. Always test your strategies with "paper money" before committing real capital. The developers are not responsible for financial losses.
Interested in a custom integration or the Pro version?
[Contact Me / Open an Issue]
