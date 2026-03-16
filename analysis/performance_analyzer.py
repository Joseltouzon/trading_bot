# -*- coding: utf-8 -*-
# analysis/performance_analyzer.py
"""
Bot Performance Analyzer - Analyzes trading performance and suggests improvements
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import pandas as pd
from dataclasses import dataclass
from enum import Enum


class TradeQuality(Enum):
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"


@dataclass
class PerformanceMetrics:
    """Container for performance metrics"""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    total_pnl: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    consecutive_losses: int = 0
    best_trade: float = 0.0
    worst_trade: float = 0.0


@dataclass
class OptimizationSuggestion:
    """Suggestion for parameter optimization"""
    parameter: str
    current_value: float
    suggested_value: float
    reason: str
    impact: str  # "high", "medium", "low"
    priority: int  # 1-5, 1=highest


class PerformanceAnalyzer:
    """Analyzes bot performance and provides optimization suggestions"""

    def __init__(self, db=None, log: logging.Logger = None):
        """
        Initialize analyzer
        Args:
            db: Database connection
            log: Logger instance
        """
        self.db = db
        self.log = log or logging.getLogger(__name__)

    def analyze_trades(self, days: int = 30) -> PerformanceMetrics:
        """
        Analyze trading performance over specified days
        Args:
            days: Number of days to analyze
        Returns:
            PerformanceMetrics object
        """
        if not self.db:
            self.log.warning("Database not connected - using dummy data")
            return self._create_dummy_metrics()

        try:
            # Get trades from closed positions
            query = """
                SELECT id, symbol, entry_price, exit_price, qty, 
                       opened_at, closed_at, realized_pnl, status
                FROM positions
                WHERE closed_at >= NOW() - INTERVAL '%d days'
                AND status = 'CLOSED'
                ORDER BY closed_at DESC
            """ % days

            with self.db.cursor() as cur:
                cur.execute(query)
                result = cur.fetchall()
            if not result:
                self.log.info("No closed trades found in the period")
                return PerformanceMetrics()

            return self._calculate_metrics(result)

        except Exception as e:
            self.log.error(f"Error analyzing trades: {e}")
            return PerformanceMetrics()

    def analyze_daily_performance(self, days: int = 30) -> pd.DataFrame:
        """
        Analyze daily aggregated performance
        Args:
            days: Number of days to analyze
        Returns:
            DataFrame with daily stats
        """
        if not self.db:
            return pd.DataFrame()

        try:
            query = """
                SELECT DATE(closed_at) as date,
                       COUNT(*) as trades,
                       SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END) as wins,
                       SUM(CASE WHEN realized_pnl < 0 THEN 1 ELSE 0 END) as losses,
                       SUM(realized_pnl) as daily_pnl,
                       AVG(realized_pnl) as avg_pnl,
                       MAX(realized_pnl) as best_trade,
                       MIN(realized_pnl) as worst_trade
                FROM positions
                WHERE closed_at >= NOW() - INTERVAL '%d days'
                AND status = 'CLOSED'
                GROUP BY DATE(closed_at)
                ORDER BY date DESC
            """ % days

            with self.db.cursor() as cur:
                cur.execute(query)
                result = cur.fetchall()
            if result:
                df = pd.DataFrame(result)
                df['date'] = pd.to_datetime(df['date'])
                return df
            return pd.DataFrame()

        except Exception as e:
            self.log.error(f"Error analyzing daily performance: {e}")
            return pd.DataFrame()

    def analyze_symbol_performance(self) -> pd.DataFrame:
        """
        Analyze performance by trading symbol
        Returns:
            DataFrame with symbol stats
        """
        if not self.db:
            return pd.DataFrame()

        try:
            query = """
                SELECT symbol,
                       COUNT(*) as trades,
                       SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END) as wins,
                       SUM(CASE WHEN realized_pnl <= 0 THEN 1 ELSE 0 END) as losses,
                       SUM(realized_pnl) as total_pnl,
                       AVG(realized_pnl) as avg_pnl,
                       STDDEV(realized_pnl) as volatility
                FROM positions
                WHERE status = 'CLOSED'
                GROUP BY symbol
                ORDER BY total_pnl DESC
            """

            with self.db.cursor() as cur:
                cur.execute(query)
                result = cur.fetchall()
            if result:
                return pd.DataFrame(result)
            return pd.DataFrame()

        except Exception as e:
            self.log.error(f"Error analyzing symbol performance: {e}")
            return pd.DataFrame()

    def get_optimization_suggestions(self, metrics: PerformanceMetrics) -> List[OptimizationSuggestion]:
        """
        Generate optimization suggestions based on metrics
        Args:
            metrics: PerformanceMetrics object
        Returns:
            List of OptimizationSuggestion objects
        """
        suggestions = []

        # Win rate analysis
        if metrics.win_rate < 0.35:
            suggestions.append(OptimizationSuggestion(
                parameter="Entry Logic",
                current_value=metrics.win_rate,
                suggested_value=0.45,
                reason="Win rate below 35% suggests entry criteria too loose",
                impact="high",
                priority=1
            ))

        if metrics.win_rate > 0.65:
            suggestions.append(OptimizationSuggestion(
                parameter="Position Sizing",
                current_value=0.5,
                suggested_value=1.0,
                reason="High win rate allows for larger position sizes",
                impact="high",
                priority=2
            ))

        # Profit factor analysis
        if metrics.profit_factor < 1.5:
            suggestions.append(OptimizationSuggestion(
                parameter="Risk/Reward Ratio",
                current_value=metrics.profit_factor,
                suggested_value=1.5,
                reason="Profit factor too low - adjust stop loss or take profit levels",
                impact="high",
                priority=3
            ))

        # Max drawdown analysis
        if metrics.max_drawdown > 0.15:
            suggestions.append(OptimizationSuggestion(
                parameter="Daily Loss Limit %",
                current_value=10.0,
                suggested_value=5.0,
                reason="Max drawdown exceeds 15% - tighter daily limits needed",
                impact="high",
                priority=1
            ))

        # Consecutive losses
        if metrics.consecutive_losses > 3:
            suggestions.append(OptimizationSuggestion(
                parameter="Cooldown Period",
                current_value=8,
                suggested_value=16,
                reason=f"Too many consecutive losses ({metrics.consecutive_losses}) - increase cooldown",
                impact="medium",
                priority=4
            ))

        # Consistency (Sharpe ratio)
        if metrics.sharpe_ratio < 1.0:
            suggestions.append(OptimizationSuggestion(
                parameter="Risk Parameters",
                current_value=1.0,
                suggested_value=1.5,
                reason="Low Sharpe ratio indicates inconsistent returns",
                impact="medium",
                priority=5
            ))

        return sorted(suggestions, key=lambda x: x.priority)

    def identify_losing_patterns(self, days: int = 30) -> Dict[str, any]:
        """
        Identify patterns in losing trades
        Args:
            days: Number of days to analyze
        Returns:
            Dictionary with losing trade patterns
        """
        if not self.db:
            return {}

        patterns = {
            "worst_symbols": [],
            "worst_times": [],
            "average_loss": 0.0,
            "loss_streak": 0,
            "recommendations": []
        }

        try:
            # Get losing trades
            query = """
                SELECT symbol, closed_at, realized_pnl, entry_price, exit_price
                FROM positions
                WHERE realized_pnl < 0
                AND closed_at >= NOW() - INTERVAL '%d days'
                AND status = 'CLOSED'
                ORDER BY realized_pnl ASC
                LIMIT 20
            """ % days

            with self.db.cursor() as cur:
                cur.execute(query)
                losing_trades = cur.fetchall()
            if losing_trades:
                patterns["average_loss"] = sum(t[2] for t in losing_trades) / len(losing_trades)

                # Get worst symbols
                symbol_losses = {}
                for trade in losing_trades:
                    symbol = trade[0]
                    symbol_losses[symbol] = symbol_losses.get(symbol, 0) + 1

                patterns["worst_symbols"] = sorted(symbol_losses.items(), key=lambda x: x[1], reverse=True)[:5]

                # Get worst times (hour of day)
                time_losses = {}
                for trade in losing_trades:
                    hour = pd.to_datetime(trade[1]).hour
                    time_losses[hour] = time_losses.get(hour, 0) + 1

                patterns["worst_times"] = sorted(time_losses.items(), key=lambda x: x[1], reverse=True)[:3]

                # Generate recommendations
                if patterns["worst_symbols"]:
                    symbols_str = ", ".join([s[0] for s in patterns["worst_symbols"]])
                    patterns["recommendations"].append(f"Consider removing {symbols_str} from trading list")

                if patterns["worst_times"]:
                    hours_str = ", ".join([f"{h}:00" for h, _ in patterns["worst_times"]])
                    patterns["recommendations"].append(f"Avoid trading during {hours_str}")

        except Exception as e:
            self.log.error(f"Error identifying losing patterns: {e}")

        return patterns

    def generate_report(self, days: int = 30) -> str:
        """
        Generate a comprehensive performance report
        Args:
            days: Number of days to analyze
        Returns:
            Formatted report string
        """
        metrics = self.analyze_trades(days)
        suggestions = self.get_optimization_suggestions(metrics)
        losing_patterns = self.identify_losing_patterns(days)
        daily_perf = self.analyze_daily_performance(days)
        symbol_perf = self.analyze_symbol_performance()

        report = f"""
╔══════════════════════════════════════════════════════════════╗
║           BOT PERFORMANCE ANALYSIS REPORT                    ║
║           Period: Last {days} days - Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}        ║
╚══════════════════════════════════════════════════════════════╝

📊 OVERALL METRICS
{'─' * 60}
Total Trades:           {metrics.total_trades}
Winning Trades:         {metrics.winning_trades}
Losing Trades:          {metrics.losing_trades}
Win Rate:               {metrics.win_rate:.2%}
Total P&L:              ${metrics.total_pnl:.2f}
Average Win:            ${metrics.avg_win:.2f}
Average Loss:           ${metrics.avg_loss:.2f}
Profit Factor:          {metrics.profit_factor:.2f}x
Sharpe Ratio:           {metrics.sharpe_ratio:.2f}
Max Drawdown:           {metrics.max_drawdown:.2%}
Best Trade:             ${metrics.best_trade:.2f}
Worst Trade:            ${metrics.worst_trade:.2f}
Consecutive Losses:     {metrics.consecutive_losses}

🎯 OPTIMIZATION SUGGESTIONS
{'─' * 60}
"""

        for i, suggestion in enumerate(suggestions[:5], 1):
            report += f"""
{i}. {suggestion.parameter} [Priority: {suggestion.priority}]
   Current: {suggestion.current_value}
   Suggested: {suggestion.suggested_value}
   Reason: {suggestion.reason}
   Impact: {suggestion.impact.upper()}
"""

        if losing_patterns.get("worst_symbols"):
            report += f"""
⚠️  LOSING PATTERNS DETECTED
{'─' * 60}
Worst Symbols:          {', '.join([s[0] for s in losing_patterns['worst_symbols'][:5]])}
Average Loss:           ${losing_patterns['average_loss']:.2f}
Worst Trading Hours:    {', '.join([f"{h}:00" for h, _ in losing_patterns['worst_times'][:3]])}

Recommendations:
"""
            for rec in losing_patterns.get("recommendations", []):
                report += f"  • {rec}\n"

        if not daily_perf.empty:
            report += f"""
📈 DAILY PERFORMANCE
{'─' * 60}
Best Day:               {daily_perf['daily_pnl'].max():.2f}
Worst Day:              {daily_perf['daily_pnl'].min():.2f}
Average Daily P&L:      {daily_perf['daily_pnl'].mean():.2f}
Profitable Days:        {(daily_perf['daily_pnl'] > 0).sum()} / {len(daily_perf)}
"""

        if not symbol_perf.empty:
            report += f"""
💰 SYMBOL PERFORMANCE (Top 5)
{'─' * 60}
"""
            for _, row in symbol_perf.head(5).iterrows():
                report += f"{row['symbol']:12} - {row['trades']} trades, Win Rate: {row['wins']/max(row['trades'], 1):.1%}, "
                report += f"Total P&L: ${row['total_pnl']:.2f}\n"

        report += f"\n{'═' * 60}\n"
        return report

    # ==================== HELPER METHODS ====================

    def _calculate_metrics(self, trades: List[Tuple]) -> PerformanceMetrics:
        """Calculate performance metrics from trades"""
        if not trades:
            return PerformanceMetrics()

        df = pd.DataFrame(trades, columns=['id', 'symbol', 'entry_price', 'exit_price', 
                                           'qty', 'opened_at', 'closed_at', 'realized_pnl', 'status'])
        
        metrics = PerformanceMetrics()
        metrics.total_trades = len(df)
        metrics.winning_trades = (df['realized_pnl'] > 0).sum()
        metrics.losing_trades = (df['realized_pnl'] < 0).sum()
        metrics.total_pnl = df['realized_pnl'].sum()
        metrics.win_rate = metrics.winning_trades / max(metrics.total_trades, 1)

        if metrics.winning_trades > 0:
            metrics.avg_win = df[df['realized_pnl'] > 0]['realized_pnl'].mean()

        if metrics.losing_trades > 0:
            metrics.avg_loss = abs(df[df['realized_pnl'] < 0]['realized_pnl'].mean())

        metrics.profit_factor = metrics.avg_win * metrics.winning_trades / max(
            metrics.avg_loss * metrics.losing_trades, 0.01)
        metrics.best_trade = df['realized_pnl'].max()
        metrics.worst_trade = df['realized_pnl'].min()

        # Calculate Sharpe ratio (simplified)
        if len(df) > 1:
            returns = df['realized_pnl'].pct_change().dropna()
            if returns.std() > 0:
                metrics.sharpe_ratio = (returns.mean() / returns.std()) * (252 ** 0.5)

        # Calculate max drawdown
        cumulative = (1 + df['realized_pnl'].pct_change()).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        metrics.max_drawdown = abs(drawdown.min()) if len(drawdown) > 0 else 0

        # Calculate consecutive losses
        losing_streak = 0
        current_streak = 0
        for pnl in df['realized_pnl']:
            if pnl < 0:
                current_streak += 1
                losing_streak = max(losing_streak, current_streak)
            else:
                current_streak = 0
        metrics.consecutive_losses = losing_streak

        return metrics

    def _create_dummy_metrics(self) -> PerformanceMetrics:
        """Create dummy metrics for testing"""
        return PerformanceMetrics(
            total_trades=100,
            winning_trades=52,
            losing_trades=48,
            win_rate=0.52,
            total_pnl=2500.0,
            avg_win=75.0,
            avg_loss=45.0,
            profit_factor=1.92,
            sharpe_ratio=1.3,
            max_drawdown=0.08,
            consecutive_losses=3,
            best_trade=250.0,
            worst_trade=-150.0
        )


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)
    analyzer = PerformanceAnalyzer()
    
    print(analyzer.generate_report(days=30))
