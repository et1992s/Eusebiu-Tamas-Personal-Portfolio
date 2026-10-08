"""
stream.py - Reusable live prediction stream for Zebio.
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.services.trading.live.prediction import (
    LivePredictionService,
)


class LivePredictionStream:
    """
    Periodically executes live ML inference for a ticker.

    This class is transport-independent. It does not know about
    FastAPI, WebSockets, HTTP, or the frontend.

    Market-session awareness is handled here so the stream does not
    repeatedly attempt inference while the relevant market is closed.

    Asset classes are passed explicitly through the stream so the same
    streaming infrastructure can support stocks, ETFs, and crypto.
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
        asset_class: str = "stocks",
    ) -> dict[str, Any]:
        """
        Execute one live prediction asynchronously.
        """

        return await asyncio.to_thread(
            self.prediction_service.predict,
            ticker,
            asset_class,
        )

    async def _market_is_open(
        self,
        asset_class: str = "stocks",
    ) -> bool:
        """
        Check whether the configured market session is currently open.

        If no session service is configured, preserve the previous
        behaviour and allow inference.
        """

        session_service = (
            self.prediction_service.session_service
        )

        if session_service is None:
            return True

        return await asyncio.to_thread(
            session_service.is_open,
            asset_class,
        )

    async def run(
        self,
        ticker: str,
        asset_class: str = "stocks",
    ):
        """
        Yield live predictions at the configured interval.

        The first prediction is produced immediately when the relevant
        market is open.

        When the market is closed, no inference is attempted. The
        stream remains alive and periodically checks the session again.

        Parameters
        ----------
        ticker:
            Asset ticker or symbol.

        asset_class:
            Market asset class. Supported values are currently
            "stocks", "etf", and "crypto".
        """

        while True:
            market_is_open = await self._market_is_open(
                asset_class=asset_class,
            )

            if market_is_open:
                result = await self.next_prediction(
                    ticker=ticker,
                    asset_class=asset_class,
                )

                yield result

            await asyncio.sleep(
                self.interval_seconds,
            )
