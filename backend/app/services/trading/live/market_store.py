"""
market_store.py - Persistent market-data storage for Zebio.

Stores canonical 1-minute OHLCV market bars independently from
Zebio's engineering-memory database.

Architecture:

    MarketDataProvider
            |
            v
      MarketDataStore
            |
            v
      market_data.db

The store deliberately contains no chart-timeframe logic. It persists
canonical market bars and provides historical/session retrieval for
higher-level trading services.
"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd


CANONICAL_COLUMNS = [
    "first",
    "high",
    "low",
    "last",
    "volume",
]


SCHEMA = """
CREATE TABLE IF NOT EXISTS market_bars (
    ticker TEXT NOT NULL,
    asset_class TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    first REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    last REAL NOT NULL,
    volume INTEGER NOT NULL,
    source TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    PRIMARY KEY (
        ticker,
        asset_class,
        timestamp
    )
);

CREATE INDEX IF NOT EXISTS idx_market_bars_ticker_timestamp
ON market_bars (
    ticker,
    asset_class,
    timestamp DESC
);

CREATE INDEX IF NOT EXISTS idx_market_bars_timestamp
ON market_bars (
    timestamp DESC
);
"""


class MarketDataStore:
    """
    SQLite-backed persistent store for canonical market bars.

    The store is intentionally independent from Zebio's MemoryStore.
    Market data can grow considerably and has a different lifecycle
    from AI engineering memory.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)

        Path(self.path).parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._lock = threading.Lock()

        self._init_schema()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(
            self.path,
            isolation_level=None,
            timeout=30,
        )

        conn.row_factory = sqlite3.Row

        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=30000")

        try:
            yield conn
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._lock, self._conn() as conn:
            conn.executescript(SCHEMA)

    @staticmethod
    def _normalise_timestamp(timestamp) -> str:
        value = pd.Timestamp(timestamp)

        if value.tzinfo is None:
            value = value.tz_localize("UTC")
        else:
            value = value.tz_convert("UTC")

        return value.isoformat()

    @staticmethod
    def _normalise_bars(
        bars: pd.DataFrame,
    ) -> pd.DataFrame:
        if bars is None:
            return pd.DataFrame(
                columns=CANONICAL_COLUMNS,
                index=pd.DatetimeIndex(
                    [],
                    name="timestamp",
                ),
            )

        if not isinstance(bars, pd.DataFrame):
            raise TypeError(
                "Market data must be provided as a pandas DataFrame."
            )

        missing = [
            column
            for column in CANONICAL_COLUMNS
            if column not in bars.columns
        ]

        if missing:
            raise ValueError(
                "Market data is missing required columns: "
                f"{missing}"
            )

        if not isinstance(
            bars.index,
            pd.DatetimeIndex,
        ):
            raise ValueError(
                "Market data must use a DatetimeIndex."
            )

        if bars.empty:
            return pd.DataFrame(
                columns=CANONICAL_COLUMNS,
                index=pd.DatetimeIndex(
                    [],
                    name="timestamp",
                ),
            )

        normalised = bars[
            CANONICAL_COLUMNS
        ].copy()

        normalised.index = pd.to_datetime(
            normalised.index,
            utc=True,
        )

        normalised.index.name = "timestamp"

        normalised = normalised.sort_index()

        normalised = normalised[
            ~normalised.index.duplicated(
                keep="last",
            )
        ]

        return normalised

    @staticmethod
    def _now() -> str:
        return datetime.now(
            timezone.utc,
        ).isoformat()

    def save_bars(
        self,
        ticker: str,
        bars: pd.DataFrame,
        asset_class: str = "stocks",
        source: str = "alpaca",
    ) -> int:
        """
        Insert or update canonical market bars.

        Returns the number of bars processed.
        """

        normalized_ticker = ticker.upper().strip()

        if not normalized_ticker:
            raise ValueError(
                "Ticker must not be empty."
            )

        normalized_asset_class = (
            asset_class.lower().strip()
        )

        if not normalized_asset_class:
            raise ValueError(
                "Asset class must not be empty."
            )

        normalized_source = source.strip()

        if not normalized_source:
            raise ValueError(
                "Source must not be empty."
            )

        normalized_bars = self._normalise_bars(
            bars,
        )

        if normalized_bars.empty:
            return 0

        now = self._now()

        rows = []

        for timestamp, row in normalized_bars.iterrows():
            rows.append(
                (
                    normalized_ticker,
                    normalized_asset_class,
                    self._normalise_timestamp(timestamp),
                    float(row["first"]),
                    float(row["high"]),
                    float(row["low"]),
                    float(row["last"]),
                    int(row["volume"]),
                    normalized_source,
                    now,
                    now,
                )
            )

        sql = """
        INSERT INTO market_bars (
            ticker,
            asset_class,
            timestamp,
            first,
            high,
            low,
            last,
            volume,
            source,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (
            ticker,
            asset_class,
            timestamp
        )
        DO UPDATE SET
            first = excluded.first,
            high = excluded.high,
            low = excluded.low,
            last = excluded.last,
            volume = excluded.volume,
            source = excluded.source,
            updated_at = excluded.updated_at
        """

        with self._lock, self._conn() as conn:
            conn.executemany(
                sql,
                rows,
            )

        return len(rows)

    def get_latest_bars(
        self,
        ticker: str,
        limit: int = 100,
        asset_class: str = "stocks",
    ) -> pd.DataFrame:
        """
        Return the most recent persisted bars for a ticker.

        Results are returned chronologically ascending.
        """

        normalized_ticker = ticker.upper().strip()

        if not normalized_ticker:
            raise ValueError(
                "Ticker must not be empty."
            )

        if limit <= 0:
            return self._empty_bars()

        normalized_asset_class = (
            asset_class.lower().strip()
        )

        sql = """
        SELECT
            timestamp,
            first,
            high,
            low,
            last,
            volume
        FROM market_bars
        WHERE ticker = ?
          AND asset_class = ?
        ORDER BY timestamp DESC
        LIMIT ?
        """

        with self._conn() as conn:
            rows = conn.execute(
                sql,
                (
                    normalized_ticker,
                    normalized_asset_class,
                    limit,
                ),
            ).fetchall()

        if not rows:
            return self._empty_bars()

        data = [
            {
                "timestamp": row["timestamp"],
                "first": row["first"],
                "high": row["high"],
                "low": row["low"],
                "last": row["last"],
                "volume": row["volume"],
            }
            for row in rows
        ]

        frame = pd.DataFrame(data)

        frame["timestamp"] = pd.to_datetime(
            frame["timestamp"],
            utc=True,
        )

        frame = frame.set_index(
            "timestamp",
        )

        frame.index.name = "timestamp"

        return frame[
            CANONICAL_COLUMNS
        ].sort_index()

    def get_latest_timestamp(
        self,
        ticker: str,
        asset_class: str = "stocks",
    ) -> pd.Timestamp | None:
        """
        Return the latest persisted timestamp for a ticker.
        """

        normalized_ticker = ticker.upper().strip()

        if not normalized_ticker:
            raise ValueError(
                "Ticker must not be empty."
            )

        normalized_asset_class = (
            asset_class.lower().strip()
        )

        sql = """
        SELECT MAX(timestamp)
        FROM market_bars
        WHERE ticker = ?
          AND asset_class = ?
        """

        with self._conn() as conn:
            row = conn.execute(
                sql,
                (
                    normalized_ticker,
                    normalized_asset_class,
                ),
            ).fetchone()

        if row is None or row[0] is None:
            return None

        return pd.Timestamp(
            row[0],
        ).tz_convert("UTC")

    def get_latest_session(
        self,
        ticker: str,
        asset_class: str = "stocks",
        limit: int = 100,
    ) -> pd.DataFrame:
        """
        Return bars belonging to the most recently persisted
        market session for a ticker.

        The latest session is determined from the persisted data.
        No weekday or calendar assumptions are made.
        """

        normalized_ticker = ticker.upper().strip()

        if not normalized_ticker:
            raise ValueError(
                "Ticker must not be empty."
            )

        if limit <= 0:
            return self._empty_bars()

        normalized_asset_class = (
            asset_class.lower().strip()
        )

        latest_timestamp_sql = """
        SELECT MAX(timestamp)
        FROM market_bars
        WHERE ticker = ?
          AND asset_class = ?
        """

        with self._conn() as conn:
            latest_row = conn.execute(
                latest_timestamp_sql,
                (
                    normalized_ticker,
                    normalized_asset_class,
                ),
            ).fetchone()

            if (
                latest_row is None
                or latest_row[0] is None
            ):
                return self._empty_bars()

            latest_timestamp = pd.Timestamp(
                latest_row[0],
            )

            if latest_timestamp.tzinfo is None:
                latest_timestamp = (
                    latest_timestamp.tz_localize("UTC")
                )
            else:
                latest_timestamp = (
                    latest_timestamp.tz_convert("UTC")
                )

            local_timestamp = latest_timestamp.tz_convert(
                "America/New_York"
            )

            session_start_local = local_timestamp.normalize()
            session_end_local = (
                session_start_local
                + pd.Timedelta(days=1)
            )

            session_start_utc = (
                session_start_local
                .tz_convert("UTC")
            )

            session_end_utc = (
                session_end_local
                .tz_convert("UTC")
            )

            session_rows = conn.execute(
                """
                SELECT
                    timestamp,
                    first,
                    high,
                    low,
                    last,
                    volume
                FROM market_bars
                WHERE ticker = ?
                  AND asset_class = ?
                  AND timestamp >= ?
                  AND timestamp < ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (
                    normalized_ticker,
                    normalized_asset_class,
                    session_start_utc.isoformat(),
                    session_end_utc.isoformat(),
                    limit,
                ),
            ).fetchall()

        if not session_rows:
            return self._empty_bars()

        data = [
            {
                "timestamp": row["timestamp"],
                "first": row["first"],
                "high": row["high"],
                "low": row["low"],
                "last": row["last"],
                "volume": row["volume"],
            }
            for row in session_rows
        ]

        frame = pd.DataFrame(data)

        frame["timestamp"] = pd.to_datetime(
            frame["timestamp"],
            utc=True,
        )

        frame = frame.set_index(
            "timestamp",
        )

        frame.index.name = "timestamp"

        return frame[
            CANONICAL_COLUMNS
        ].sort_index()

    @staticmethod
    def _empty_bars() -> pd.DataFrame:
        return pd.DataFrame(
            columns=CANONICAL_COLUMNS,
            index=pd.DatetimeIndex(
                [],
                name="timestamp",
            ),
        )