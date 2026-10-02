"""
Trading API — bars, indicators, backtest.

Assumes trading_engine is already loaded at app startup. All heavy
computation (CNN-LSTM, GA) lives offline; this router only serves
cached data and runs the strategy loop, which is pure pandas/numpy.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import json
import numpy as np
import pandas as pd
from pathlib import Path

from app.services.trading.simulation.engine import trading_engine

router = APIRouter(prefix="/api/v1/trading", tags=["Trading"])

PREDICTIONS_DIR = (
    Path(__file__).parent.parent.parent
    / "services" / "trading" / "predictions"
)


# ==================================================================
# BAR ACCESS
# ==================================================================

def _ensure_loaded():
    if not getattr(trading_engine, "_loaded", False):
        raise HTTPException(503, "Trading engine not loaded")


def _fetch_bars_df(ticker: str, limit: int) -> pd.DataFrame:
    """
    Return the last `limit` bars for a ticker as a DataFrame with
    canonical column names: timestamp, open, high, low, close, volume.
    """
    _ensure_loaded()

    df = trading_engine.get_bars(ticker)
    if df is None or len(df) == 0:
        raise HTTPException(404, f"No bars for ticker: {ticker}")

    df = df.copy()

    # Normalise the common name variants in the Algoseek schema.
    rename_map = {
        "first": "open",
        "last": "close",
        "price": "close",
    }
    for src, dst in rename_map.items():
        if src in df.columns and dst not in df.columns:
            df = df.rename(columns={src: dst})

    df = df.tail(limit).reset_index(drop=True)
    return df


def _timestamp_series(df: pd.DataFrame) -> pd.Series:
    """
    Resolve the timestamp column into a Series of pd.Timestamp.
    """
    if "timestamp" in df.columns:
        return pd.to_datetime(df["timestamp"])

    if "date_time" in df.columns:
        return pd.to_datetime(df["date_time"])

    if isinstance(df.index, pd.DatetimeIndex):
        return pd.Series(df.index, index=df.index)

    # Last resort: use positional index as minutes from epoch.
    return pd.to_datetime(df.index, errors="coerce")


# ==================================================================
# BASIC ENDPOINTS
# ==================================================================

@router.get("/status")
async def status():
    loaded = getattr(trading_engine, "_loaded", False)

    return {
        "trading_ready": loaded,
        "tickers_loaded": (
            len(trading_engine.tickers) if loaded else 0
        ),
        "predictions_available": (
            len(list(PREDICTIONS_DIR.glob("*.json")))
            if PREDICTIONS_DIR.exists()
            else 0
        ),
    }


@router.get("/tickers")
async def tickers():
    _ensure_loaded()
    return {"tickers": sorted(trading_engine.tickers)}


@router.get("/bars/{ticker}")
async def bars(ticker: str, limit: int = 200):
    df = _fetch_bars_df(ticker, limit)

    # Attach a timestamp column so the frontend chart can parse it.
    if "timestamp" not in df.columns:
        ts = _timestamp_series(df)
        df = df.assign(timestamp=ts.astype("int64") // 1_000_000)

    return {
        "ticker": ticker,
        "bars": df.to_dict(orient="records"),
    }


# ==================================================================
# INDICATORS
# ==================================================================

def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)

    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50.0)


def _stochastic(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
    smooth_k: int = 3,
    smooth_d: int = 3,
):
    lowest = low.rolling(period).min()
    highest = high.rolling(period).max()
    denom = (highest - lowest).replace(0, np.nan)
    raw_k = 100 * (close - lowest) / denom
    slow_k = raw_k.rolling(smooth_k).mean()
    slow_d = slow_k.rolling(smooth_d).mean()
    return slow_k.fillna(50.0), slow_d.fillna(50.0)


@router.get("/indicators/{ticker}")
async def indicators(ticker: str, limit: int = 500):
    """
    Compute the classic indicator set for a ticker.

    Overlays (share the price axis):
        ema_5, ema_20, ema_50, bb_upper, bb_lower

    Oscillators (separate scale):
        rsi_14, macd, macd_signal, macd_hist, stoch_k, stoch_d
    """
    df = _fetch_bars_df(ticker, limit)

    if not {"open", "high", "low", "close"}.issubset(df.columns):
        raise HTTPException(
            400,
            "Bar data is missing required OHLC columns."
        )

    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)

    # ---- Overlays ------------------------------------------------
    ema_5 = _ema(close, 5)
    ema_20 = _ema(close, 20)
    ema_50 = _ema(close, 50)

    sma_20 = close.rolling(20).mean()
    std_20 = close.rolling(20).std()
    bb_upper = sma_20 + 2 * std_20
    bb_lower = sma_20 - 2 * std_20

    # ---- MACD ----------------------------------------------------
    macd_line = _ema(close, 12) - _ema(close, 26)
    macd_signal = _ema(macd_line, 9)
    macd_hist = macd_line - macd_signal

    # ---- Oscillators --------------------------------------------
    rsi_14 = _rsi(close, 14)
    stoch_k, stoch_d = _stochastic(high, low, close)

    # ---- Timestamps ---------------------------------------------
    if "timestamp" in df.columns:
        ts = pd.to_datetime(df["timestamp"]).astype("int64") // 1_000_000
    else:
        ts = _timestamp_series(df).astype("int64") // 1_000_000

    ts_list = ts.tolist()

    def series_payload(series: pd.Series) -> list:
        return [
            {"time": int(t), "value": float(v)}
            for t, v in zip(ts_list, series.fillna(0.0).tolist())
            if np.isfinite(v)
        ]

    return {
        "ticker": ticker,
        "overlays": {
            "ema_5":   series_payload(ema_5),
            "ema_20":  series_payload(ema_20),
            "ema_50":  series_payload(ema_50),
            "bb_upper": series_payload(bb_upper),
            "bb_lower": series_payload(bb_lower),
        },
        "oscillators": {
            "rsi_14":       series_payload(rsi_14),
            "macd":         series_payload(macd_line),
            "macd_signal":  series_payload(macd_signal),
            "macd_hist":    series_payload(macd_hist),
            "stoch_k":      series_payload(stoch_k),
            "stoch_d":      series_payload(stoch_d),
        },
    }


# ==================================================================
# BACKTEST
# ==================================================================

class BacktestRequest(BaseModel):
    ticker: str
    limit: int = Field(500, ge=50, le=5000)
    buy_threshold:  float = Field(0.005, ge=0.0, le=0.20)
    sell_threshold: float = Field(0.005, ge=0.0, le=0.20)
    stop_loss:      float = Field(0.02,  ge=0.0, le=0.50)
    take_profit:    float = Field(0.02,  ge=0.0, le=0.50)
    position_size:  float = Field(1000,  gt=0)


def _load_or_synthesise_predictions(
    ticker: str,
    prices: pd.Series,
) -> tuple[np.ndarray, str]:
    """
    Return (predictions, source).

    If a precomputed predictions file exists, use it. Otherwise fall
    back to an EMA-crossover predictor so the interactive layer works
    before the offline ML precompute has been run.
    """
    path = PREDICTIONS_DIR / f"{ticker}.json"

    if path.exists():
        try:
            data = json.loads(path.read_text())
            arr = np.asarray(data.get("y_pred", []), dtype=float)
            if len(arr) >= len(prices):
                return arr[-len(prices):], "precomputed"
        except Exception as exc:
            print(f"[TRADING] predictions file unreadable: {exc}")

    fast = _ema(prices, 5)
    slow = _ema(prices, 20)
    spread = (fast - slow) / slow.replace(0, np.nan)
    naive = spread.shift(1).fillna(0.0).to_numpy()
    return naive, "synthetic"


@router.post("/backtest")
async def backtest(req: BacktestRequest):
    df = _fetch_bars_df(req.ticker, req.limit)

    if "close" not in df.columns:
        raise HTTPException(400, "Bar data is missing a close column.")

    prices = df["close"].astype(float).reset_index(drop=True)
    n = len(prices)

    if n < 5:
        raise HTTPException(400, "Not enough bars to backtest.")

    preds, source = _load_or_synthesise_predictions(
        req.ticker, prices
    )

    trades: list[dict] = []
    in_position = False
    entry_price = 0.0
    entry_idx = 0
    total_return = 0.0

    for i in range(1, n):
        price = float(prices.iloc[i])
        predicted = float(preds[i - 1])

        if in_position:
            change = (price / entry_price) - 1.0

            reason = None

            if change <= -req.stop_loss:
                reason = "stop_loss"
            elif change >= req.take_profit:
                reason = "take_profit"
            elif predicted < -req.sell_threshold:
                reason = "signal"

            if reason:
                total_return += req.position_size * change
                trades.append({
                    "entry_idx": entry_idx,
                    "exit_idx": i,
                    "entry_price": entry_price,
                    "exit_price": price,
                    "return": change,
                    "reason": reason,
                })
                in_position = False
        else:
            if predicted > req.buy_threshold:
                in_position = True
                entry_price = price
                entry_idx = i

    # Close any open position at the last bar.
    if in_position:
        price = float(prices.iloc[-1])
        change = (price / entry_price) - 1.0
        total_return += req.position_size * change
        trades.append({
            "entry_idx": entry_idx,
            "exit_idx": n - 1,
            "entry_price": entry_price,
            "exit_price": price,
            "return": change,
            "reason": "end_of_data",
        })

    wins = [t for t in trades if t["return"] > 0]
    losses = [t for t in trades if t["return"] <= 0]

    return {
        "ticker": req.ticker,
        "params": req.model_dump(),
        "prediction_source": source,
        "trade_count": len(trades),
        "win_rate": (len(wins) / len(trades)) if trades else 0.0,
        "total_return": total_return,
        "total_return_pct": (
            total_return / req.position_size
            if req.position_size else 0.0
        ),
        "avg_win": (
            float(np.mean([t["return"] for t in wins]))
            if wins else 0.0
        ),
        "avg_loss": (
            float(np.mean([t["return"] for t in losses]))
            if losses else 0.0
        ),
        "trades": trades,
        "prices": [float(p) for p in prices.tolist()],
        "predictions": [float(p) for p in preds.tolist()],
    }