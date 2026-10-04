"""
main.py - Zebio Studio Engine

FastAPI application for:
- London Underground routing and network analytics
- Algorithmic trading data access
- Machine-learning trading inference
- Deterministic trading backtesting
"""

import logging
import websockets
import json
import os
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, List

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
from pydantic import BaseModel

from app.api.ai import router as ai_router
from app.api.contact import router as contact_router
from app.services.trading.live.alpaca import AlpacaMarketDataProvider
from app.services.trading.live.chart import LiveChartService
from app.services.trading.live.prediction import LivePredictionService
from app.services.trading.live.market_data import MarketDataService
from app.services.trading.live.market_store import MarketDataStore
from app.services.trading.live.stream import LivePredictionStream
from app.services.trading.ml.inference import inference_service
from app.services.trading.simulation.engine import TradingEngine
from app.services.trading.paper.api import router as paper_router
from app.services.trading.paper.bootstrap import ensure_portfolio
from app.services.tube import tube_engine



# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Trading engine
# ---------------------------------------------------------------------------

trading_engine = TradingEngine(
    data_path="data/algoseek_preprocessed.pkl"
)

live_market_provider = AlpacaMarketDataProvider()

market_data_store = MarketDataStore(
    path="data/market_data.db",
)

market_data_service = MarketDataService(
    provider=live_market_provider,
    store=market_data_store,
)

live_chart_service = LiveChartService(
    provider=market_data_service,
    default_limit=100,
)

live_prediction_service = LivePredictionService(
    provider=market_data_service,
    bars_limit=100,
)

live_prediction_stream = LivePredictionStream(
    prediction_service=live_prediction_service,
    interval_seconds=60.0,
)

# ---------------------------------------------------------------------------
# Application lifecycle
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise and shut down Zebio services."""

    logger.info("Starting Zebio Studio Engine")

    start_time = time.time()

    logger.info("Loading trading data")
    trading_engine.load_data()

    elapsed = time.time() - start_time

    logger.info(
        "Loaded %d trading tickers in %.2f seconds",
        len(trading_engine.tickers),
        elapsed,
    )

    tube_status = (
        "verified"
        if tube_engine.stations_to_int
        else "failed"
    )

    logger.info("Tube data status: %s", tube_status)

    # ── Paper trading bootstrap ─────────────────────────────
    try:
        ensure_portfolio()
    except Exception:
        logger.exception("Paper portfolio bootstrap failed")

    logger.info("Zebio Studio Engine ready")

    yield

    logger.info("Shutting down Zebio Studio Engine")


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Zebio Studio Engine",
    description=(
        "Interactive backend for transit routing and "
        "algorithmic trading simulations"
    ),
    version="1.0.0",
    lifespan=lifespan,
    default_response_class=ORJSONResponse,
)

app.include_router(ai_router)
app.include_router(contact_router)
app.include_router(paper_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def clean_ticker(ticker: str) -> str:
    """Normalise a ticker symbol."""
    return ticker.upper().strip()

def denormalize_ticker(ticker: str) -> str:
    """Convert BTC-USD → BTC/USD for crypto, leave equities alone."""
    t = ticker.upper().strip()
    # Only translate dash → slash if it looks like a crypto pair
    if "-" in t and not t.startswith("-"):
        return t.replace("-", "/", 1)
    return t

def require_trading_ticker(ticker: str) -> str:
    """
    Validate a ticker against the loaded trading dataset.

    Returns the normalised ticker or raises HTTP 404.
    """
    ticker = clean_ticker(ticker)

    if not trading_engine._loaded:
        raise HTTPException(
            status_code=503,
            detail="Trading engine not loaded",
        )

    if ticker not in trading_engine.ticker_data:
        raise HTTPException(
            status_code=404,
            detail=f"Ticker '{ticker}' not found",
        )

    return ticker


def extract_bar_close(bar: Dict[str, Any]) -> float | None:
    """Extract a closing price from a trading bar."""
    for key in ("close", "last", "price"):
        value = bar.get(key)

        if value is None:
            continue

        try:
            return float(value)
        except (TypeError, ValueError):
            continue

    return None


def calculate_ema(values: List[float], span: int) -> List[float]:
    """Calculate an exponential moving average using pure Python."""
    if not values:
        return []

    alpha = 2.0 / (span + 1.0)

    result = [0.0] * len(values)
    previous = values[0]
    result[0] = previous

    for index in range(1, len(values)):
        previous = (
            alpha * values[index]
            + (1.0 - alpha) * previous
        )
        result[index] = previous

    return result


# ---------------------------------------------------------------------------
# System health
# ---------------------------------------------------------------------------

@app.get(
    "/health",
    tags=["System Health"],
)
async def health_check():
    """Return the current health status of Zebio services."""

    tube_status = (
        "verified"
        if tube_engine.stations_to_int
        else "failed"
    )

    return {
        "status": "online",
        "tube_data": tube_status,
        "trading_ready": trading_engine._loaded,
        "tickers_loaded": (
            len(trading_engine.tickers)
            if trading_engine._loaded
            else 0
        ),
    }


# ---------------------------------------------------------------------------
# Tube routing
# ---------------------------------------------------------------------------

@app.get(
    "/api/v1/tube/stations",
    tags=["Transit Routing"],
)
async def get_tube_stations():
    """Return all available Tube stations."""

    stations = sorted(tube_engine.stations_to_int.keys())

    return {
        "count": len(stations),
        "stations": stations,
    }


@app.get(
    "/api/v1/tube/route",
    tags=["Transit Routing"],
)
async def compute_tube_route(
    start: str = Query(
        ...,
        description="Origin station",
        example="VICTORIA",
    ),
    end: str = Query(
        ...,
        description="Destination station",
        example="OXFORD CIRCUS",
    ),
    algorithm: str = Query(
        "dijkstra",
        description="'dijkstra' or 'bellman_ford'",
    ),
    optimize: str = Query(
        "time",
        description="'time' or 'stops'",
    ),
):
    """Compute a Tube route using Dijkstra or Bellman-Ford."""

    start_station = start.upper().strip()
    end_station = end.upper().strip()
    algorithm_choice = algorithm.lower().strip()
    minimize_stops = optimize.lower().strip() == "stops"

    try:
        if algorithm_choice == "dijkstra":
            route, cost = tube_engine.compute_dijkstra_route(
                start_station,
                end_station,
                minimize_stops=minimize_stops,
            )

            return {
                "status": "success",
                "algorithm": "Dijkstra",
                "optimization": (
                    "stops"
                    if minimize_stops
                    else "time"
                ),
                "total_cost": cost,
                "route": route,
            }

        if algorithm_choice == "bellman_ford":
            (
                route,
                cost,
                has_negative_cycle,
            ) = tube_engine.compute_bellman_ford_route(
                start_station,
                end_station,
                minimize_stops=minimize_stops,
            )

            return {
                "status": "success",
                "algorithm": "Bellman-Ford",
                "optimization": (
                    "stops"
                    if minimize_stops
                    else "time"
                ),
                "total_cost": cost,
                "negative_cycle_detected": has_negative_cycle,
                "route": route,
            }

        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid algorithm. "
                "Use 'dijkstra' or 'bellman_ford'."
            ),
        )

    except HTTPException:
        raise

    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        logger.exception("Tube routing failed")

        raise HTTPException(
            status_code=500,
            detail=f"Routing error: {exc}",
        ) from exc


@app.get(
    "/api/v1/tube/closures",
    tags=["Network Analytics"],
)
async def get_mst_closures():
    """Calculate network closures using the MST analysis."""

    try:
        closures = tube_engine.compute_closures()

        return {
            "status": "success",
            "total": len(closures),
            "closures": closures,
        }

    except Exception as exc:
        logger.exception("Tube network analytics failed")

        raise HTTPException(
            status_code=500,
            detail=f"Analytics error: {exc}",
        ) from exc


# ---------------------------------------------------------------------------
# Trading data
# ---------------------------------------------------------------------------

@app.get(
    "/api/v1/trading/tickers",
    tags=["Trading"],
)
async def get_trading_tickers():
    """Return all tickers available in the trading dataset."""

    try:
        tickers = trading_engine.get_tickers()

        return {
            "status": "success",
            "count": len(tickers),
            "tickers": tickers,
        }

    except Exception as exc:
        logger.exception("Failed to retrieve trading tickers")

        raise HTTPException(
            status_code=500,
            detail=f"Error fetching tickers: {exc}",
        ) from exc


@app.get(
    "/api/v1/trading/bars/{ticker}",
    tags=["Trading"],
)
async def get_trading_bars(
    ticker: str,
    limit: int = Query(
        100,
        ge=1,
        le=5000,
        description="Number of bars",
    ),
):
    """Return OHLCV bars from the 2015 trading dataset."""

    ticker = require_trading_ticker(ticker)

    try:
        bars = trading_engine.get_bars_2015(
            ticker,
            limit,
        )

        if not bars:
            raise HTTPException(
                status_code=404,
                detail=f"No 2015 data for '{ticker}'",
            )

        return {
            "status": "success",
            "ticker": ticker,
            "bars": len(bars),
            "data": bars,
        }

    except HTTPException:
        raise

    except Exception as exc:
        logger.exception(
            "Failed to retrieve bars for %s",
            ticker,
        )

        raise HTTPException(
            status_code=500,
            detail=f"Error fetching bars: {exc}",
        ) from exc


@app.get(
    "/api/v1/trading/status",
    tags=["Trading"],
)
async def get_trading_status():
    """Return trading engine status."""

    return {
        "ready": trading_engine._loaded,
        "tickers_loaded": (
            len(trading_engine.tickers)
            if trading_engine._loaded
            else 0
        ),
    }

@app.get(
    "/api/v1/trading/live/chart/{ticker}",
    tags=["Trading"],
)
async def get_live_chart(
    ticker: str,
    timeframe: str = Query("1m"),
    limit: int = Query(100, ge=1, le=500),
    asset_class: str = Query("stocks"),
):
    """
    Return market candles for the requested chart timeframe.

    Supports stocks, ETFs, and crypto.

    The response source identifies whether the data came directly
    from Alpaca or from the persistent historical market-data cache.
    """
    if not ticker:
        raise HTTPException(
            status_code=400,
            detail="Ticker must not be empty.",
        )

    # Denormalize: BTC-USD -> BTC/USD for Alpaca.
    alpaca_ticker = denormalize_ticker(ticker)

    try:
        normalized_timeframe = (
            live_chart_service.normalize_timeframe(
                timeframe
            )
        )

        chart_result = live_chart_service.get_bars(
            ticker=alpaca_ticker,
            timeframe=normalized_timeframe,
            limit=limit,
            asset_class=asset_class,
        )

        bars = chart_result.bars

        if bars.empty:
            raise HTTPException(
                status_code=404,
                detail=(
                    "No market data available for "
                    f"'{alpaca_ticker}'."
                ),
            )

        data = []

        for timestamp, row in bars.iterrows():
            data.append(
                {
                    "timestamp": (
                        timestamp
                        .tz_convert("UTC")
                        .isoformat()
                    ),
                    "open": float(row["first"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["last"]),
                    "volume": int(row["volume"]),
                }
            )

        return {
            "status": "success",
            "source": chart_result.source,
            "ticker": alpaca_ticker,
            "timeframe": normalized_timeframe,
            "bars": len(data),
            "data": data,
        }

    except HTTPException:
        raise

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    except Exception:
        logger.exception(
            "Live chart request failed for %s",
            alpaca_ticker,
        )

        raise HTTPException(
            status_code=502,
            detail=(
                "Market-data request failed for "
                f"'{alpaca_ticker}'."
            ),
        )

# ---------------------------------------------------------------------------
# Machine-learning inference
# ---------------------------------------------------------------------------

@app.get(
    "/api/v1/trading/predict/{ticker}",
    tags=["Trading"],
)
async def predict_trading(
    ticker: str,
    limit: int = Query(
        500,
        ge=30,
        le=5000,
        description=(
            "Number of recent OHLCV bars "
            "used for inference"
        ),
    ),
):
    """
    Run the trained ML model for the latest valid sequence.

    The endpoint:
    1. Validates the ticker against the trading dataset.
    2. Retrieves the most recent OHLCV bars.
    3. Builds the model feature sequence.
    4. Runs the trained ticker-specific model.
    5. Returns the predicted forward return.
    """

    ticker = require_trading_ticker(ticker)

    try:
        bars = trading_engine.get_bars_dataframe(
            ticker,
            limit,
        )

        if bars is None or bars.empty:
            raise HTTPException(
                status_code=404,
                detail=f"No bars available for '{ticker}'",
            )

        result = inference_service.predict(
            ticker,
            bars,
        )

        return {
            "status": "success",
            "prediction": result,
        }

    except HTTPException:
        raise

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        logger.exception(
            "ML inference failed for %s",
            ticker,
        )

        raise HTTPException(
            status_code=500,
            detail=f"Inference failed for '{ticker}': {exc}",
        ) from exc

@app.get(
    "/api/v1/trading/live/predict/{ticker}",
    tags=["Trading"],
)
async def predict_live_trading(ticker: str):
    """
    Fetch recent live market data and run the production ML model.
    """

    normalized = clean_ticker(ticker)

    if not normalized:
        raise HTTPException(
            status_code=400,
            detail="Ticker must not be empty.",
        )

    try:
        result = live_prediction_service.predict(
            normalized,
        )

        return {
            "status": "success",
            "source": "live",
            "prediction": result,
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        logger.exception(
            "Live prediction failed for %s",
            normalized,
        )

        raise HTTPException(
            status_code=502,
            detail=(
                f"Live market-data or inference request "
                f"failed for '{normalized}'."
            ),
        ) from exc

_ASSET_CACHE: dict[str, list[dict]] = {}


@app.get(
    "/api/v1/trading/assets",
    tags=["Trading"],
)
async def get_tradable_assets(
    asset_class: str = Query(
        "stocks",
        description="One of: stocks, etf, crypto",
    ),
):
    """
    Return the list of tradable symbols for a given asset class,
    sourced directly from Alpaca.
    """
    if asset_class not in ("stocks", "etf", "crypto"):
        raise HTTPException(
            status_code=400,
            detail="asset_class must be one of: stocks, etf, crypto",
        )

    if asset_class not in _ASSET_CACHE:
        try:
            assets = live_market_provider.get_tradable_assets(asset_class)
            _ASSET_CACHE[asset_class] = assets
            logger.info(
                "Cached %d %s assets from Alpaca",
                len(assets),
                asset_class,
            )
        except Exception as exc:
            logger.exception("Failed to fetch assets from Alpaca")
            raise HTTPException(
                status_code=502,
                detail=f"Failed to fetch Alpaca assets: {exc}",
            ) from exc

    return {
        "status": "success",
        "asset_class": asset_class,
        "count": len(_ASSET_CACHE[asset_class]),
        "assets": _ASSET_CACHE[asset_class],
    }

@app.websocket("/api/v1/trading/live/chart/stream/{ticker}")
async def live_chart_stream(websocket: WebSocket, ticker: str, asset_class: str = "stocks"):
    await websocket.accept()
    alpaca_ticker = denormalize_ticker(ticker)

    if asset_class == "crypto":
        alpaca_url = "wss://stream.data.alpaca.markets/v1beta3/crypto/us"
    else:
        alpaca_url = "wss://stream.data.alpaca.markets/v2/iex"

    logger.info("WS connect: ticker=%s asset=%s", alpaca_ticker, asset_class)

    try:
        async with websockets.connect(alpaca_url) as alpaca_ws:
            # Auth
            await alpaca_ws.send(json.dumps({
                "action": "auth",
                "key": os.getenv("ALPACA_API_KEY"),
                "secret": os.getenv("ALPACA_API_SECRET"),
            }))

            # Log Alpaca's auth/subscription responses
            auth_resp = await alpaca_ws.recv()
            logger.info("Alpaca auth: %s", auth_resp)

            # Subscribe
            await alpaca_ws.send(json.dumps({
                "action": "subscribe",
                "bars": [alpaca_ticker],
            }))

            sub_resp = await alpaca_ws.recv()
            logger.info("Alpaca sub: %s", sub_resp)

            async for message in alpaca_ws:
                logger.info("Alpaca msg: %s", message[:200])
                await websocket.send_text(message)

    except WebSocketDisconnect:
        logger.info("Frontend chart WS disconnected: %s", alpaca_ticker)
    except Exception as exc:
        logger.exception("Alpaca WS error for %s", alpaca_ticker)
        try:
            await websocket.close(code=1011)
        except Exception:
            pass

@app.websocket("/api/v1/trading/live/stream/{ticker}")
async def live_trading_stream(websocket: WebSocket, ticker: str):
    await websocket.accept()
    alpaca_ticker = denormalize_ticker(ticker)

    try:
        async for prediction in live_prediction_stream.run(alpaca_ticker):
            await websocket.send_json({
                "status": "success",
                "source": "live",
                "prediction": prediction,
            })
            
    except WebSocketDisconnect:
        logger.info("Live prediction WS disconnected: %s", alpaca_ticker)
    except Exception:
        logger.exception("Live prediction WS failed for %s", alpaca_ticker)
        try:
            await websocket.close(code=1011)
        except Exception:
            pass

# ---------------------------------------------------------------------------
# Trading backtest
# ---------------------------------------------------------------------------

class BacktestRequest(BaseModel):
    """Parameters for the deterministic trading backtest."""

    ticker: str
    limit: int = 500
    buy_threshold: float = 0.005
    sell_threshold: float = 0.005
    stop_loss: float = 0.02
    take_profit: float = 0.02
    position_size: float = 1000


@app.post(
    "/api/v1/trading/backtest",
    tags=["Trading"],
)
async def run_trading_backtest(
    req: BacktestRequest,
):
    """
    Run the deterministic strategy backtest.

    The current predictor is intentionally synthetic:
    a 5/20 EMA crossover shifted by one bar.

    This endpoint remains independent of the ML inference service.
    """

    ticker = require_trading_ticker(req.ticker)

    bars = trading_engine.get_bars_2015(
        ticker,
        req.limit,
    )

    if not bars:
        raise HTTPException(
            status_code=404,
            detail=f"No data for '{ticker}'",
        )

    prices = []

    for bar in bars:
        close = extract_bar_close(bar)

        if close is not None:
            prices.append(close)

    n = len(prices)

    if n < 5:
        raise HTTPException(
            status_code=400,
            detail="Not enough bars to backtest",
        )

    # Synthetic predictor:
    # 5/20 EMA crossover shifted by one bar.
    fast_ema = calculate_ema(
        prices,
        5,
    )

    slow_ema = calculate_ema(
        prices,
        20,
    )

    predictions = [0.0] * n

    for index in range(1, n):
        previous_slow = slow_ema[index - 1]

        if previous_slow != 0:
            predictions[index] = (
                fast_ema[index - 1]
                - previous_slow
            ) / previous_slow

    # Strategy state.
    trades = []
    in_position = False
    entry_price = 0.0
    entry_index = 0
    total_return = 0.0

    for index in range(1, n):
        price = prices[index]
        predicted = predictions[index]

        if in_position:
            change = (
                price / entry_price
            ) - 1.0

            exit_reason = None

            if change <= -req.stop_loss:
                exit_reason = "stop_loss"

            elif change >= req.take_profit:
                exit_reason = "take_profit"

            elif predicted < -req.sell_threshold:
                exit_reason = "signal"

            if exit_reason:
                total_return += (
                    req.position_size * change
                )

                trades.append(
                    {
                        "entry_idx": entry_index,
                        "exit_idx": index,
                        "entry_price": entry_price,
                        "exit_price": price,
                        "return": change,
                        "reason": exit_reason,
                    }
                )

                in_position = False

        elif predicted > req.buy_threshold:
            in_position = True
            entry_price = price
            entry_index = index

    # Close any remaining position at the end of the dataset.
    if in_position:
        final_price = prices[-1]

        change = (
            final_price / entry_price
        ) - 1.0

        total_return += (
            req.position_size * change
        )

        trades.append(
            {
                "entry_idx": entry_index,
                "exit_idx": n - 1,
                "entry_price": entry_price,
                "exit_price": final_price,
                "return": change,
                "reason": "end_of_data",
            }
        )

    winning_trades = [
        trade
        for trade in trades
        if trade["return"] > 0
    ]

    losing_trades = [
        trade
        for trade in trades
        if trade["return"] <= 0
    ]

    def mean(values: List[float]) -> float:
        return (
            sum(values) / len(values)
            if values
            else 0.0
        )

    return {
        "ticker": ticker,
        "params": req.model_dump(),
        "prediction_source": "synthetic",
        "trade_count": len(trades),
        "win_rate": (
            len(winning_trades) / len(trades)
            if trades
            else 0.0
        ),
        "total_return": total_return,
        "total_return_pct": (
            total_return / req.position_size
            if req.position_size
            else 0.0
        ),
        "avg_win": mean(
            [
                trade["return"]
                for trade in winning_trades
            ]
        ),
        "avg_loss": mean(
            [
                trade["return"]
                for trade in losing_trades
            ]
        ),
        "trades": trades,
        "prices": prices,
        "predictions": predictions,
    }


# ---------------------------------------------------------------------------
# Root
# ---------------------------------------------------------------------------

@app.get(
    "/",
    response_class=ORJSONResponse,
)
async def root():
    """Return basic API information."""

    return {
        "name": "Zebio Studio Engine",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "health": "/health",
            "tube": "/api/v1/tube/route",
            "trading": "/api/v1/trading/tickers",
            "bars": "/api/v1/trading/bars/{ticker}",
            "predict": "/api/v1/trading/predict/{ticker}",
            "backtest": "/api/v1/trading/backtest",
        },
    }
