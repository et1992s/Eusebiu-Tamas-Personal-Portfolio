-- ─────────────────────────────────────────────────────────────
-- Zebio paper-trading schema
-- ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS paper_portfolio (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  name             TEXT    NOT NULL UNIQUE,
  initial_capital  REAL    NOT NULL,
  currency         TEXT    NOT NULL DEFAULT 'GBP',
  cash             REAL    NOT NULL,
  equity           REAL    NOT NULL,
  starting_date    TEXT    NOT NULL,
  created_at       TEXT    NOT NULL,
  updated_at       TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS paper_positions (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  portfolio_id     INTEGER NOT NULL REFERENCES paper_portfolio(id),
  ticker           TEXT    NOT NULL,
  side             TEXT    NOT NULL CHECK (side IN ('LONG')),
  quantity         REAL    NOT NULL,
  entry_price      REAL    NOT NULL,
  entry_time       TEXT    NOT NULL,
  stop_loss        REAL,
  take_profit      REAL,
  predicted_return REAL,
  signal           TEXT,
  status           TEXT    NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN')),
  UNIQUE (portfolio_id, ticker)
);

CREATE TABLE IF NOT EXISTS paper_trades (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  portfolio_id     INTEGER NOT NULL REFERENCES paper_portfolio(id),
  ticker           TEXT    NOT NULL,
  side             TEXT    NOT NULL,
  quantity         REAL    NOT NULL,
  entry_price      REAL    NOT NULL,
  exit_price       REAL    NOT NULL,
  entry_time       TEXT    NOT NULL,
  exit_time        TEXT    NOT NULL,
  predicted_return REAL,
  signal           TEXT,
  realised_pnl     REAL    NOT NULL,
  pnl_pct          REAL    NOT NULL,
  exit_reason      TEXT,
  holding_seconds  INTEGER,
  fees             REAL    NOT NULL DEFAULT 0,
  created_at       TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_trades_portfolio_exit_time
  ON paper_trades (portfolio_id, exit_time DESC);

CREATE TABLE IF NOT EXISTS paper_daily_snapshots (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  portfolio_id     INTEGER NOT NULL REFERENCES paper_portfolio(id),
  date             TEXT    NOT NULL,
  equity           REAL    NOT NULL,
  cash             REAL    NOT NULL,
  unrealised_pnl   REAL    NOT NULL,
  realised_pnl_day REAL    NOT NULL,
  cumulative_pnl   REAL    NOT NULL,
  drawdown         REAL    NOT NULL,
  trade_count      INTEGER NOT NULL DEFAULT 0,
  UNIQUE (portfolio_id, date)
);

CREATE INDEX IF NOT EXISTS idx_snapshots_portfolio_date
  ON paper_daily_snapshots (portfolio_id, date ASC);