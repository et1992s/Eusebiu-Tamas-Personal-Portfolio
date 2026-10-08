"""
migrate_schema.py - Safe migration for the paper trading schema.

Updates paper_positions.status so CLOSED positions are supported while
preserving all existing paper-trading data.
"""

from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[4]
DATABASE_PATH = BASE_DIR / "data" / "paper_trading.sqlite"


def backup_database() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = DATABASE_PATH.with_name(
        f"{DATABASE_PATH.stem}_backup_{timestamp}{DATABASE_PATH.suffix}"
    )

    shutil.copy2(DATABASE_PATH, backup_path)

    return backup_path


def migrate() -> None:
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            f"Paper trading database not found: {DATABASE_PATH}"
        )

    backup_path = backup_database()

    print(f"Database: {DATABASE_PATH}")
    print(f"Backup:   {backup_path}")

    connection = sqlite3.connect(DATABASE_PATH)
    connection.execute("PRAGMA foreign_keys = ON")

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT sql
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'paper_positions'
            """
        )

        row = cursor.fetchone()

        if row is None:
            print("paper_positions table does not exist.")
            print("No migration required.")
            return

        table_sql = row[0] or ""

        if "CHECK (status IN ('OPEN', 'CLOSED'))" in table_sql:
            print("paper_positions already supports CLOSED status.")
            print("No migration required.")
            return

        if "CHECK (status IN ('OPEN'))" not in table_sql:
            raise RuntimeError(
                "Unexpected paper_positions schema. "
                "Migration stopped to protect existing data."
            )

        print("Legacy OPEN-only schema detected.")
        print("Starting transactional migration...")

        cursor.execute("BEGIN IMMEDIATE")

        cursor.execute(
            """
            ALTER TABLE paper_positions
            RENAME TO paper_positions_legacy
            """
        )

        cursor.execute(
            """
            CREATE TABLE paper_positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                portfolio_id INTEGER NOT NULL REFERENCES paper_portfolio(id),
                ticker TEXT NOT NULL,
                side TEXT NOT NULL CHECK (side IN ('LONG')),
                quantity REAL NOT NULL,
                entry_price REAL NOT NULL,
                entry_time TEXT NOT NULL,
                stop_loss REAL,
                take_profit REAL,
                predicted_return REAL,
                signal TEXT,
                status TEXT NOT NULL DEFAULT 'OPEN'
                    CHECK (status IN ('OPEN', 'CLOSED')),
                UNIQUE (portfolio_id, ticker)
            )
            """
        )

        cursor.execute(
            """
            INSERT INTO paper_positions (
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
            )
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
            FROM paper_positions_legacy
            """
        )

        cursor.execute("DROP TABLE paper_positions_legacy")

        connection.commit()

        print("Migration committed successfully.")

    except Exception:
        connection.rollback()
        print("Migration failed. Transaction rolled back.")
        raise

    finally:
        connection.close()


if __name__ == "__main__":
    migrate()