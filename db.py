
import os
from dotenv import load_dotenv
load_dotenv()

import psycopg2
import psycopg2.extras
from psycopg2 import pool
import json
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager


class Database:

    def __init__(self):
        self.pool = pool.ThreadedConnectionPool(
            minconn=2,
            maxconn=10,
            host=os.getenv("DB_HOST"),
            database=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            port=os.getenv("DB_PORT", 5432),
        )

    # ==========================================================
    # CONTEXT MANAGER (manejo seguro de commit / rollback)
    # ==========================================================

    @contextmanager
    def cursor(self):
        conn = self.pool.getconn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                yield cur
            conn.commit()
        finally:
            self.pool.putconn(conn)

    # ==========================================================
    # POSITIONS
    # ==========================================================

    def create_position(self, symbol, side, qty, entry_price, strategy_tag=None):
        with self.cursor() as cur:
            cur.execute("""
                INSERT INTO positions (symbol, side, qty, entry_price, status, strategy_tag)
                VALUES (%s, %s, %s, %s, 'OPEN', %s)
                RETURNING id;
            """, (symbol, side, qty, entry_price, strategy_tag))
            return cur.fetchone()["id"]

    def close_position(self, position_id, exit_price, realized_pnl, close_reason=None):
        with self.cursor() as cur:

            # 1️⃣ actualizar posición
            cur.execute("""
                UPDATE positions
                SET status='CLOSED',
                    exit_price=%s,
                    realized_pnl=%s,
                    closed_at=NOW()
                WHERE id=%s;
            """, (exit_price, realized_pnl, position_id))

            # 2️⃣ desactivar stops
            cur.execute("""
                UPDATE position_stops
                SET is_active=FALSE,
                    canceled_at=NOW()
                WHERE position_id=%s
                AND is_active=TRUE;
            """, (position_id,))

            # 3️⃣ evento histórico
            cur.execute("""
                INSERT INTO position_events (position_id, event_type, payload)
                VALUES (%s,%s,%s);
            """, (
                position_id,
                "CLOSED",
                json.dumps({
                    "exit_price": exit_price,
                    "realized_pnl": realized_pnl,
                    "reason": close_reason
                })
            ))

    def get_open_positions_with_stops(self):
        with self.cursor() as cur:
            cur.execute("""
                SELECT p.id, p.symbol, p.side, p.qty, p.entry_price, p.opened_at,
                    ps.stop_price AS current_stop
                FROM positions p
                LEFT JOIN position_stops ps
                    ON ps.position_id = p.id AND ps.is_active = TRUE
                WHERE p.status = 'OPEN'
                ORDER BY p.opened_at DESC
            """)
            return cur.fetchall()        

    # ==========================================================
    # STOPS (Trailing histórico)
    # ==========================================================

    def deactivate_stops(self, position_id):
        with self.cursor() as cur:
            cur.execute("""
                UPDATE position_stops
                SET is_active=FALSE,
                    canceled_at=NOW()
                WHERE position_id=%s
                AND is_active=TRUE;
            """, (position_id,))

    def create_stop(self, position_id, stop_price, exchange_algo_id):
        with self.cursor() as cur:
            cur.execute("""
                INSERT INTO position_stops
                (position_id, stop_price, exchange_algo_id, is_active)
                VALUES (%s, %s, %s, TRUE)
                RETURNING id;
            """, (position_id, stop_price, exchange_algo_id))
            return cur.fetchone()["id"]

    # ==========================================================
    # ORDERS
    # ==========================================================

    def create_order(
        self,
        position_id,
        symbol,
        side,
        order_type,
        is_reduce_only,
        is_close_position,
        exchange_order_id,
        exchange_algo_id,
        is_algo,
        price,
        stop_price,
        status,
        raw_response
    ):
        with self.cursor() as cur:
            cur.execute("""
                INSERT INTO orders (
                    position_id,
                    symbol,
                    side,
                    order_type,
                    is_reduce_only,
                    is_close_position,
                    exchange_order_id,
                    exchange_algo_id,
                    is_algo,
                    price,
                    stop_price,
                    status,
                    raw_response
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id;
            """, (
                position_id,
                symbol,
                side,
                order_type,
                is_reduce_only,
                is_close_position,
                exchange_order_id,
                exchange_algo_id,
                is_algo,
                price,
                stop_price,
                status,
                json.dumps(raw_response)
            ))
            return cur.fetchone()["id"]

    # ==========================================================
    # BOT STATE (reemplaza save_state)
    # ==========================================================

    def save_state(self, state_dict):
        with self.cursor() as cur:
            cur.execute("""
                INSERT INTO bot_state (id, state_json, updated_at)
                VALUES (1, %s, NOW())
                ON CONFLICT (id)
                DO UPDATE SET
                    state_json = EXCLUDED.state_json,
                    updated_at = NOW();
            """, (json.dumps(state_dict),))

    def load_state(self):
        with self.cursor() as cur:
            cur.execute("SELECT state_json FROM bot_state WHERE id=1;")
            row = cur.fetchone()
            return row["state_json"] if row else {}

    # ==========================================================
    # LOGS
    # ==========================================================

    def log(self, level, symbol, message, context=None):
        with self.cursor() as cur:
            cur.execute("""
                INSERT INTO bot_logs (level, symbol, message, context)
                VALUES (%s,%s,%s,%s);
            """, (
                level,
                symbol,
                message,
                json.dumps(context) if context else None
            ))

    # ==========================================================
    # EQUITY SNAPSHOT
    # ==========================================================

    def save_equity_snapshot(self, total_balance, available_balance, unrealized_pnl):
        with self.cursor() as cur:
            cur.execute("""
                INSERT INTO equity_snapshots
                (total_balance, available_balance, unrealized_pnl)
                VALUES (%s,%s,%s);
            """, (
                total_balance,
                available_balance,
                unrealized_pnl
            ))

    def update_position_qty(self, position_id, new_qty):
        with self.cursor() as cur:
            cur.execute("""
                UPDATE positions
                SET qty=%s
                WHERE id=%s
            """, (new_qty, position_id))

    # ==========================================================
    # DASHBOARD
    # ==========================================================

    def get_dashboard_stats(self):
        with self.cursor() as cur:

            # Open positions
            cur.execute("""
                SELECT COUNT(*) AS open_positions
                FROM positions
                WHERE status = 'OPEN'
            """)
            open_positions = cur.fetchone()["open_positions"]

            # Último equity
            cur.execute("""
                SELECT total_balance
                FROM equity_snapshots
                ORDER BY created_at DESC
                LIMIT 1
            """)
            row = cur.fetchone()
            equity = float(row["total_balance"]) if row else 0

            # PnL diario
            cur.execute("""
                SELECT COALESCE(SUM(realized_pnl),0) AS daily_pnl
                FROM positions
                WHERE status='CLOSED'
                AND closed_at::date = CURRENT_DATE
            """)
            daily_pnl = float(cur.fetchone()["daily_pnl"])

            # Win rate
            cur.execute("""
                SELECT
                    COUNT(*) FILTER (WHERE realized_pnl > 0) AS wins,
                    COUNT(*) FILTER (WHERE status='CLOSED') AS total
                FROM positions
            """)
            row = cur.fetchone()
            wins = row["wins"] or 0
            total = row["total"] or 0
            win_rate = round((wins / total) * 100, 2) if total > 0 else 0

        return {
            "equity": round(equity, 2),
            "open_positions": open_positions,
            "daily_pnl": round(daily_pnl, 2),
            "win_rate": win_rate,
        }
    
    def get_trade_analytics(self, start_date: str = None, end_date: str = None, symbol: str = None):
        """
        Obtiene analytics de trades con filtros opcionales.
        
        Args:
            start_date: 'YYYY-MM-DD' - Fecha inicio (inclusive)
            end_date: 'YYYY-MM-DD' - Fecha fin (inclusive)
            symbol: 'BTCUSDT' - Filtrar por símbolo específico
        """
        with self.cursor() as cur:
            query = """
                SELECT
                    symbol,
                    COUNT(*) AS total_trades,
                    SUM(realized_pnl) AS total_pnl,
                    MAX(realized_pnl) AS best_trade,
                    MIN(realized_pnl) AS worst_trade,
                    AVG(EXTRACT(EPOCH FROM (closed_at - opened_at))/3600) AS avg_hold_hours
                FROM positions
                WHERE status = 'CLOSED'
            """
            params = []
            
            # Agregar filtros dinámicamente
            if start_date:
                query += " AND closed_at >= %s::date"
                params.append(start_date)
            if end_date:
                query += " AND closed_at <= %s::date + INTERVAL '1 day'"
                params.append(end_date)
            if symbol:
                query += " AND symbol = %s"
                params.append(symbol.upper())
            
            query += " GROUP BY symbol ORDER BY total_pnl DESC"
            
            cur.execute(query, params if params else ())
            return cur.fetchall()

    def get_equity_curve(self):
        with self.cursor() as cur:
            cur.execute("""
                SELECT created_at, total_balance
                FROM equity_snapshots
                ORDER BY created_at ASC
            """)
            rows = cur.fetchall()

        return rows

    def get_open_positions(self):
        with self.cursor() as cur:
            cur.execute("""
                SELECT id, symbol, side, qty, entry_price, opened_at
                FROM positions
                WHERE status='OPEN'
                ORDER BY opened_at DESC
            """)
            return cur.fetchall()

    def get_recent_closed_positions(self, limit: int = 10):
        """
        Obtiene posiciones cerradas. 
        Si limit=None, devuelve TODAS (para exportación).
        """
        with self.cursor() as cur:
            query = """
                SELECT 
                    id, symbol, side, entry_price, exit_price,
                    qty, realized_pnl, opened_at, closed_at,
                    (SELECT payload->>'reason' FROM position_events 
                    WHERE position_id = positions.id AND event_type = 'CLOSED'
                    ORDER BY created_at DESC LIMIT 1) as close_reason
                FROM positions
                WHERE status='CLOSED'
                ORDER BY closed_at DESC
            """
            if limit is not None:
                query += " LIMIT %s"
                cur.execute(query, (limit,))
            else:
                cur.execute(query)
            return cur.fetchall()

    def get_recent_logs(self, limit=20):
        with self.cursor() as cur:
            cur.execute("""
                SELECT level, symbol, message, created_at
                FROM bot_logs
                ORDER BY created_at DESC
                LIMIT %s
            """, (limit,))
            return cur.fetchall()

    def get_bot_status(self):
        state = self.load_state()
        return "PAUSED" if state.get("paused") else "RUNNING"

    def get_performance_metrics(self):
        with self.cursor() as cur:
            cur.execute("""
                SELECT
                    SUM(CASE WHEN realized_pnl > 0 THEN realized_pnl ELSE 0 END) as total_wins,
                    SUM(CASE WHEN realized_pnl < 0 THEN realized_pnl ELSE 0 END) as total_losses,
                    AVG(CASE WHEN realized_pnl > 0 THEN realized_pnl END) as avg_win,
                    AVG(CASE WHEN realized_pnl < 0 THEN realized_pnl END) as avg_loss
                FROM positions
                WHERE status='CLOSED'
            """)
            data = cur.fetchone()

        total_wins = data["total_wins"] or 0
        total_losses = abs(data["total_losses"] or 0)

        profit_factor = round(total_wins / total_losses, 2) if total_losses > 0 else 0

        return {
            "profit_factor": profit_factor,
            "avg_win": round(data["avg_win"] or 0, 2),
            "avg_loss": round(data["avg_loss"] or 0, 2),
        }

    def calculate_drawdown(self, equity_curve):
        if not equity_curve:
            return 0.0

        peak = float(equity_curve[0]["total_balance"])
        max_drawdown = 0.0

        for point in equity_curve:
            balance = float(point["total_balance"])

            if balance > peak:
                peak = balance

            drawdown = (peak - balance) / peak

            if drawdown > max_drawdown:
                max_drawdown = drawdown

        return round(max_drawdown * 100, 2)

    def get_drawdown_curve(self, equity_curve):
        if not equity_curve:
            return []

        peak = float(equity_curve[0]["total_balance"])
        drawdown_curve = []

        for point in equity_curve:
            balance = float(point["total_balance"])

            if balance > peak:
                peak = balance

            drawdown = (peak - balance) / peak * 100
            drawdown_curve.append(round(float(drawdown), 2))

        return drawdown_curve

    def get_advanced_metrics(self):
        """Métricas avanzadas de performance"""
        with self.cursor() as cur:
            # 1. Sharpe Ratio (simplificado, asumiendo risk-free rate = 0)
            cur.execute("""
                SELECT 
                    AVG(realized_pnl) as avg_pnl,
                    STDDEV(realized_pnl) as stddev_pnl,
                    COUNT(*) as total_trades
                FROM positions
                WHERE status = 'CLOSED'
            """)
            row = cur.fetchone()
            
            avg_pnl = float(row["avg_pnl"] or 0)
            stddev_pnl = float(row["stddev_pnl"] or 0)
            total_trades = int(row["total_trades"] or 0)
            
            sharpe_ratio = round((avg_pnl / stddev_pnl) * (252 ** 0.5), 2) if stddev_pnl > 0 else 0
            
            # 2. Expectancy (ganancia esperada por trade)
            expectancy = round(avg_pnl, 2)
            
            # 3. Rachas máximas
            cur.execute("""
                SELECT 
                    realized_pnl > 0 as is_win,
                    closed_at
                FROM positions
                WHERE status = 'CLOSED'
                ORDER BY closed_at ASC
            """)
            trades = cur.fetchall()
            
            max_win_streak = 0
            max_loss_streak = 0
            current_win_streak = 0
            current_loss_streak = 0
            
            for trade in trades:
                if trade["is_win"]:
                    current_win_streak += 1
                    current_loss_streak = 0
                    max_win_streak = max(max_win_streak, current_win_streak)
                else:
                    current_loss_streak += 1
                    current_win_streak = 0
                    max_loss_streak = max(max_loss_streak, current_loss_streak)
            
            # 4. Recovery Factor
            performance = self.get_performance_metrics()
            stats = self.get_dashboard_stats()
            
            win_rate = float(stats.get("win_rate", 0) or 0)
            avg_win = float(performance.get("avg_win", 0) or 0)
            total_trades_for_profit = total_trades if total_trades > 0 else 1
            
            net_profit = avg_win * (total_trades_for_profit * (win_rate/100))
            
            equity_curve = self.get_equity_curve()
            max_dd = self.calculate_drawdown(equity_curve)
            
            recovery_factor = round(net_profit / float(max_dd), 2) if float(max_dd) > 0 else 0
            
            # 5. Trading frequency (trades por día en promedio)
            cur.execute("""
                SELECT 
                    MIN(closed_at::date) as first_day,
                    MAX(closed_at::date) as last_day,
                    COUNT(*) as total_trades
                FROM positions
                WHERE status = 'CLOSED'
            """)
            date_row = cur.fetchone()
            
            if date_row and date_row["first_day"] and date_row["last_day"]:
                days_active = (date_row["last_day"] - date_row["first_day"]).days + 1
                trades_per_day = round(total_trades / days_active, 2) if days_active > 0 else 0
            else:
                trades_per_day = 0
            
            return {
                "sharpe_ratio": sharpe_ratio,
                "expectancy": expectancy,
                "max_win_streak": max_win_streak,
                "max_loss_streak": max_loss_streak,
                "recovery_factor": recovery_factor,
                "trades_per_day": trades_per_day,
            }

    def get_risk_reward_stats(self):
        """Estadísticas de riesgo/recompensa por trade"""
        with self.cursor() as cur:
            cur.execute("""
                SELECT 
                    AVG(
                        CASE 
                            WHEN realized_pnl > 0 THEN realized_pnl 
                            ELSE ABS(realized_pnl) 
                        END
                    ) as avg_rr_ratio
                FROM positions
                WHERE status = 'CLOSED'
            """)
            row = cur.fetchone()
            return {
                "avg_win_amount": round(row["avg_rr_ratio"] or 0, 2)
            }

    def get_time_in_market(self):
        """Porcentaje de tiempo con posiciones abiertas"""
        with self.cursor() as cur:
            cur.execute("""
                SELECT 
                    SUM(EXTRACT(EPOCH FROM (closed_at - opened_at))) as total_seconds_in_market,
                    MIN(opened_at) as first_trade,
                    MAX(closed_at) as last_trade
                FROM positions
                WHERE status = 'CLOSED'
            """)
            row = cur.fetchone()
            
            if not row or not row["first_trade"] or not row["last_trade"]:
                return {"time_in_market_pct": 0}
            
            total_period = float((row["last_trade"] - row["first_trade"]).total_seconds())
            time_in_market = float(row["total_seconds_in_market"] or 0)
            
            time_in_market_pct = round((time_in_market / total_period) * 100, 2) if total_period > 0 else 0
            
            return {
                "time_in_market_pct": min(time_in_market_pct, 100)  # Cap en 100%
            }
            
    # ==========================================================
    # POSITIONS EVENTS
    # ==========================================================

    def create_position_event(self, position_id, event_type, payload=None):
        with self.cursor() as cur:
            cur.execute("""
                INSERT INTO position_events (position_id, event_type, payload)
                VALUES (%s,%s,%s);
            """, (
                position_id,
                event_type,
                json.dumps(payload) if payload else None
            ))

    def get_position_by_id(self, position_id):
        with self.cursor() as cur:
            cur.execute("""
                SELECT *
                FROM positions
                WHERE id = %s
                LIMIT 1;
            """, (position_id,))

            row = cur.fetchone()

            if not row:
                return None

            return row        

    def save_account_snapshot(self, equity, used_margin, available):
        with self.cursor() as cur:
            cur.execute("""
                INSERT INTO account_snapshots
                (equity, used_margin, available)
                VALUES (%s, %s, %s);
            """, (
                equity,
                used_margin,
                available
            ))

    def get_latest_account_snapshot(self):
        with self.cursor() as cur:
            cur.execute("""
                SELECT equity, used_margin, available
                FROM account_snapshots
                ORDER BY created_at DESC
                LIMIT 1
            """)
            row = cur.fetchone()

            if not row:
                return None

            return {
                "equity": float(row["equity"]),
                "used_margin": float(row["used_margin"]),
                "available": float(row["available"])
            }

    def get_closed_positions_filtered(self, start_date: str = None, end_date: str = None, symbol: str = None):
        """Versión filtrada para exportación"""
        with self.cursor() as cur:
            query = """
                SELECT 
                    id, symbol, side, qty, entry_price, exit_price,
                    realized_pnl, opened_at, closed_at,
                    (SELECT payload->>'reason' FROM position_events 
                    WHERE position_id = positions.id AND event_type = 'CLOSED'
                    ORDER BY created_at DESC LIMIT 1) as close_reason
                FROM positions
                WHERE status = 'CLOSED'
            """
            params = []
            
            if start_date:
                query += " AND closed_at >= %s"
                params.append(start_date)
            if end_date:
                query += " AND closed_at <= %s"
                params.append(end_date)
            if symbol:
                query += " AND symbol = %s"
                params.append(symbol.upper())
            
            query += " ORDER BY closed_at DESC"
            
            cur.execute(query, params if params else ())
            return cur.fetchall()        