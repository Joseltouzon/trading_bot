# -*- coding: utf-8 -*-
# analysis/anomaly_detector.py
"""
Anomaly Detection - Identifies unusual patterns and risks in bot behavior
"""

import logging
from typing import Dict, List, Tuple
from dataclasses import dataclass
from enum import Enum
import statistics


class AnomalyType(Enum):
    CONSECUTIVE_LOSSES = "consecutive_losses"
    UNUSUAL_VOLATILITY = "unusual_volatility"
    SLIPPAGE_SPIKE = "slippage_spike"
    FILL_RATE_LOW = "fill_rate_low"
    MARGIN_WARNING = "margin_warning"
    FUNDING_RATE_SPIKE = "funding_rate_spike"
    SYMBOL_CORRELATION = "symbol_correlation"
    EXECUTION_DELAY = "execution_delay"


class SeverityLevel(Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


@dataclass
class Anomaly:
    """Detected anomaly"""
    type: AnomalyType
    severity: SeverityLevel
    description: str
    metric_value: float
    threshold: float
    timestamp: str
    recommendation: str


class AnomalyDetector:
    """Detects anomalies in bot behavior and trading"""

    def __init__(self, db=None, log: logging.Logger = None):
        self.db = db
        self.log = log or logging.getLogger(__name__)
        self.anomalies = []

    def detect_all(self) -> List[Anomaly]:
        """
        Run all anomaly detections
        Returns:
            List of detected anomalies
        """
        self.anomalies = []
        
        self._detect_consecutive_losses()
        self._detect_volatility_spikes()
        self._detect_margin_issues()
        self._detect_execution_issues()

        return self.anomalies

    def _detect_consecutive_losses(self) -> None:
        """Detect consecutive losing trades"""
        if not self.db:
            return

        try:
            query = """
                SELECT realized_pnl, closed_at
                FROM positions
                WHERE status = 'CLOSED'
                ORDER BY closed_at DESC
                LIMIT 20
            """
            with self.db.cursor() as cur:
                cur.execute(query)
                trades = cur.fetchall()
            
            if not trades:
                return

            consecutive = 0
            for pnl, _ in trades:
                if pnl < 0:
                    consecutive += 1
                else:
                    break

            if consecutive > 5:
                self.anomalies.append(Anomaly(
                    type=AnomalyType.CONSECUTIVE_LOSSES,
                    severity=SeverityLevel.WARNING if consecutive < 8 else SeverityLevel.CRITICAL,
                    description=f"Detected {consecutive} consecutive losing trades",
                    metric_value=consecutive,
                    threshold=5,
                    timestamp=trades[0][1] if trades else "unknown",
                    recommendation="Consider pausing trading or reviewing entry criteria"
                ))

        except Exception as e:
            self.log.error(f"Error detecting consecutive losses: {e}")

    def _detect_volatility_spikes(self) -> None:
        """Detect unusual market volatility"""
        if not self.db:
            return

        try:
            query = """
                SELECT symbol, price_volatility, timestamp
                FROM market_snapshots
                WHERE timestamp >= NOW() - INTERVAL '1 hour'
                ORDER BY timestamp DESC
            """
            with self.db.cursor() as cur:
                cur.execute(query)
                snapshots = cur.fetchall()
            
            if len(snapshots) < 5:
                return

            volatilities = [s[1] for s in snapshots if s[1]]
            if volatilities:
                avg_vol = statistics.mean(volatilities)
                std_vol = statistics.stdev(volatilities) if len(volatilities) > 1 else 0
                
                current_vol = volatilities[0]
                threshold = avg_vol + (2 * std_vol)

                if current_vol > threshold:
                    self.anomalies.append(Anomaly(
                        type=AnomalyType.UNUSUAL_VOLATILITY,
                        severity=SeverityLevel.WARNING,
                        description=f"Unusual volatility spike detected",
                        metric_value=current_vol,
                        threshold=threshold,
                        timestamp=snapshots[0][2],
                        recommendation="Consider reducing position sizes or increasing stops"
                    ))

        except Exception as e:
            self.log.error(f"Error detecting volatility: {e}")

    def _detect_margin_issues(self) -> None:
        """Detect margin/leverage issues"""
        if not self.db:
            return

        try:
            query = """
                SELECT equity, used_margin, available
                FROM account_snapshots
                ORDER BY created_at DESC
                LIMIT 1
            """
            with self.db.cursor() as cur:
                cur.execute(query)
                snapshot = cur.fetchone()
            
            if not snapshot:
                return

            equity, used_margin, available = snapshot
            
            if equity > 0:
                margin_ratio = used_margin / equity
                
                if margin_ratio > 0.8:
                    severity = SeverityLevel.CRITICAL if margin_ratio > 0.95 else SeverityLevel.WARNING
                    self.anomalies.append(Anomaly(
                        type=AnomalyType.MARGIN_WARNING,
                        severity=severity,
                        description=f"High margin usage: {margin_ratio:.1%}",
                        metric_value=margin_ratio,
                        threshold=0.8,
                        timestamp="now",
                        recommendation="Reduce position sizes immediately"
                    ))

        except Exception as e:
            self.log.error(f"Error detecting margin issues: {e}")

    def _detect_execution_issues(self) -> None:
        """Detect execution and fill issues"""
        if not self.db:
            return

        try:
            query = """
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN status = 'filled' THEN 1 ELSE 0 END) as filled,
                       AVG(execution_time_ms) as avg_exec_time
                FROM orders
                WHERE created_at >= NOW() - INTERVAL '1 hour'
            """
            with self.db.cursor() as cur:
                cur.execute(query)
                result = cur.fetchone()
            
            if not result or result[0] == 0:
                return

            total, filled, avg_exec_time = result
            fill_rate = filled / total if total > 0 else 0

            if fill_rate < 0.85:
                self.anomalies.append(Anomaly(
                    type=AnomalyType.FILL_RATE_LOW,
                    severity=SeverityLevel.WARNING,
                    description=f"Low fill rate: {fill_rate:.1%}",
                    metric_value=fill_rate,
                    threshold=0.85,
                    timestamp="now",
                    recommendation="Check order sizes and market conditions"
                ))

            if avg_exec_time and avg_exec_time > 1000:  # > 1 second
                self.anomalies.append(Anomaly(
                    type=AnomalyType.EXECUTION_DELAY,
                    severity=SeverityLevel.INFO,
                    description=f"High execution delay: {avg_exec_time:.0f}ms",
                    metric_value=avg_exec_time,
                    threshold=1000,
                    timestamp="now",
                    recommendation="Monitor network latency and API response times"
                ))

        except Exception as e:
            self.log.error(f"Error detecting execution issues: {e}")

    def get_critical_anomalies(self) -> List[Anomaly]:
        """Get only critical severity anomalies"""
        return [a for a in self.anomalies if a.severity == SeverityLevel.CRITICAL]

    def generate_anomaly_report(self) -> str:
        """Generate a formatted anomaly report"""
        anomalies = self.detect_all()
        
        if not anomalies:
            return "✅ No anomalies detected - Bot operating normally\n"

        report = f"""
╔══════════════════════════════════════════════════════════════╗
║              ANOMALY DETECTION REPORT                        ║
║              Status: {len(anomalies)} anomalies detected                  ║
╚══════════════════════════════════════════════════════════════╝

"""
        
        # Sort by severity
        critical = [a for a in anomalies if a.severity == SeverityLevel.CRITICAL]
        warnings = [a for a in anomalies if a.severity == SeverityLevel.WARNING]
        info = [a for a in anomalies if a.severity == SeverityLevel.INFO]

        if critical:
            report += "🚨 CRITICAL ISSUES\n" + "─" * 60 + "\n"
            for anomaly in critical:
                report += f"""
{anomaly.type.value.upper()}
  Current: {anomaly.metric_value:.2f}
  Threshold: {anomaly.threshold:.2f}
  Description: {anomaly.description}
  ⚠️  Action: {anomaly.recommendation}
"""

        if warnings:
            report += "\n⚠️  WARNINGS\n" + "─" * 60 + "\n"
            for anomaly in warnings:
                report += f"""
{anomaly.type.value.upper()}
  Current: {anomaly.metric_value:.2f}
  Threshold: {anomaly.threshold:.2f}
  Description: {anomaly.description}
  📌 Action: {anomaly.recommendation}
"""

        if info:
            report += "\nℹ️  INFO\n" + "─" * 60 + "\n"
            for anomaly in info:
                report += f"{anomaly.type.value.upper()}: {anomaly.description}\n"

        report += "\n" + "═" * 60 + "\n"
        return report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    detector = AnomalyDetector()
    print(detector.generate_anomaly_report())
