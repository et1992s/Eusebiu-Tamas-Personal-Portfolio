"""
live_loop.py - Recurring live paper-trading execution loop.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.services.trading.live.prediction import LivePredictionService
from app.services.trading.live.stream import LivePredictionStream
from app.services.trading.ml.inference import inference_service
from app.services.trading.paper.live_trading import (
    LivePaperTradingService,
)

logger = logging.getLogger(__name__)


class LivePaperTradingLoop:
    """
    Consume production ML predictions and execute paper trades.

    The ML artifact universe is the single source of truth for the
    ticker universe. Strategy and execution remain delegated to the
    existing paper-trading services.
    """

    def __init__(
        self,
        prediction_stream: LivePredictionStream,
        trading_service: LivePaperTradingService,
        asset_class: str = "stocks",
    ) -> None:
        normalized_asset_class = asset_class.strip().lower()

        if not normalized_asset_class:
            raise ValueError(
                "asset_class must not be empty."
            )

        self.prediction_stream = prediction_stream
        self.trading_service = trading_service
        self.asset_class = normalized_asset_class

        self._tasks: list[asyncio.Task[Any]] = []
        self._stop_event = asyncio.Event()

    def tickers(self) -> list[str]:
        """
        Return the current production ML ticker universe.
        """

        return inference_service.discover_tickers()

    async def _run_ticker(
        self,
        ticker: str,
    ) -> None:
        """
        Consume the live prediction stream for one ticker.
        """

        logger.info(
            "Starting live paper trading stream: %s (%s)",
            ticker,
            self.asset_class,
        )

        try:
            async for prediction in self.prediction_stream.run(
                ticker=ticker,
                asset_class=self.asset_class,
            ):
                if self._stop_event.is_set():
                    break

                try:
                    result = (
                        self.trading_service.process_prediction(
                            prediction_payload=prediction,
                        )
                    )

                    if result["executed"]:
                        execution = result["execution"] or {}

                        logger.info(
                            "Paper trade executed: "
                            "%s action=%s mode=%s "
                            "price=%.6f predicted_return=%.6f",
                            result["ticker"],
                            execution.get(
                                "action",
                                "UNKNOWN",
                            ),
                            result["mode"],
                            result["current_price"],
                            result["predicted_return"],
                        )
                    else:
                        evaluation = (
                            result["evaluation"] or {}
                        )

                        logger.info(
                            "Paper trading decision: "
                            "%s mode=%s action=%s reason=%s "
                            "price=%.6f predicted_return=%.6f",
                            result["ticker"],
                            result["mode"],
                            evaluation.get(
                                "action",
                                "HOLD",
                            ),
                            evaluation.get(
                                "reason",
                                "unknown",
                            ),
                            result["current_price"],
                            result["predicted_return"],
                        )

                except Exception:
                    logger.exception(
                        "Paper trading cycle failed for %s.",
                        ticker,
                    )

        except asyncio.CancelledError:
            logger.info(
                "Live paper trading stream cancelled: %s",
                ticker,
            )
            raise

        except Exception:
            logger.exception(
                "Live paper trading stream stopped for %s.",
                ticker,
            )

    async def start(self) -> None:
        """
        Start one asynchronous consumer for every supported model.
        """

        if self._tasks:
            raise RuntimeError(
                "Live paper trading loop is already running."
            )

        tickers = self.tickers()

        if not tickers:
            raise RuntimeError(
                "No complete production ML models were discovered."
            )

        self._stop_event.clear()

        self._tasks = [
            asyncio.create_task(
                self._run_ticker(ticker),
                name=f"paper-trading-{ticker}",
            )
            for ticker in tickers
        ]

        logger.info(
            "Live paper trading loop started: "
            "%d ticker(s), asset_class=%s",
            len(tickers),
            self.asset_class,
        )

        try:
            await asyncio.gather(
                *self._tasks,
            )
        finally:
            self._tasks.clear()

    async def stop(self) -> None:
        """
        Stop all active ticker consumers.
        """

        if not self._tasks:
            return

        logger.info(
            "Stopping live paper trading loop."
        )

        self._stop_event.set()

        tasks = list(self._tasks)

        for task in tasks:
            task.cancel()

        await asyncio.gather(
            *tasks,
            return_exceptions=True,
        )

        self._tasks.clear()

        logger.info(
            "Live paper trading loop stopped."
        )

    def status(self) -> dict[str, Any]:
        """
        Return the current runtime state.
        """

        tickers = self.tickers()

        return {
            "running": bool(self._tasks),
            "tickers": tickers,
            "asset_class": self.asset_class,
            "ticker_count": len(tickers),
        }