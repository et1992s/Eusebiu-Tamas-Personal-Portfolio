"""
main.py - Zebio Studio Engine
Interactive backend for transit routing and algorithmic trading simulations
"""

import logging
from contextlib import asynccontextmanager
import time

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from app.services.tube import tube_engine
from app.services.trading.simulation.engine import TradingEngine
from app.api.ai import router as ai_router

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============================================
# GLOBAL TRADING ENGINE - USING PRE-PROCESSED PICKLE
# ============================================
trading_engine = TradingEngine(data_path='data/algoseek_preprocessed.pkl')


# ============================================
# LIFECYCLE MANAGEMENT
# ============================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("🚀 Starting Zebio Studio Engine...")
    
    # Load pre-processed data (instant)
    logger.info("📊 Loading trading data...")
    start_time = time.time()
    trading_engine.load_data()
    logger.info(f"✅ Loaded {len(trading_engine.tickers)} tickers in {time.time() - start_time:.2f}s")
    
    tube_status = "verified" if len(tube_engine.stations_to_int) > 0 else "failed"
    logger.info(f"📊 Tube data: {tube_status}")
    logger.info("✅ Server ready!")
    
    yield
    
    logger.info("💤 Shutting down...")


# ============================================
# FASTAPI APP
# ============================================
app = FastAPI(
    title="Zebio Studio Engine",
    description="Interactive backend for transit routing and algorithmic trading simulations",
    version="1.0.0",
    lifespan=lifespan,
    default_response_class=ORJSONResponse
)

app.include_router(ai_router)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================
# HEALTH CHECK
# ============================================
@app.get("/health", tags=["System Health"])
async def health_check():
    tube_status = "verified" if len(tube_engine.stations_to_int) > 0 else "failed"
    return {
        "status": "online",
        "tube_data": tube_status,
        "trading_ready": trading_engine._loaded,
        "tickers_loaded": len(trading_engine.tickers) if trading_engine._loaded else 0
    }


# ============================================
# TUBE ROUTING
# ============================================

@app.get("/api/v1/tube/stations", tags=["Transit Routing"])
async def get_tube_stations():
    return {
        "count": len(tube_engine.stations_to_int),
        "stations": sorted(tube_engine.stations_to_int.keys()),
    }

@app.get("/api/v1/tube/route", tags=["Transit Routing"])
async def compute_tube_route(
    start: str = Query(..., description="Origin station", example="VICTORIA"),
    end: str = Query(..., description="Destination station", example="OXFORD CIRCUS"),
    algorithm: str = Query("dijkstra", description="'dijkstra' or 'bellman_ford'"),
    optimize: str = Query("time", description="'time' or 'stops'")
):
    minimize_stops = (optimize.strip().lower() == "stops")
    algo_choice = algorithm.strip().lower()

    try:
        if algo_choice == "dijkstra":
            route, cost = tube_engine.compute_dijkstra_route(start.upper().strip(), end.upper().strip(), minimize_stops=minimize_stops)
            return {
                "status": "success",
                "algorithm": "Dijkstra",
                "optimization": "stops" if minimize_stops else "time",
                "total_cost": cost,
                "route": route
            }
        elif algo_choice == "bellman_ford":
            route, cost, has_negative_cycle = tube_engine.compute_bellman_ford_route(start.upper().strip(), end.upper().strip(), minimize_stops=minimize_stops)
            return {
                "status": "success",
                "algorithm": "Bellman-Ford",
                "optimization": "stops" if minimize_stops else "time",
                "total_cost": cost,
                "negative_cycle_detected": has_negative_cycle,
                "route": route
            }
        else:
            raise HTTPException(status_code=400, detail="Invalid algorithm. Use 'dijkstra' or 'bellman_ford'.")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Routing error: {str(e)}")


@app.get("/api/v1/tube/closures", tags=["Network Analytics"])
async def get_mst_closures():
    try:
        closures = tube_engine.compute_closures()
        return {
            "status": "success",
            "total": len(closures),
            "closures": closures
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analytics error: {str(e)}")


# ============================================
# TRADING ENDPOINTS
# ============================================
@app.get("/api/v1/trading/tickers", tags=["Trading"])
async def get_trading_tickers():
    """Get all available tickers"""
    try:
        tickers = trading_engine.get_tickers()
        return {
            "status": "success",
            "count": len(tickers),
            "tickers": tickers
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching tickers: {str(e)}")


@app.get("/api/v1/trading/bars/{ticker}", tags=["Trading"])
async def get_trading_bars(
    ticker: str,
    limit: int = Query(100, ge=1, le=5000, description="Number of bars")
):
    """Get OHLCV bars for a ticker (2015 data)"""
    clean_ticker = ticker.upper().strip()
    try:
        # Check if ticker exists
        if clean_ticker not in trading_engine.ticker_data:
            raise HTTPException(status_code=404, detail=f"Ticker '{clean_ticker}' not found")
        
        bars = trading_engine.get_bars_2015(clean_ticker, limit)
        
        if not bars:
            raise HTTPException(status_code=404, detail=f"No 2015 data for '{clean_ticker}'")
        
        return {
            "status": "success",
            "ticker": clean_ticker,
            "bars": len(bars),
            "data": bars
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching bars: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching bars: {str(e)}")


@app.get("/api/v1/trading/status", tags=["Trading"])
async def get_trading_status():
    """Get trading engine status"""
    return {
        "ready": trading_engine._loaded,
        "tickers_loaded": len(trading_engine.tickers) if trading_engine._loaded else 0
    }


# ============================================
# ROOT
# ============================================
@app.get("/", response_class=ORJSONResponse)
async def root():
    return {
        "name": "Zebio Studio Engine",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "tube": "/api/v1/tube/route",
            "trading": "/api/v1/trading/tickers",
            "bars": "/api/v1/trading/bars/{ticker}"
        }
    }