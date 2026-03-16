# 🚀 Analyzer - Quick Start Guide

## Installation (Already Done!)

The analyzer has been installed in your Beast Money Maker bot! No additional setup needed.

## 3-Second Start

```bash
python analyze_bot.py
```

That's it! You'll get a comprehensive analysis of your bot's performance.

## Common Commands

```bash
# Full analysis (default - last 30 days)
python analyze_bot.py

# Quick health check (fast)
python analyze_bot.py --quick

# Last 7 days
python analyze_bot.py --days 7

# Save to file
python analyze_bot.py --save

# Save with custom name
python analyze_bot.py --save --output my_analysis.txt
```

## What You'll See

### 1️⃣ Overall Metrics
```
Total Trades: 142
Win Rate: 54.93%
Profit Factor: 2.34x
P&L: $3,245.67
Max Drawdown: 8.42%
```

### 2️⃣ Optimization Suggestions
```
Top 5 parameter changes to improve performance
- EMA_FAST: 9 → 11 (Expected: +5% better entries)
- POSITION_SIZE: 1.0 → 1.5 (Expected: +15% returns)
```

### 3️⃣ Anomaly Alerts
```
🚨 Critical issues detected
⚠️ Warnings
ℹ️ Information
```

### 4️⃣ Daily & Symbol Performance
```
Best day: $245.50
Worst day: -$120.33
Best symbol: BTCUSDT ($850 profit)
```

## What It Analyzes

✅ **Performance Metrics**
- Win/loss statistics
- Profit factor
- Risk-adjusted returns (Sharpe ratio)
- Maximum drawdown

✅ **Anomaly Detection**
- Consecutive losing trades
- Margin warnings
- Unusual volatility
- Execution delays
- Fill rate issues

✅ **Strategy Optimization**
- EMA period suggestions
- ADX threshold calibration
- Position sizing optimization
- Stop loss/take profit levels

## Recommended Usage

| Frequency | Command | Purpose |
|-----------|---------|---------|
| **Daily** | `--quick` | Fast health check |
| **Weekly** | `--days 7 --save` | Weekly review |
| **Monthly** | `--days 30 --save` | Deep analysis |

## Folder Structure

```
your-bot/
├── analyze_bot.py          ← Run this
├── ANALYZER_GUIDE.md       ← Full documentation
├── analysis/               ← Analysis modules
│   ├── performance_analyzer.py
│   ├── anomaly_detector.py
│   ├── strategy_optimizer.py
│   ├── bot_analyzer.py
│   └── README.md
└── reports/                ← Analysis reports saved here
```

## Sample Output

When you run `python analyze_bot.py`, you get:

```
╔══════════════════════════════════════════════════════════════╗
║            🤖 COMPLETE BOT ANALYSIS REPORT 🤖                ║
║              Generated: 2026-03-16 14:30:45                  ║
║              Analysis Period: 30 days                        ║
╚══════════════════════════════════════════════════════════════╝

📊 OVERALL METRICS
────────────────────────────────────────────────────────────
Total Trades:           142
Winning Trades:         78
Losing Trades:          64
Win Rate:               54.93%
Total P&L:              $3,245.67
Profit Factor:          2.34x
Sharpe Ratio:           1.67
Max Drawdown:           8.42%

[... more sections ...]
```

## Integration with Your Bot

### Option 1: Standalone (Easiest)
Just run: `python analyze_bot.py --quick`

### Option 2: In Your Code
```python
from analysis import BotAnalyzer

analyzer = BotAnalyzer(db=db, config=CFG, log=log)
report = analyzer.run_quick_check()
print(report)
```

### Option 3: Automatic Monitoring
See `analysis/integration_examples.py` for:
- Startup checks
- Periodic anomaly detection
- Daily summaries
- Weekly deep analysis

## Files Included

| File | Purpose |
|------|---------|
| `analyze_bot.py` | Command-line tool (run this) |
| `ANALYZER_GUIDE.md` | Complete documentation |
| `analysis/` | All analyzer modules |
| `analysis/README.md` | Detailed API docs |

## First Run

1. **Open terminal**
   ```bash
   cd /Users/joselt/Desktop/beast-money-maker
   ```

2. **Run analyzer**
   ```bash
   python analyze_bot.py --quick
   ```

3. **Review output**
   - Check for critical alerts
   - Note optimization suggestions
   - Save interesting results

4. **For full analysis**
   ```bash
   python analyze_bot.py --save
   ```

## Interpreting Results

### Win Rate Targets
- **< 35%**: Entry logic too loose
- **35-50%**: Conservative and safe
- **50-65%**: Balanced (good target)
- **> 65%**: Aggressive (watch drawdown)

### Profit Factor Targets
- **< 1.0**: Losing money 🚨
- **1.0-1.5**: Barely profitable
- **1.5-2.5**: Good profitability ✅
- **> 2.5**: Excellent profitability

### Sharpe Ratio (Risk-Adjusted)
- **< 0.5**: Very inconsistent
- **0.5-1.0**: Below target
- **1.0+**: Good consistency ✅
- **> 2.0**: Excellent

### Max Drawdown Targets
- **< 5%**: Excellent ✅
- **5-10%**: Good
- **10-15%**: Acceptable
- **> 15%**: Too high 🚨

## Next Steps

1. **Run analysis**: `python analyze_bot.py --save`
2. **Review report**: Check `./reports/` folder
3. **Note suggestions**: Pick top 2-3 to test
4. **Test in paper**: Implement changes carefully
5. **Measure impact**: Re-run after 50+ trades
6. **Iterate**: Keep improving

## Common Questions

**Q: How often should I run analysis?**
A: Daily quick checks (`--quick`), weekly full analysis (`--days 7`).

**Q: Can I improve my bot with this?**
A: Yes! Data-driven suggestions help optimize performance and reduce risk.

**Q: What if my bot is losing?**
A: The analyzer will highlight issues (low win rate, high losses, etc.) and suggest fixes.

**Q: Does it require database?**
A: Yes, your bot's database tracks trades for analysis. Works out of the box.

**Q: Can I use this with live trading?**
A: Yes! The analyzer only reads data, doesn't trade. Use suggestions in paper trading first.

## Troubleshooting

**No data found?**
- Ensure your bot has records in the database
- Run: `python analyze_bot.py --days 7`

**Command not found?**
- Ensure you're in the bot directory
- Try: `python /full/path/to/analyze_bot.py`

**Database error?**
- Check your `.env` file has correct DB credentials
- Ensure PostgreSQL is running

## Support

- **Full docs**: Read `ANALYZER_GUIDE.md`
- **API docs**: Check `analysis/README.md`
- **Code examples**: See `analysis/integration_examples.py`

---

**Ready to analyze your bot?** 

```bash
python analyze_bot.py --quick
```

Go get those insights! 📊🚀
