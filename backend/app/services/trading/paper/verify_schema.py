import sqlite3
from pathlib import Path


DATABASE_PATH = (
    Path(__file__).resolve().parents[4]
    / "data"
    / "paper_trading.sqlite"
)


connection = sqlite3.connect(DATABASE_PATH)

try:
    cursor = connection.cursor()

    table_sql = cursor.execute(
        """
        SELECT sql
        FROM sqlite_master
        WHERE type = 'table'
          AND name = 'paper_positions'
        """
    ).fetchone()

    open_positions = cursor.execute(
        """
        SELECT COUNT(*)
        FROM paper_positions
        WHERE status = 'OPEN'
        """
    ).fetchone()[0]

    closed_positions = cursor.execute(
        """
        SELECT COUNT(*)
        FROM paper_positions
        WHERE status = 'CLOSED'
        """
    ).fetchone()[0]

    trades = cursor.execute(
        """
        SELECT COUNT(*)
        FROM paper_trades
        """
    ).fetchone()[0]

    print("=== PAPER TRADING SCHEMA VERIFICATION ===")
    print()
    print("paper_positions schema:")
    print(table_sql[0] if table_sql else "NOT FOUND")
    print()
    print(f"OPEN positions:   {open_positions}")
    print(f"CLOSED positions: {closed_positions}")
    print(f"Trades:           {trades}")

finally:
    connection.close()