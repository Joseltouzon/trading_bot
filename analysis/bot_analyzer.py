# -*- coding: utf-8 -*-
# analysis/bot_analyzer.py
"""
Bot Analyzer - Master analyzer that orchestrates all analysis modules
"""

import logging
from typing import Dict, List
from .performance_analyzer import PerformanceAnalyzer
from .anomaly_detector import AnomalyDetector
from .strategy_optimizer import StrategyOptimizer
from datetime import datetime


class BotAnalyzer:
    """Master analyzer that coordinates all bot analysis"""

    def __init__(self, db=None, config=None, log: logging.Logger = None):
        """
        Initialize the master analyzer
        Args:
            db: Database connection
            config: Bot configuration object
            log: Logger instance
        """
        self.db = db
        self.config = config
        self.log = log or logging.getLogger(__name__)

        # Initialize sub-analyzers
        self.performance = PerformanceAnalyzer(db, log)
        self.anomalies = AnomalyDetector(db, log)
        self.optimizer = StrategyOptimizer(db, config, log)

    def run_full_analysis(self, days: int = 30) -> str:
        """
        Run complete analysis with all modules
        Args:
            days: Number of days to analyze
        Returns:
            Complete analysis report
        """
        report = f"""
╔══════════════════════════════════════════════════════════════╗
║            🤖 COMPLETE BOT ANALYSIS REPORT 🤖                ║
║              Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}             ║
║              Analysis Period: {days} days                             ║
╚══════════════════════════════════════════════════════════════╝

"""

        # 1. Performance Analysis
        self.log.info("Running performance analysis...")
        report += self.performance.generate_report(days)
        report += "\n"

        # 2. Anomaly Detection
        self.log.info("Running anomaly detection...")
        report += self.anomalies.generate_anomaly_report()
        report += "\n"

        # 3. Strategy Optimization
        self.log.info("Running strategy optimization...")
        report += self.optimizer.generate_optimization_report(days)

        # 4. Executive Summary
        report += self._generate_executive_summary(days)

        return report

    def run_quick_check(self) -> str:
        """
        Run quick health check without full analysis
        Returns:
            Quick status report
        """
        report = f"""
╔══════════════════════════════════════════════════════════════╗
║               🔍 BOT QUICK HEALTH CHECK 🔍                   ║
║                   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                       ║
╚══════════════════════════════════════════════════════════════╝

"""

        # Check for critical issues
        anomalies = self.anomalies.detect_all()
        critical = [a for a in anomalies if a.severity.value == "critical"]

        if critical:
            report += "🚨 CRITICAL ALERTS:\n"
            for anomaly in critical:
                report += f"  ⚠️  {anomaly.type.value.upper()}: {anomaly.description}\n"
                report += f"      ➜ {anomaly.recommendation}\n"
            report += "\n"
        else:
            report += "✅ No critical alerts\n\n"

        # Get latest performance
        metrics = self.performance.analyze_trades(days=1)
        if metrics and metrics.total_trades > 0:
            report += f"""
TODAY'S PERFORMANCE:
  Trades:     {metrics.total_trades}
  Win Rate:   {metrics.win_rate:.1%}
  P&L:        ${metrics.total_pnl:.2f}
  Best:       ${metrics.best_trade:.2f}
  Worst:      ${metrics.worst_trade:.2f}
"""

        return report

    def get_actionable_recommendations(self) -> List[str]:
        """
        Get top actionable recommendations
        Returns:
            List of action items prioritized by impact
        """
        recommendations = []

        # From anomaly detection
        anomalies = self.anomalies.detect_all()
        critical_anomalies = [a for a in anomalies if a.severity.value == "critical"]
        for anomaly in critical_anomalies:
            recommendations.append(f"[URGENT] {anomaly.recommendation}")

        # From performance analysis
        metrics = self.performance.analyze_trades(days=7)
        suggestions = self.performance.get_optimization_suggestions(metrics)
        for suggestion in suggestions[:3]:
            recommendations.append(f"[{suggestion.impact.upper()}] {suggestion.parameter}: {suggestion.reason}")

        # From strategy optimization
        optimizations = self.optimizer.get_all_optimizations(days=7)
        high_conf = [o for o in optimizations if o.confidence > 0.75]
        for opt in high_conf[:2]:
            recommendations.append(
                f"[{opt.confidence:.0%} confidence] Adjust {opt.parameter} "
                f"from {opt.current:.2f} to {opt.recommended:.2f}"
            )

        return recommendations

    def save_report_to_file(self, report: str, filename: str = None) -> str:
        """
        Save analysis report to file
        Args:
            report: Report text
            filename: Output filename (optional)
        Returns:
            Path to saved file
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"bot_analysis_{timestamp}.txt"

        filepath = f"./reports/{filename}"
        
        try:
            import os
            os.makedirs("./reports", exist_ok=True)
            
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(report)
            
            self.log.info(f"Report saved to {filepath}")
            return filepath
        except Exception as e:
            self.log.error(f"Failed to save report: {e}")
            return None

    def _generate_executive_summary(self, days: int = 30) -> str:
        """Generate executive summary"""
        summary = f"""
{'═' * 60}
📋 EXECUTIVE SUMMARY
{'═' * 60}

KEY METRICS:
"""

        metrics = self.performance.analyze_trades(days)
        if metrics and metrics.total_trades > 0:
            summary += f"""
  • Total Trades: {metrics.total_trades}
  • Win Rate: {metrics.win_rate:.1%} (Target: 50%+)
  • Profit Factor: {metrics.profit_factor:.2f}x (Target: 1.5x+)
  • Sharpe Ratio: {metrics.sharpe_ratio:.2f} (Target: 1.0+)
  • Max Drawdown: {metrics.max_drawdown:.2%} (Target: <10%)
  • Total P&L: ${metrics.total_pnl:.2f}
"""

        # Recommendations
        recommendations = self.get_actionable_recommendations()
        if recommendations:
            summary += f"""
TOP RECOMMENDATIONS:
"""
            for i, rec in enumerate(recommendations[:5], 1):
                summary += f"  {i}. {rec}\n"
        else:
            summary += "\n✅ No critical recommendations at this time\n"

        summary += f"""
NEXT STEPS:
  1. Review critical alerts (if any)
  2. Test parameter optimizations in paper trading
  3. Monitor anomalies and adjust position sizing
  4. Re-run analysis in 7 days

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'═' * 60}
"""
        return summary


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    analyzer = BotAnalyzer()
    
    # Quick check
    print(analyzer.run_quick_check())
    
    # Full analysis
    # report = analyzer.run_full_analysis(days=30)
    # analyzer.save_report_to_file(report)
