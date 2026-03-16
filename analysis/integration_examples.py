# -*- coding: utf-8 -*-
# analysis/integration_examples.py
"""
Integration examples - How to integrate the analyzer into the bot
"""

import logging
from typing import Optional
from datetime import datetime, timedelta
from analysis import BotAnalyzer


class AnalysisIntegration:
    """
    Examples of how to integrate analysis into your bot workflow
    """

    def __init__(self, db, config, log: logging.Logger, telegram=None):
        """
        Initialize analysis integration
        Args:
            db: Database connection
            config: Bot configuration
            log: Logger instance
            telegram: Telegram notifier (optional)
        """
        self.db = db
        self.config = config
        self.log = log
        self.telegram = telegram
        self.analyzer = BotAnalyzer(db=db, config=config, log=log)
        self.last_analysis = None

    # ==================== STARTUP CHECKS ====================

    def run_startup_analysis(self) -> bool:
        """
        Run quick analysis at bot startup to verify everything is ok
        Returns:
            True if bot can start safely, False if there are critical issues
        """
        self.log.info("Running startup health check...")

        try:
            # Get critical anomalies
            critical = self.analyzer.anomalies.detect_all()
            critical = [a for a in critical if a.severity.value == "critical"]

            if critical:
                self.log.error(f"Critical issues detected at startup: {len(critical)}")
                for anomaly in critical:
                    msg = f"🚨 {anomaly.type.value}: {anomaly.description}"
                    self.log.error(msg)
                    if self.telegram:
                        self.telegram.send_notification(msg)
                return False

            self.log.info("✅ Startup health check passed")
            return True

        except Exception as e:
            self.log.error(f"Error during startup analysis: {e}")
            return True  # Don't block bot startup on analysis errors


    # ==================== PERIODIC ANALYSIS ====================

    def check_for_anomalies_periodically(self, interval_hours: int = 1) -> None:
        """
        Run anomaly detection at regular intervals
        Args:
            interval_hours: Check every N hours
        """
        now = datetime.now()
        
        if self.last_analysis is None or \
           (now - self.last_analysis).total_seconds() > (interval_hours * 3600):
            
            self.log.info(f"Running periodic anomaly check...")
            
            try:
                anomalies = self.analyzer.anomalies.detect_all()
                
                # Alert on any new critical/warning issues
                critical = [a for a in anomalies if a.severity.value == "critical"]
                warnings = [a for a in anomalies if a.severity.value == "warning"]
                
                if critical:
                    msg = f"⚠️ ALERT: {len(critical)} critical issues detected!"
                    self.log.warning(msg)
                    if self.telegram:
                        self.telegram.send_notification(msg)
                        for anomaly in critical:
                            self.telegram.send_notification(
                                f"{anomaly.type.value}: {anomaly.recommendation}"
                            )
                
                if warnings:
                    self.log.warning(f"Found {len(warnings)} warnings")
                
                self.last_analysis = now
            
            except Exception as e:
                self.log.error(f"Error in periodic analysis: {e}")


    # ==================== TRADE-BASED TRIGGERS ====================

    def analyze_after_trade(self, trade_count: int = 20) -> None:
        """
        Analyze bot after reaching specific trade count
        Args:
            trade_count: Number of trades since last analysis
        """
        try:
            # Check if we've made N trades since last analysis
            metrics = self.analyzer.performance.analyze_trades(days=1)
            
            if metrics and metrics.total_trades > 0 and metrics.total_trades % trade_count == 0:
                self.log.info(f"Reached {metrics.total_trades} trades, running analysis...")
                
                # Get quick statistics for this session
                if metrics.winning_trades > 0 or metrics.losing_trades > 0:
                    win_rate = metrics.winning_trades / (metrics.winning_trades + metrics.losing_trades)
                    
                    msg = f"""
📊 Trading Session Update ({metrics.total_trades} trades):
Win Rate: {win_rate:.1%}
P&L: ${metrics.total_pnl:.2f}
Avg Win: ${metrics.avg_win:.2f}
Avg Loss: ${metrics.avg_loss:.2f}
"""
                    self.log.info(msg)
                    if self.telegram:
                        self.telegram.send_notification(msg)
        
        except Exception as e:
            self.log.error(f"Error in trade-based analysis: {e}")


    # ==================== DAILY SUMMARY ====================

    def send_daily_summary(self, hour: int = 21, minute: int = 0) -> None:
        """
        Send daily analysis summary at specific time
        Args:
            hour: Hour to send summary (24-hour format)
            minute: Minute to send summary
        """
        now = datetime.now()
        
        if now.hour == hour and now.minute == minute:
            self.log.info("Generating daily summary...")
            
            try:
                report = self.analyzer.performance.generate_report(days=1)
                
                if self.telegram:
                    # Send as multiple messages if summary is long
                    sections = report.split("═" * 60)
                    for section in sections:
                        if section.strip():
                            self.telegram.send_notification(section)
                
                # Also save to file
                filepath = self.analyzer.save_report_to_file(
                    report,
                    f"daily_summary_{now.strftime('%Y%m%d')}.txt"
                )
                self.log.info(f"Daily summary saved to {filepath}")
            
            except Exception as e:
                self.log.error(f"Error generating daily summary: {e}")


    # ==================== WEEKLY DEEP ANALYSIS ====================

    def run_weekly_analysis(self) -> None:
        """
        Run comprehensive analysis weekly for detailed review
        """
        now = datetime.now()
        
        # Run on Sundays at 22:00 UTC
        if now.weekday() == 6 and now.hour == 22:  # Sunday = 6
            self.log.info("Running weekly deep analysis...")
            
            try:
                # Full analysis for last 7 days
                full_report = self.analyzer.run_full_analysis(days=7)
                
                # Get recommendations
                recommendations = self.analyzer.get_actionable_recommendations()
                
                # Save report
                filepath = self.analyzer.save_report_to_file(
                    full_report,
                    f"weekly_analysis_{now.strftime('%Y_week_%U')}.txt"
                )
                
                # Send summary to Telegram
                if self.telegram:
                    summary = f"""
🔍 WEEKLY ANALYSIS REPORT
Generated: {now.strftime('%Y-%m-%d %H:%M:%S')}

{self.analyzer._generate_executive_summary(days=7)}

Full report saved to: {filepath}
"""
                    self.telegram.send_notification(summary)
                
                self.log.info(f"Weekly analysis complete. Report: {filepath}")
            
            except Exception as e:
                self.log.error(f"Error in weekly analysis: {e}")


    # ==================== RISK MONITORING ====================

    def check_risk_levels(self) -> None:
        """
        Monitor risk metrics and alert if thresholds exceeded
        """
        try:
            metrics = self.analyzer.performance.analyze_trades(days=7)
            
            # High drawdown alert
            if metrics.max_drawdown > 0.15:  # 15%
                msg = f"⚠️ High drawdown detected: {metrics.max_drawdown:.1%}"
                self.log.warning(msg)
                if self.telegram:
                    self.telegram.send_notification(msg)
            
            # Low win rate alert
            if metrics.win_rate < 0.35 and metrics.total_trades > 20:
                msg = f"⚠️ Low win rate: {metrics.win_rate:.1%} ({metrics.total_trades} trades)"
                self.log.warning(msg)
                if self.telegram:
                    self.telegram.send_notification(msg)
            
            # Profit factor check
            if metrics.profit_factor < 1.0:
                msg = f"🚨 CRITICAL: Bot is losing money! Profit factor: {metrics.profit_factor:.2f}"
                self.log.error(msg)
                if self.telegram:
                    self.telegram.send_notification(msg)
        
        except Exception as e:
            self.log.error(f"Error in risk monitoring: {e}")


    # ==================== SYMBOL ANALYSIS ====================

    def analyze_symbol_performance(self) -> None:
        """
        Analyze which symbols are performing best/worst
        """
        try:
            symbol_perf = self.analyzer.performance.analyze_symbol_performance()
            
            if symbol_perf.empty:
                return
            
            # Get worst performing symbols
            worst = symbol_perf.nsmallest(3, 'total_pnl')
            
            for _, row in worst.iterrows():
                win_rate = row['wins'] / row['trades'] if row['trades'] > 0 else 0
                
                if win_rate < 0.4:
                    self.log.warning(
                        f"Poor performance for {row['symbol']}: "
                        f"{row['trades']} trades, {win_rate:.1%} win rate"
                    )
            
            # Get best performing symbols
            best = symbol_perf.nlargest(3, 'total_pnl')
            
            if not best.empty:
                self.log.info(f"Best symbol: {best.iloc[0]['symbol']} "
                             f"with ${best.iloc[0]['total_pnl']:.2f} P&L")
        
        except Exception as e:
            self.log.error(f"Error analyzing symbols: {e}")


# ==================== INTEGRATION WITH BOT ====================

def integrate_analysis_with_bot(bot_instance):
    """
    Example of integrating analysis into bot's event loop
    
    Usage in bot.py:
        
        from analysis.integration_examples import integrate_analysis_with_bot
        
        # After bot initialization
        bot = Bot()
        analysis_integration = integrate_analysis_with_bot(bot)
        
        # In bot's main loop
        analysis_integration.check_for_anomalies_periodically(interval_hours=1)
        analysis_integration.check_risk_levels()
        analysis_integration.analyze_after_trade(trade_count=20)
    """
    
    integration = AnalysisIntegration(
        db=bot_instance.db,
        config=bot_instance.config,
        log=bot_instance.log,
        telegram=bot_instance.telegram if hasattr(bot_instance, 'telegram') else None
    )
    
    # Run startup check
    integration.run_startup_analysis()
    
    return integration


if __name__ == "__main__":
    # Example standalone usage
    logging.basicConfig(level=logging.INFO)
    
    from db import Database
    import config as CFG
    
    db = Database()
    logger = logging.getLogger(__name__)
    analyzer = BotAnalyzer(db=db, config=CFG, log=logger)
    
    print(analyzer.run_quick_check())
