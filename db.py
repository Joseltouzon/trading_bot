
import os
from dotenv import load_dotenv
load_dotenv()

import psycopg2
import psycopg2.extras
import json
from contextlib import contextmanager


class Database:

    def __init__(self):
        self.conn = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            database=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD")
        )
        self.conn.autocommit = False  # control total de transacciones

    # ==========================================================
    # CONTEXT MANAGER (manejo seguro de commit / rollback)
    # ==========================================================

    @contextmanager
    def cursor(self):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            yield cur
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        finally:
            cur.close()

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

    def close_position(self, position_id, exit_price, realized_pnl):
        with self.cursor() as cur:
            cur.execute("""
                UPDATE positions
                SET status='CLOSED',
                    exit_price=%s,
                    realized_pnl=%s,
                    closed_at=NOW()
                WHERE id=%s;
            """, (exit_price, realized_pnl, position_id))

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
