"""
repository.py - Persistence layer for Zebio paper trading.

Uses SQLite with WAL mode for durability and concurrent reads.
Single-statement writes remain autocommit by default, while
multi-step position opening and closing use explicit transactions so
position state, trade history, and portfolio cash remain consistent.
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

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(
            self.db_path,
            isolation_level=None,
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
            conn.executescript(
                SCHEMA_PATH.read_text()
            )

    def get_portfolio(
        self,
        name: str,
    ) -> dict[str, Any] | None:
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
                  (
                    name,
                    initial_capital,
                    currency,
                    cash,
                    equity,
                    starting_date,
                    created_at,
                    updated_at
                  )
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
                   SET cash = ?,
                       equity = ?,
                       updated_at = ?
                 WHERE name = ?
                """,
                (
                    float(cash),
                    float(equity),
                    _utcnow_iso(),
                    name,
                ),
            )

    def open_position(
        self,
        portfolio_id: int,
        ticker: str,
        quantity: float,
        entry_price: float,
        predicted_return: float | None = None,
        signal: str | None = None,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        entry_time: str | None = None,
    ) -> dict[str, Any]:
        """
        Open a new long paper position and deduct its cost from cash.

        The position insert and portfolio cash update are committed
        atomically. Equity is unchanged because the position is opened
        at its current entry price.
        """

        normalized_ticker = ticker.strip().upper()

        if not normalized_ticker:
            raise ValueError(
                "Ticker must not be empty."
            )

        if quantity <= 0:
            raise ValueError(
                "Position quantity must be greater than zero."
            )

        if entry_price <= 0:
            raise ValueError(
                "Entry price must be greater than zero."
            )

        position_cost = (
            float(quantity)
            * float(entry_price)
        )

        timestamp = (
            entry_time
            or _utcnow_iso()
        )

        with self._conn() as conn:
            conn.execute("BEGIN IMMEDIATE")

            try:
                portfolio = conn.execute(
                    """
                    SELECT id, cash, equity
                      FROM paper_portfolio
                     WHERE id = ?
                    """,
                    (portfolio_id,),
                ).fetchone()

                if portfolio is None:
                    raise ValueError(
                        f"Paper portfolio with id "
                        f"{portfolio_id} not found."
                    )

                existing = conn.execute(
                    """
                    SELECT id
                      FROM paper_positions
                     WHERE portfolio_id = ?
                       AND ticker = ?
                       AND status = 'OPEN'
                    """,
                    (
                        portfolio_id,
                        normalized_ticker,
                    ),
                ).fetchone()

                if existing is not None:
                    raise ValueError(
                        f"An open position already exists "
                        f"for {normalized_ticker}."
                    )

                current_cash = float(
                    portfolio["cash"]
                )

                if position_cost > current_cash:
                    raise ValueError(
                        f"Insufficient cash to open "
                        f"{normalized_ticker}: "
                        f"required={position_cost:.2f}, "
                        f"available={current_cash:.2f}."
                    )

                new_cash = (
                    current_cash
                    - position_cost
                )

                cursor = conn.execute(
                    """
                    INSERT INTO paper_positions
                      (
                        portfolio_id,
                        ticker,
                        side,
                        quantity,
                        entry_price,
                        entry_time,
                        stop_loss,
                        take_profit,
                        predicted_return,
                        signal,
                        status
                      )
                    VALUES (
                        ?,
                        ?,
                        'LONG',
                        ?,
                        ?,
                        ?,
                        ?,
                        ?,
                        ?,
                        ?,
                        'OPEN'
                    )
                    """,
                    (
                        portfolio_id,
                        normalized_ticker,
                        float(quantity),
                        float(entry_price),
                        timestamp,
                        stop_loss,
                        take_profit,
                        predicted_return,
                        signal,
                    ),
                )

                conn.execute(
                    """
                    UPDATE paper_portfolio
                       SET cash = ?,
                           updated_at = ?
                     WHERE id = ?
                    """,
                    (
                        new_cash,
                        _utcnow_iso(),
                        portfolio_id,
                    ),
                )

                conn.execute("COMMIT")

                return {
                    "position_id": int(
                        cursor.lastrowid
                    ),
                    "portfolio_id": portfolio_id,
                    "ticker": normalized_ticker,
                    "side": "LONG",
                    "quantity": float(quantity),
                    "entry_price": float(entry_price),
                    "position_cost": position_cost,
                    "cash_before": current_cash,
                    "cash_after": new_cash,
                    "equity": float(
                        portfolio["equity"]
                    ),
                    "entry_time": timestamp,
                    "predicted_return": predicted_return,
                    "signal": signal,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "status": "OPEN",
                }

            except Exception:
                conn.execute("ROLLBACK")
                raise

    def close_position(
        self,
        position_id: int,
        exit_price: float,
        exit_reason: str,
        exit_time: str | None = None,
        fees: float = 0.0,
    ) -> dict[str, Any]:
        """
        Close an existing long paper position.

        The operation atomically:

            1. reads the open position
            2. validates the exit price and fees
            3. calculates realised P&L
            4. records the completed trade
            5. marks the position CLOSED
            6. returns sale proceeds to portfolio cash

        Portfolio equity is unchanged by the transaction itself because
        the position's market value is converted into cash at the supplied
        exit price.

        Fees are treated as exit transaction costs.
        """

        if exit_price <= 0:
            raise ValueError(
                "Exit price must be greater than zero."
            )

        if fees < 0:
            raise ValueError(
                "Fees must be greater than or equal to zero."
            )

        normalized_reason = (
            exit_reason.strip()
        )

        if not normalized_reason:
            raise ValueError(
                "Exit reason must not be empty."
            )

        timestamp = (
            exit_time
            or _utcnow_iso()
        )

        with self._conn() as conn:
            conn.execute("BEGIN IMMEDIATE")

            try:
                position = conn.execute(
                    """
                    SELECT
                        id,
                        portfolio_id,
                        ticker,
                        side,
                        quantity,
                        entry_price,
                        entry_time,
                        stop_loss,
                        take_profit,
                        predicted_return,
                        signal,
                        status
                    FROM paper_positions
                    WHERE id = ?
                    """,
                    (position_id,),
                ).fetchone()

                if position is None:
                    raise ValueError(
                        f"Paper position "
                        f"{position_id} not found."
                    )

                if position["status"] != "OPEN":
                    raise ValueError(
                        f"Paper position "
                        f"{position_id} is not open."
                    )

                if position["side"] != "LONG":
                    raise ValueError(
                        f"Unsupported paper position side: "
                        f"{position['side']}."
                    )

                quantity = float(
                    position["quantity"]
                )

                entry_price = float(
                    position["entry_price"]
                )

                if quantity <= 0:
                    raise ValueError(
                        f"Invalid quantity for position "
                        f"{position_id}: {quantity}."
                    )

                if entry_price <= 0:
                    raise ValueError(
                        f"Invalid entry price for position "
                        f"{position_id}: {entry_price}."
                    )

                portfolio = conn.execute(
                    """
                    SELECT id, cash, equity
                      FROM paper_portfolio
                     WHERE id = ?
                    """,
                    (
                        int(
                            position["portfolio_id"]
                        ),
                    ),
                ).fetchone()

                if portfolio is None:
                    raise ValueError(
                        f"Paper portfolio with id "
                        f"{position['portfolio_id']} not found."
                    )

                current_cash = float(
                    portfolio["cash"]
                )

                entry_value = (
                    quantity
                    * entry_price
                )

                gross_exit_value = (
                    quantity
                    * float(exit_price)
                )

                realised_pnl = (
                    gross_exit_value
                    - entry_value
                    - float(fees)
                )

                pnl_pct = (
                    realised_pnl / entry_value
                    if entry_value
                    else 0.0
                )

                entry_dt = datetime.fromisoformat(
                    str(position["entry_time"])
                )

                exit_dt = datetime.fromisoformat(
                    timestamp
                )

                holding_seconds = max(
                    0,
                    int(
                        (
                            exit_dt
                            - entry_dt
                        ).total_seconds()
                    ),
                )

                cash_after = (
                    current_cash
                    + gross_exit_value
                    - float(fees)
                )

                trade_cursor = conn.execute(
                    """
                    INSERT INTO paper_trades
                      (
                        portfolio_id,
                        ticker,
                        side,
                        quantity,
                        entry_price,
                        exit_price,
                        entry_time,
                        exit_time,
                        predicted_return,
                        signal,
                        realised_pnl,
                        pnl_pct,
                        exit_reason,
                        holding_seconds,
                        fees,
                        created_at
                      )
                    VALUES (
                        ?,
                        ?,
                        ?,
                        ?,
                        ?,
                        ?,
                        ?,
                        ?,
                        ?,
                        ?,
                        ?,
                        ?,
                        ?,
                        ?,
                        ?,
                        ?
                    )
                    """,
                    (
                        int(
                            position["portfolio_id"]
                        ),
                        str(
                            position["ticker"]
                        ),
                        str(
                            position["side"]
                        ),
                        quantity,
                        entry_price,
                        float(exit_price),
                        str(
                            position["entry_time"]
                        ),
                        timestamp,
                        position["predicted_return"],
                        position["signal"],
                        realised_pnl,
                        pnl_pct,
                        normalized_reason,
                        holding_seconds,
                        float(fees),
                        _utcnow_iso(),
                    ),
                )

                conn.execute(
                    """
                    UPDATE paper_positions
                       SET status = 'CLOSED'
                     WHERE id = ?
                       AND status = 'OPEN'
                    """,
                    (position_id,),
                )

                if conn.execute(
                    """
                    SELECT changes()
                    """
                ).fetchone()[0] != 1:
                    raise RuntimeError(
                        f"Paper position "
                        f"{position_id} could not be closed."
                    )

                conn.execute(
                    """
                    UPDATE paper_portfolio
                       SET cash = ?,
                           updated_at = ?
                     WHERE id = ?
                    """,
                    (
                        cash_after,
                        _utcnow_iso(),
                        int(
                            position["portfolio_id"]
                        ),
                    ),
                )

                conn.execute("COMMIT")

                return {
                    "trade_id": int(
                        trade_cursor.lastrowid
                    ),
                    "position_id": position_id,
                    "portfolio_id": int(
                        position["portfolio_id"]
                    ),
                    "ticker": str(
                        position["ticker"]
                    ),
                    "side": str(
                        position["side"]
                    ),
                    "quantity": quantity,
                    "entry_price": entry_price,
                    "exit_price": float(exit_price),
                    "entry_value": entry_value,
                    "gross_exit_value": gross_exit_value,
                    "fees": float(fees),
                    "realised_pnl": realised_pnl,
                    "pnl_pct": pnl_pct,
                    "exit_reason": normalized_reason,
                    "holding_seconds": holding_seconds,
                    "entry_time": str(
                        position["entry_time"]
                    ),
                    "exit_time": timestamp,
                    "cash_before": current_cash,
                    "cash_after": cash_after,
                    "predicted_return": position[
                        "predicted_return"
                    ],
                    "signal": position["signal"],
                    "stop_loss": position["stop_loss"],
                    "take_profit": position["take_profit"],
                    "status": "CLOSED",
                }

            except Exception:
                conn.execute("ROLLBACK")
                raise

    def open_positions(
        self,
        portfolio_id: int,
    ) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT *
                  FROM paper_positions
                 WHERE portfolio_id = ?
                   AND status = 'OPEN'
                 ORDER BY entry_time ASC
                """,
                (portfolio_id,),
            ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    def recent_trades(
        self,
        portfolio_id: int,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT *
                  FROM paper_trades
                 WHERE portfolio_id = ?
                 ORDER BY exit_time DESC
                 LIMIT ?
                """,
                (
                    portfolio_id,
                    limit,
                ),
            ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    def trade_count(
        self,
        portfolio_id: int,
    ) -> int:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS n
                  FROM paper_trades
                 WHERE portfolio_id = ?
                """,
                (portfolio_id,),
            ).fetchone()

        return int(
            row["n"]
        ) if row else 0

    def equity_curve(
        self,
        portfolio_id: int,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT
                    date,
                    equity,
                    cash,
                    unrealised_pnl,
                    realised_pnl_day,
                    cumulative_pnl,
                    drawdown,
                    trade_count
                FROM paper_daily_snapshots
                WHERE portfolio_id = ?
                ORDER BY date ASC
                LIMIT ?
                """,
                (
                    portfolio_id,
                    limit,
                ),
            ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

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
                  (
                    portfolio_id,
                    date,
                    equity,
                    cash,
                    unrealised_pnl,
                    realised_pnl_day,
                    cumulative_pnl,
                    drawdown,
                    trade_count
                  )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (
                    portfolio_id,
                    date
                )
                DO UPDATE SET
                    equity = excluded.equity,
                    cash = excluded.cash,
                    unrealised_pnl = excluded.unrealised_pnl,
                    realised_pnl_day = excluded.realised_pnl_day,
                    cumulative_pnl = excluded.cumulative_pnl,
                    drawdown = excluded.drawdown,
                    trade_count = excluded.trade_count
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