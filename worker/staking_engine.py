# worker/staking_engine.py
"""
Dynamic Percentage Staking Engine
================================
Sequence: $10 → $20 → $30
Resets to $10 on any loss.
Pauses for 1 hour after 3 consecutive losses.

This module manages the staking state machine for the LSB Football Betting Bot.
It tracks the current step, consecutive losses, bankroll, and provides
safety pause functionality with detailed statistics.

Key Features:
- Dynamic Percentage progression: 10, 20,30
- Immediate reset to base stake on any loss
- Safety pause after 3 consecutive losses (1 hour)
- Full statistics tracking (win rate, ROI, drawdown, streaks)
- Thread-safe state management
- Telegram-formatted status messages
"""

import time
import logging
from typing import Dict, Optional, List, Any
from datetime import datetime

# Configure logger
logger = logging.getLogger("BetBot.Staking")

# ============================================================
# CONSTANTS
# ============================================================

# The Dynamic Percentage Sequence
STAKE_SEQUENCE = [10, 20, 30]

# Safety thresholds
MAX_CONSECUTIVE_LOSSES = 3
PAUSE_DURATION = 1800  # 1 hour in seconds

# Bet odds (fixed at 1.45)
ODDS = 1.45
PROFIT_MULTIPLIER = ODDS - 1  # 0.45

# Status display formatting
SEQUENCE_DISPLAY = " → ".join(f"${s}" for s in STAKE_SEQUENCE)


class StakingEngine:
    """
    Manages the Dynamic Percentage staking system.
    Tracks current step, consecutive losses, pause states, and statistics.

    The sequence progresses as follows:
    Step 0: $10  → Win → Step 1
    Step 1: $15  → Win → Step 2
    Step 2: $25  → Win → Step 3
    Step 3: $40  → Win → Step 4
    Step 4: $60  → Win → Step 5
    Step 5: $90  → Win → Reset to Step 0

    Any loss: Reset immediately to Step 0 ($10).
    3 consecutive losses: Pause for 1 hour.
    """

    def __init__(self, initial_bankroll: float = 1000.0):
        """
        Initialize the staking engine.

        Args:
            initial_bankroll: Starting bankroll amount (default: $1000)
        """
        self.initial_bankroll = initial_bankroll
        self.current_bankroll = initial_bankroll
        self.start_time = time.time()
        self.last_activity_time = self.start_time

        # State variables
        self.current_step = 0
        self.consecutive_losses = 0
        self.is_paused = False
        self.pause_until = 0.0
        self.pause_reason = ""

        # Statistics tracking
        self.total_bets = 0
        self.total_wins = 0
        self.total_losses = 0
        self.total_staked = 0.0
        self.total_profit = 0.0
        self.max_drawdown = 0.0
        self.peak_bankroll = self.initial_bankroll
        self.current_streak = 0
        self.max_win_streak = 0
        self.max_loss_streak = 0
        self.win_streak_count = 0
        self.loss_streak_count = 0

        # Bet history (last 100 bets)
        self.bet_history = []
        self.max_history_size = 100

        # Statistics for win/loss tracking
        self.last_10_results = []

        logger.info("=" * 50)
        logger.info("🔄 Staking Engine Initialized")
        logger.info(f"💰 Initial Bankroll: ${self.initial_bankroll:.2f}")
        logger.info(f"📊 Sequence: {STAKE_SEQUENCE}")
        logger.info(f"📈 Odds: {ODDS} (Profit Multiplier: {PROFIT_MULTIPLIER})")
        logger.info(f"⚠️ Pause after {MAX_CONSECUTIVE_LOSSES} consecutive losses")
        logger.info("=" * 50)

    # ============================================================
    # CORE METHODS
    # ============================================================

    def reset(self) -> None:
        """Reset the staking engine to initial state."""
        self.current_step = 0
        self.consecutive_losses = 0
        self.is_paused = False
        self.pause_until = 0.0
        self.pause_reason = ""
        self.current_bankroll = self.initial_bankroll
        self.peak_bankroll = self.initial_bankroll
        self.current_streak = 0
        self.win_streak_count = 0
        self.loss_streak_count = 0
        self.bet_history = []
        self.last_10_results = []
        self.start_time = time.time()
        self.last_activity_time = self.start_time

        # Reset statistics (keep initial bankroll)
        self.total_bets = 0
        self.total_wins = 0
        self.total_losses = 0
        self.total_staked = 0.0
        self.total_profit = 0.0
        self.max_drawdown = 0.0
        self.max_win_streak = 0
        self.max_loss_streak = 0

        logger.info("🔄 Staking Engine reset to initial state.")
        logger.info(f"💰 Bankroll: ${self.current_bankroll:.2f}")

    def get_current_stake(self) -> int:
        """
        Returns the current stake based on the step sequence.
        Returns 0 if paused (no bet should be placed).
        """
        # Check if paused
        if self.is_paused:
            if time.time() < self.pause_until:
                return 0  # Still paused
            else:
                # Pause expired, resume
                self.is_paused = False
                self.pause_until = 0.0
                self.pause_reason = ""
                self.consecutive_losses = 0
                logger.info("⏰ Pause expired. Resuming staking.")
                logger.info(f"📊 {self.get_current_step_display()}")

        return STAKE_SEQUENCE[self.current_step]

    def get_current_step_display(self) -> str:
        """
        Human-readable display of current staking status.
        """
        if self.is_paused:
            remaining = int(self.pause_until - time.time())
            minutes = remaining // 60
            seconds = remaining % 60
            return f"⏸️ PAUSED for {minutes}m {seconds}s | Step {self.current_step+1}/{len(STAKE_SEQUENCE)} | Stake: ${STAKE_SEQUENCE[self.current_step]}"

        return f"Step {self.current_step+1}/{len(STAKE_SEQUENCE)} | Stake: ${STAKE_SEQUENCE[self.current_step]}"

    def record_result(self, is_win: bool, match_info: Optional[Dict] = None) -> Dict:
        """
        Record the result of a bet and update the state machine.

        Args:
            is_win: True if the bet won, False if it lost.
            match_info: Optional dictionary with match details for logging.

        Returns:
            Dictionary with the result details and updated state.
        """
        stake = STAKE_SEQUENCE[self.current_step]
        self.total_bets += 1
        self.total_staked += stake
        self.last_activity_time = time.time()

        # Update streak tracking
        if is_win:
            self.current_streak = self.current_streak + 1 if self.current_streak >= 0 else 1
            self.win_streak_count += 1
            if self.current_streak > self.max_win_streak:
                self.max_win_streak = self.current_streak
        else:
            self.current_streak = self.current_streak - 1 if self.current_streak <= 0 else -1
            self.loss_streak_count += 1
            if abs(self.current_streak) > self.max_loss_streak:
                self.max_loss_streak = abs(self.current_streak)

        # Calculate profit/loss
        if is_win:
            profit = stake * PROFIT_MULTIPLIER
            self.total_profit += profit
            self.current_bankroll += profit
            self.total_wins += 1
            self.consecutive_losses = 0

            # Update peak bankroll for drawdown calculation
            if self.current_bankroll > self.peak_bankroll:
                self.peak_bankroll = self.current_bankroll

            # Move to next step
            self.current_step += 1
            if self.current_step >= len(STAKE_SEQUENCE):
                self.current_step = 0  # Reset to $10 after completing sequence
                logger.info(f"✅ Completed full sequence! Resetting to $10.")

            logger.debug(f"✅ WIN: Stake ${stake:.2f} | Profit +${profit:.2f} | Bankroll: ${self.current_bankroll:.2f} | Next: ${STAKE_SEQUENCE[self.current_step]}")

        else:
            # Loss: Reset to step 0 immediately, increment loss counter
            loss = stake
            self.total_profit -= loss
            self.current_bankroll -= loss
            self.total_losses += 1
            self.consecutive_losses += 1

            # Update drawdown
            drawdown = self.peak_bankroll - self.current_bankroll
            if drawdown > self.max_drawdown:
                self.max_drawdown = drawdown

            # Reset to $10
            self.current_step = 0
            logger.debug(f"❌ LOSS: Stake ${stake:.2f} | Loss -${loss:.2f} | Bankroll: ${self.current_bankroll:.2f} | Resetting to $10")

            # Check for safety pause
            if self.consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
                self.is_paused = True
                self.pause_until = time.time() + PAUSE_DURATION
                self.pause_reason = f"{MAX_CONSECUTIVE_LOSSES} consecutive losses"
                logger.warning(f"⏸️ PAUSED: {self.pause_reason}. Resuming at {time.ctime(self.pause_until)}")

        # Store in history
        bet_record = {
            'timestamp': time.time(),
            'datetime': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'stake': stake,
            'is_win': is_win,
            'profit': profit if is_win else -loss,
            'bankroll': self.current_bankroll,
            'step': self.current_step,
            'consecutive_losses': self.consecutive_losses,
            'is_paused': self.is_paused,
            'match_info': match_info or {},
        }

        self.bet_history.append(bet_record)
        if len(self.bet_history) > self.max_history_size:
            self.bet_history.pop(0)

        # Update last 10 results
        self.last_10_results.append(is_win)
        if len(self.last_10_results) > 10:
            self.last_10_results.pop(0)

        # Build result dictionary
        result = {
            'is_win': is_win,
            'stake': stake,
            'profit': profit if is_win else -loss,
            'bankroll': self.current_bankroll,
            'step': self.current_step,
            'next_stake': self.get_current_stake(),
            'consecutive_losses': self.consecutive_losses,
            'is_paused': self.is_paused,
            'total_bets': self.total_bets,
            'total_wins': self.total_wins,
            'total_losses': self.total_losses,
            'total_profit': self.total_profit,
        }

        return result

    # ============================================================
    # STATISTICS METHODS
    # ============================================================

    def get_stats(self) -> Dict:
        """Return current statistics for logging and monitoring."""
        win_rate = (self.total_wins / self.total_bets * 100) if self.total_bets > 0 else 0
        roi = (self.total_profit / self.total_staked * 100) if self.total_staked > 0 else 0
        bankroll_change = ((self.current_bankroll - self.initial_bankroll) / self.initial_bankroll * 100) if self.initial_bankroll > 0 else 0

        # Last 10 performance
        last_10_wins = sum(1 for r in self.last_10_results if r)
        last_10_rate = (last_10_wins / len(self.last_10_results) * 100) if self.last_10_results else 0

        # Running time
        running_seconds = int(time.time() - self.start_time)
        running_hours = running_seconds // 3600
        running_minutes = (running_seconds % 3600) // 60

        return {
            "total_bets": self.total_bets,
            "total_wins": self.total_wins,
            "total_losses": self.total_losses,
            "win_rate": f"{win_rate:.1f}%",
            "last_10_win_rate": f"{last_10_rate:.1f}%",
            "total_staked": f"${self.total_staked:.2f}",
            "total_profit": f"${self.total_profit:.2f}",
            "roi": f"{roi:.1f}%",
            "current_bankroll": f"${self.current_bankroll:.2f}",
            "initial_bankroll": f"${self.initial_bankroll:.2f}",
            "bankroll_change": f"{bankroll_change:+.1f}%",
            "peak_bankroll": f"${self.peak_bankroll:.2f}",
            "max_drawdown": f"${self.max_drawdown:.2f}",
            "current_step": self.current_step,
            "current_stake": f"${STAKE_SEQUENCE[self.current_step]}",
            "is_paused": self.is_paused,
            "pause_until": time.ctime(self.pause_until) if self.is_paused else "N/A",
            "pause_reason": self.pause_reason if self.is_paused else "N/A",
            "consecutive_losses": self.consecutive_losses,
            "current_streak": self.current_streak,
            "max_win_streak": self.max_win_streak,
            "max_loss_streak": self.max_loss_streak,
            "running_time": f"{running_hours}h {running_minutes}m",
            "last_activity": time.ctime(self.last_activity_time),
        }

    def get_status_message(self) -> str:
        """
        Generate a formatted status message for Telegram.
        """
        stats = self.get_stats()

        # Determine streak display
        streak_display = "0"
        if stats['current_streak'] > 0:
            streak_display = f"+{stats['current_streak']}"
        elif stats['current_streak'] < 0:
            streak_display = f"{stats['current_streak']}"

        pause_status = "⏸️ PAUSED" if stats['is_paused'] else "🟢 Active"

        # Build the message
        message = (
            f"📊 **Staking Engine Status**\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 Current Stake: **{stats['current_stake']}**\n"
            f"📈 Step: **{stats['current_step']+1}/{len(STAKE_SEQUENCE)}**\n"
            f"✅ Wins: **{stats['total_wins']}**\n"
            f"❌ Losses: **{stats['total_losses']}**\n"
            f"📊 Win Rate: **{stats['win_rate']}**\n"
            f"📊 Last 10: **{stats['last_10_win_rate']}**\n"
            f"💵 Total Staked: **{stats['total_staked']}**\n"
            f"📈 Total Profit: **{stats['total_profit']}**\n"
            f"📈 ROI: **{stats['roi']}**\n"
            f"💰 Bankroll: **{stats['current_bankroll']}**\n"
            f"📊 Change: **{stats['bankroll_change']}**\n"
            f"📉 Max Drawdown: **{stats['max_drawdown']}**\n"
            f"🔥 Streak: **{streak_display}**\n"
            f"🔢 Consecutive Losses: **{stats['consecutive_losses']}**\n"
            f"⏸️ Status: **{pause_status}**\n"
        )

        # Add pause details if paused
        if stats['is_paused']:
            message += f"⏰ Resume: **{stats['pause_until']}**\n"
            message += f"📝 Reason: **{stats['pause_reason']}**\n"

        message += (
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔄 Sequence: {SEQUENCE_DISPLAY}\n"
            f"⚠️ Pause after {MAX_CONSECUTIVE_LOSSES} consecutive losses\n"
            f"⏱️ Running: **{stats['running_time']}**"
        )

        return message

    def get_quick_status(self) -> str:
        """
        Generate a quick one-line status message for logging.
        """
        if self.is_paused:
            return f"PAUSED | Step {self.current_step+1}/{len(STAKE_SEQUENCE)} | Bankroll: ${self.current_bankroll:.2f}"

        return f"Step {self.current_step+1}/{len(STAKE_SEQUENCE)} | Stake: ${STAKE_SEQUENCE[self.current_step]} | Bankroll: ${self.current_bankroll:.2f} | Profit: ${self.total_profit:.2f}"

    def get_bet_history(self, limit: int = 10) -> List[Dict]:
        """
        Get the last N bet history entries.

        Args:
            limit: Number of entries to return (max 100)

        Returns:
            List of bet history entries.
        """
        return self.bet_history[-limit:] if self.bet_history else []

    def get_sequence_info(self) -> Dict:
        """
        Get information about the current sequence.
        """
        return {
            "sequence": STAKE_SEQUENCE,
            "current_step": self.current_step,
            "current_stake": STAKE_SEQUENCE[self.current_step],
            "next_stake": STAKE_SEQUENCE[self.current_step + 1] if self.current_step + 1 < len(STAKE_SEQUENCE) else STAKE_SEQUENCE[0],
            "steps_remaining": len(STAKE_SEQUENCE) - self.current_step - 1,
            "total_sequence_value": sum(STAKE_SEQUENCE),
        }

    # ============================================================
    # TELEGRAM-FORMATTED MESSAGES
    # ============================================================

    def get_bet_result_message(self, is_win: bool, stake: float, match_info: Optional[Dict] = None) -> str:
        """
        Generate a formatted message for a bet result.
        """
        if is_win:
            profit = stake * PROFIT_MULTIPLIER
            emoji = "✅"
            result_text = "WIN"
        else:
            profit = -stake
            emoji = "❌"
            result_text = "LOSS"

        match_name = match_info.get('match_name', 'Unknown Match') if match_info else 'Unknown Match'

        message = (
            f"{emoji} **{result_text} HT Settlement**\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"⏱️ {match_name}\n"
        )

        if match_info:
            message += f"🌍 {match_info.get('country', 'Unknown')} | 🏆 {match_info.get('league', 'Unknown')}\n"
            message += f"🔢 Score: {match_info.get('score', 'N/A')} (Target: {match_info.get('trigger_score', 'N/A')})\n"

        message += (
            f"💰 Stake: **${stake:.2f}**\n"
            f"📈 Profit: **{profit:+.2f}**\n"
            f"📊 {self.get_current_step_display()}\n"
            f"💵 Bankroll: **${self.current_bankroll:.2f}**\n"
            f"📈 Total Profit: **${self.total_profit:.2f}**"
        )

        if self.is_paused:
            message += f"\n⏸️ **PAUSED** - {self.pause_reason}"

        return message

    def get_bet_placed_message(self, stake: float, match_info: Dict) -> str:
        """
        Generate a formatted message for a bet placement.
        """
        step_display = f" | Step {self.current_step + 1}/{len(STAKE_SEQUENCE)}"

        message = (
            f"🎯 **BET PLACED**\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"⏱️ {match_info.get('match_name', 'Unknown Match')}\n"
            f"🌍 {match_info.get('country', 'Unknown')} | 🏆 {match_info.get('league', 'Unknown')}\n"
            f"🔢 Score: {match_info.get('score', 'N/A')}\n"
            f"💰 Stake: **${stake:.2f}**{step_display}\n"
            f"💵 Bankroll: **${self.current_bankroll:.2f}**"
        )

        return message


# ============================================================
# SINGLETON INSTANCE (Optional)
# ============================================================

_staking_engine_instance: Optional[StakingEngine] = None


def get_staking_engine(initial_bankroll: float = 1000.0) -> StakingEngine:
    """
    Get or create the global staking engine instance.

    Args:
        initial_bankroll: Starting bankroll (only used on first creation).

    Returns:
        The global StakingEngine instance.
    """
    global _staking_engine_instance
    if _staking_engine_instance is None:
        _staking_engine_instance = StakingEngine(initial_bankroll)
    return _staking_engine_instance


def reset_staking_engine() -> None:
    """Reset the global staking engine instance."""
    global _staking_engine_instance
    if _staking_engine_instance:
        _staking_engine_instance.reset()
    else:
        _staking_engine_instance = StakingEngine()


# ============================================================
# TESTING / DEBUGGING
# ============================================================

if __name__ == "__main__":
    # Quick test of the staking engine
    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("STAKING ENGINE TEST")
    print("=" * 60)

    engine = StakingEngine(1000)
    print(f"Initial Bankroll: ${engine.current_bankroll:.2f}")
    print(f"Sequence: {STAKE_SEQUENCE}")
    print(f"Odds: {ODDS} (Profit: {PROFIT_MULTIPLIER * 100}%)")
    print("=" * 60)

    # Simulate a series of bets based on a 74% win rate pattern
    import random
    random.seed(42)  # For reproducible results

    test_results = [True] * 74 + [False] * 26
    random.shuffle(test_results)

    total_profit = 0

    for i, result in enumerate(test_results[:20]):  # Show first 20 bets
        stake = engine.get_current_stake()
        outcome = "WIN" if result else "LOSS"
        print(f"\nBet {i+1}: Stake ${stake} → {outcome}")
        engine.record_result(result)
        print(f"  {engine.get_current_step_display()}")
        print(f"  Bankroll: ${engine.current_bankroll:.2f}")
        print(f"  Total Profit: ${engine.total_profit:.2f}")
        if engine.is_paused:
            print(f"  ⏸️ PAUSED until {time.ctime(engine.pause_until)}")

    print("\n" + "=" * 60)
    print("FINAL STATS")
    print("=" * 60)
    print(engine.get_status_message())

    print("\n" + "=" * 60)
    print("BET HISTORY (Last 5)")
    print("=" * 60)
    for bet in engine.get_bet_history(5):
        print(f"{bet['datetime']} | ${bet['stake']} | {'WIN' if bet['is_win'] else 'LOSS'} | Profit: {bet['profit']:+.2f} | Bankroll: ${bet['bankroll']:.2f}")
