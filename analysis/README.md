# Bot Analysis Module 📊

Complete analysis suite for the Beast Money Maker trading bot. Provides comprehensive performance tracking, anomaly detection, and strategy optimization suggestions.

## Features

### 🎯 Performance Analyzer
Tracks and analyzes overall trading performance:
- Win/loss statistics and win rate
- Profit factor and Sharpe ratio
- Maximum drawdown analysis
- Daily and symbol-level performance breakdown
- Consecutive loss detection

**Key Metrics:**
- Total trades and win/loss count
- Average win/loss amounts
- Best/worst trade analysis
- Risk-adjusted returns (Sharpe ratio)

### 🚨 Anomaly Detector
Detects unusual patterns and potential risks:
- Consecutive losing trades alert
- Market volatility spikes
- Margin/leverage warnings
- Execution fill rate monitoring
- Unexpected execution delays

**Severity Levels:**
- 🚨 **CRITICAL**: Immediate action required
- ⚠️ **WARNING**: Review and adjust
- ℹ️ **INFO**: Monitor situation

### 🔧 Strategy Optimizer
Suggests parameter optimizations based on actual performance:
- EMA period optimization
- ADX threshold calibration
- Optimal position sizing
- Stop loss and take profit levels
- Confidence-based recommendations

**Output Includes:**
- Current vs. recommended values
- Valid parameter ranges
- Expected improvements
- Confidence percentages

### 🤖 Master Analyzer
Orchestrates all analysis modules:
- Run complete analysis with all components
- Quick health checks
- Actionable recommendations
- Report generation and file saving

## Usage

### Command-Line Interface

#### Full Analysis (Default)
```bash
python analyze_bot.py
```
Analyzes last 30 days of trading data and generates comprehensive report.

#### Quick Health Check
```bash
python analyze_bot.py --quick
```
Fast check for critical issues without full analysis.

#### Custom Time Period
```bash
python analyze_bot.py --days 7
```
Analyze specific number of days (e.g., last 7 days).

#### Save Report to File
```bash
python analyze_bot.py --save
```
Generates report and saves to `./reports/` directory.

#### Custom Output Filename
```bash
python analyze_bot.py --save --output my_analysis.txt
```

### Python API

#### Import Analyzer
```python
from analysis import BotAnalyzer
from db import Database

db = Database()
analyzer = BotAnalyzer(db=db)
```

#### Run Full Analysis
```python
report = analyzer.run_full_analysis(days=30)
print(report)
```

#### Quick Health Check
```python
quick_report = analyzer.run_quick_check()
print(quick_report)
```

#### Get Actionable Recommendations
```python
recommendations = analyzer.get_actionable_recommendations()
for rec in recommendations:
    print(rec)
```

#### Individual Analyzers

**Performance Analysis:**
```python
from analysis import PerformanceAnalyzer

perf = PerformanceAnalyzer(db=db)
metrics = perf.analyze_trades(days=30)
daily_stats = perf.analyze_daily_performance(days=30)
symbol_stats = perf.analyze_symbol_performance()
```

**Anomaly Detection:**
```python
from analysis import AnomalyDetector

detector = AnomalyDetector(db=db)
anomalies = detector.detect_all()
critical = detector.get_critical_anomalies()
```

**Strategy Optimization:**
```python
from analysis import StrategyOptimizer

optimizer = StrategyOptimizer(db=db, config=config)
optimizations = optimizer.get_all_optimizations(days=30)
report = optimizer.generate_optimization_report()
```

## Output Examples

### Performance Report Section
```
📊 OVERALL METRICS
────────────────────────────────────────────────────────────
Total Trades:           142
Winning Trades:         78
Losing Trades:          64
Win Rate:               54.93%
Total P&L:              $3,245.67
Average Win:            $65.34
Average Loss:           $42.18
Profit Factor:          2.34x
Sharpe Ratio:           1.67
Max Drawdown:           8.42%
```

### Optimization Suggestions
```
🎯 OPTIMIZATION SUGGESTIONS
────────────────────────────────────────────────────────────

1. Position Sizing [Priority: 1]
   Current: 1.0
   Suggested: 1.5
   Reason: High win rate allows for larger positions
   Impact: HIGH
```

### Anomaly Report
```
🚨 CRITICAL ISSUES
────────────────────────────────────────────────────────────

MARGIN_WARNING
  Current: 0.85
  Threshold: 0.80
  Description: High margin usage: 85.0%
  ⚠️  Action: Reduce position sizes immediately
```

## Report Sections

1. **Overall Metrics**: Summary statistics
2. **Optimization Suggestions**: Top 5 parameter changes
3. **Losing Patterns**: Worst symbols, times
4. **Daily Performance**: Best/worst days
5. **Symbol Performance**: Breakdown by traded symbol
6. **Executive Summary**: Key findings and next steps

## Interpretation Guide

### Win Rate Thresholds
- < 35%: Entry logic too loose
- 35-45%: Conservative entries
- 45-55%: Balanced approach
- 55-70%: Aggressive entries (watch for drawdown)
- > 70%: Review for unrealistic positional advantage

### Profit Factor
- < 1.0: Loss-making strategy
- 1.0-1.5: Borderline profitable
- 1.5-2.5: Good profitability
- 2.5-5.0: Excellent profitability
- > 5.0: Check for overfitting or insufficient trades

### Sharpe Ratio
- < 0.5: High volatility relative to returns
- 0.5-1.0: Below target consistency
- 1.0-2.0: Good risk-adjusted returns
- > 2.0: Excellent consistency (check for data errors)

### Max Drawdown
- < 5%: Excellent risk management
- 5-10%: Good risk management
- 10-15%: Acceptable risk
- 15-20%: High risk
- > 20%: Excessive risk, reduce positions

## Database Requirements

Requires the following tables:

**trades**
- id, symbol, entry_price, exit_price, quantity
- entry_time, exit_time, pnl, status

**account_snapshots**
- equity, used_margin, available, created_at

**market_snapshots** (optional)
- symbol, price_volatility, timestamp

**orders** (optional)
- status, execution_time_ms, created_at

## Tips for Best Results

1. **Sufficient Data**: Analyze at least 100+ trades for meaningful statistics
2. **Consistent Period**: Compare same timeframes (e.g., last 30 days)
3. **One Change at a Time**: Test parameter changes individually
4. **Paper Trading**: Test optimizations in simulation before live
5. **Regular Analysis**: Run weekly or biweekly for trend detection
6. **Monitor Anomalies**: Act on critical alerts immediately

## Scheduled Analysis

Add to cron job for automatic analysis:

```bash
# Daily analysis at 21:00 UTC
0 21 * * * cd /path/to/beast-money-maker && python analyze_bot.py --save >> /var/log/bot_analysis.log 2>&1
```

Or add to bot initialization:

```python
from analysis import BotAnalyzer

# Run analysis at bot startup
analyzer = BotAnalyzer(db=db, config=CFG, log=log)
recommendations = analyzer.get_actionable_recommendations()
if recommendations:
    telegram.notify(f"Analysis recommendations: {recommendations}")
```

## Troubleshooting

**No data found error:**
- Ensure database is properly connected
- Check if trades table has records
- Verify time ranges include actual trades

**Low confidence scores:**
- Insufficient trading history
- Parameter values haven't stabilized
- Increase analysis period (--days 60)

**Unexpected anomalies:**
- Check market conditions
- Verify position sizing is appropriate
- Review recent trades for patterns

## Performance Notes

- Analysis processes typically complete in <5 seconds for 30-day periods
- Full analysis with 1000+ trades: <30 seconds
- Reports auto-save to `./reports/` directory
- Log files available in `./logs/analysis.log`

## Future Enhancements

- [ ] Machine learning parameter optimization
- [ ] Trade-by-trade detailed analysis
- [ ] Correlation analysis between symbols
- [ ] API endpoints for dashboard integration
- [ ] Automated alert system
- [ ] Historical comparison tracking
- [ ] Monte Carlo simulation capabilities
