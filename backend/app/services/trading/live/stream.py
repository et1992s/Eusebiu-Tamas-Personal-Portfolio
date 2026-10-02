"""
stream.py - Reusable live prediction stream for Zebio.
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.services.trading.live.prediction import LivePredictionService


class LivePredictionStream:
    """
    Periodically executes live ML inference for a ticker.

    This class is transport-independent. It does not know about
    FastAPI, WebSockets, HTTP, or the frontend.
    """

    def __init__(
        self,
        prediction_service: LivePredictionService,
        interval_seconds: float = 60.0,
    ) -> None:
        if interval_seconds <= 0:
            raise ValueError(
                "interval_seconds must be greater than zero."
            )

        self.prediction_service = prediction_service
        self.interval_seconds = interval_seconds

    async def next_prediction(
        self,
        ticker: str,
    ) -> dict[str, Any]:
        """
        Execute one live prediction asynchronously.
        """

        return await asyncio.to_thread(
            self.prediction_service.predict,
            ticker,
        )

    async def run(
        self,
        ticker: str,
    ):
        """
        Yield live predictions at the configured interval.

        The first prediction is produced immediately.
        Subsequent predictions are produced after each interval.
        """

        while True:
            result = await self.next_prediction(ticker)

            yield result

            await asyncio.sleep(
                self.interval_seconds
            )