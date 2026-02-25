import time

class DashboardService:
    _stats_cache = None
    _stats_cache_time = 0
    _cache_ttl = 10  # segundos

    def __init__(self, db, exchange_cache):
        self.db = db
        self.exchange_cache = exchange_cache

    def build_dashboard_context(self):

        now = time.time()
        if (
            not DashboardService._stats_cache or
            now - DashboardService._stats_cache_time > DashboardService._cache_ttl
        ):
            DashboardService._stats_cache = self.db.get_dashboard_stats()
            DashboardService._stats_cache_time = now
        stats = DashboardService._stats_cache
        
        equity_curve = self.db.get_equity_curve() or []
        closed_positions = self.db.get_recent_closed_positions()
        logs = self.db.get_recent_logs()
        bot_status = self.db.get_bot_status()
        performance = self.db.get_performance_metrics()
        analytics = self.db.get_trade_analytics()
        state = self.db.load_state() or {}
        open_positions = self.db.get_open_positions_with_stops() or []

        # Unrealized desde exchange
        exchange_positions = self.exchange_cache.get_open_positions()
        exchange_map = {p["symbol"]: p for p in exchange_positions}

        for pos in open_positions:
            pos["unrealized_pnl"] = float(
                exchange_map.get(pos["symbol"], {}).get("unrealized_pnl", 0)
            )

        account = self.db.get_latest_account_snapshot() or {
            "equity": 0,
            "used_margin": 0,
            "available": 0
        }

        usage_pct = (
            round((account["used_margin"] / account["equity"]) * 100, 2)
            if account["equity"] > 0 else 0
        )

        # Formateo equity
        for e in equity_curve:
            e["created_at"] = e["created_at"].strftime("%H:%M")
            e["total_balance"] = float(e["total_balance"])

        max_drawdown = self.db.calculate_drawdown(equity_curve)
        drawdown_curve = self.db.get_drawdown_curve(equity_curve)

        return {
            "stats": stats,
            "equity_curve": equity_curve,
            "open_positions": open_positions,
            "closed_positions": closed_positions,
            "logs": logs,
            "bot_status": bot_status,
            "performance": performance,
            "max_drawdown": max_drawdown,
            "drawdown_curve": drawdown_curve,
            "state": state,
            "account": account,
            "usage_pct": usage_pct,
            "analytics": analytics
        }