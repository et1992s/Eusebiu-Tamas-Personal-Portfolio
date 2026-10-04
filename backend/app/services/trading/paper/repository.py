"""
repository.py - Persistence layer for Zebio paper trading.

Uses SQLite with WAL mode for durability and concurrent reads.
All writes are single-statement (autocommit) which is sufficient
for the throughput this system will see (a few trades per day).
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_PATH = Path(__file__).parent / "schema.sql"
DEFAULT_DB_PATH = Path("data") / "paper_trading.sqlite"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class PaperRepository:
    def __init__(self, db_path: Path = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    # ──────────────────────────────────────────────────
    # Connection
    # ──────────────────────────────────────────────────

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(
            self.db_path,
            isolation_level=None,  # autocommit
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
        finally:
            conn.close()

    def _ensure_schema(self) -> None:
        with self._conn() as conn:
            conn.executescript(SCHEMA_PATH.read_text())

    # ──────────────────────────────────────────────────
    # Portfolio
    # ──────────────────────────────────────────────────

    def get_portfolio(self, name: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM paper_portfolio WHERE name = ?",
                (name,),
            ).fetchone()
        return dict(row) if row else None

    def create_portfolio(
        self,
        name: str,
        initial_capital: float,
        currency: str = "GBP",
        starting_date: str | None = None,
    ) -> None:
        now = _utcnow_iso()
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO paper_portfolio
                  (name, initial_capital, currency, cash, equity,
                   starting_date, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name,
                    float(initial_capital),
                    currency,
                    float(initial_capital),
                    float(initial_capital),
                    starting_date or now[:10],
                    now,
                    now,
                ),
            )

    def update_portfolio_equity(
        self,
        name: str,
        cash: float,
        equity: float,
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE paper_portfolio
                   SET cash = ?, equity = ?, updated_at = ?
                 WHERE name = ?
                """,
                (float(cash), float(equity), _utcnow_iso(), name),
            )

    # ──────────────────────────────────────────────────
    # Open positions
    # ──────────────────────────────────────────────────

    def open_positions(self, portfolio_id: int) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM paper_positions
                 WHERE portfolio_id = ? AND status = 'OPEN'
                 ORDER BY entry_time ASC
                """,
                (portfolio_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ──────────────────────────────────────────────────
    # Closed trades (journal)
    # ──────────────────────────────────────────────────

    def recent_trades(
        self,
        portfolio_id: int,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM paper_trades
                 WHERE portfolio_id = ?
                 ORDER BY exit_time DESC
                 LIMIT ?
                """,
                (portfolio_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def trade_count(self, portfolio_id: int) -> int:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM paper_trades WHERE portfolio_id = ?",
                (portfolio_id,),
            ).fetchone()
        return int(row["n"]) if row else 0

    # ──────────────────────────────────────────────────
    # Daily snapshots (equity curve)
    # ──────────────────────────────────────────────────

    def equity_curve(
        self,
        portfolio_id: int,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT date, equity, cash, unrealised_pnl,
                       realised_pnl_day, cumulative_pnl,
                       drawdown, trade_count
                  FROM paper_daily_snapshots
                 WHERE portfolio_id = ?
                 ORDER BY date ASC
                 LIMIT ?
                """,
                (portfolio_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def upsert_snapshot(
        self,
        portfolio_id: int,
        date: str,
        equity: float,
        cash: float,
        unrealised_pnl: float,
        realised_pnl_day: float,
        cumulative_pnl: float,
        drawdown: float,
        trade_count: int,
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO paper_daily_snapshots
                  (portfolio_id, date, equity, cash, unrealised_pnl,
                   realised_pnl_day, cumulative_pnl, drawdown, trade_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (portfolio_id, date) DO UPDATE SET
                  equity           = excluded.equity,
                  cash             = excluded.cash,
                  unrealised_pnl   = excluded.unrealised_pnl,
                  realised_pnl_day = excluded.realised_pnl_day,
                  cumulative_pnl   = excluded.cumulative_pnl,
                  drawdown         = excluded.drawdown,
                  trade_count      = excluded.trade_count
                """,
                (
                    portfolio_id,
                    date,
                    float(equity),
                    float(cash),
                    float(unrealised_pnl),
                    float(realised_pnl_day),
                    float(cumulative_pnl),
                    float(drawdown),
                    int(trade_count),
                ),
            )