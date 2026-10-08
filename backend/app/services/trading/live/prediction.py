"""
prediction.py - Live market-data to ML inference orchestration.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.services.trading.live.market_data import MarketDataService
from app.services.trading.live.provider import MarketDataProvider
from app.services.trading.live.session import MarketSessionService
from app.services.trading.ml.inference import inference_service


class MarketSessionClosedError(RuntimeError):
    """
    Raised when fresh ML inference is requested outside the
    active market session.
    """

    def __init__(
        self,
        asset_class: str,
        next_open: str | None = None,
    ) -> None:
        self.asset_class = asset_class
        self.next_open = next_open

        if next_open:
            message = (
                f"The {asset_class} market is currently closed. "
                f"Fresh inference resumes at {next_open}."
            )
        else:
            message = (
                f"The {asset_class} market is currently closed."
            )

        super().__init__(message)


class ModelUnavailableError(RuntimeError):
    """
    Raised when an asset has live market data but no complete
    production ML model artifact is available.
    """

    def __init__(
        self,
        ticker: str,
        asset_class: str,
    ) -> None:
        self.ticker = ticker
        self.asset_class = asset_class

        message = (
            f"No production ML model is currently available "
            f"for {ticker} ({asset_class})."
        )

        super().__init__(message)


class LivePredictionService:
    """
    Orchestrates live market data and the existing production
    inference service.

    This class does not implement feature engineering, scaling,
    model loading, strategy logic, or order execution.

    Fresh inference is only permitted when the relevant market
    session is open.
    """

    def __init__(
        self,
        provider: MarketDataProvider,
        bars_limit: int = 100,
        session_service: MarketSessionService | None = None,
    ) -> None:
        if bars_limit <= 0:
            raise ValueError(
                "bars_limit must be greater than zero."
            )

        self.provider = provider
        self.bars_limit = bars_limit
        self.session_service = session_service

    @staticmethod
    def _serialize_bars(
        bars: pd.DataFrame,
    ) -> list[dict[str, Any]]:
        """
        Convert canonical provider bars into Zebio's frontend
        market-bar representation.

        Provider schema:
            first
            high
            low
            last
            volume

        Frontend schema:
            timestamp
            open
            high
            low
            close
            volume
        """

        result: list[dict[str, Any]] = []

        for timestamp, row in bars.iterrows():
            result.append(
                {
                    "timestamp": (
                        pd.Timestamp(timestamp)
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

        return result

    def _require_open_session(
        self,
        asset_class: str,
    ) -> None:
        """
        Prevent fresh inference when the market is closed.

        If no session service has been injected, inference remains
        available for backwards compatibility. The application
        wires the real session service during normal startup.
        """

        if self.session_service is None:
            return

        session = self.session_service.get_status(
            asset_class=asset_class,
        )

        if session.is_open:
            return

        raise MarketSessionClosedError(
            asset_class=session.asset_class,
            next_open=session.next_open,
        )

    def _require_model(
        self,
        ticker: str,
        asset_class: str,
    ) -> None:
        """
        Prevent live inference when no production model exists.

        Model availability is determined entirely by the inference
        service's complete artifact discovery.
        """

        if inference_service.supports_ticker(ticker):
            return

        raise ModelUnavailableError(
            ticker=ticker,
            asset_class=asset_class,
        )

    def predict(
        self,
        ticker: str,
        asset_class: str = "stocks",
    ) -> dict[str, Any]:
        """
        Fetch recent live bars and produce an ML prediction.

        Fresh inference is only performed during an active market
        session and when a complete production model is available.

        The returned payload contains both the exact market bars
        used for inference and the resulting prediction.
        """

        normalized = ticker.upper().strip()

        if not normalized:
            raise ValueError(
                "Ticker must not be empty."
            )

        normalized_asset_class = asset_class.lower().strip()

        if not normalized_asset_class:
            raise ValueError(
                "Asset class must not be empty."
            )

        self._require_open_session(
            asset_class=normalized_asset_class,
        )

        self._require_model(
            ticker=normalized,
            asset_class=normalized_asset_class,
        )

        bars = self.provider.get_recent_bars(
            normalized,
            limit=self.bars_limit,
            asset_class=normalized_asset_class,
        )

        if bars is None or bars.empty:
            raise ValueError(
                f"No live market data available for '{normalized}'."
            )

        prediction = inference_service.predict(
            normalized,
            bars,
        )

        return {
            "ticker": normalized,
            "asset_class": normalized_asset_class,
            "bars": self._serialize_bars(bars),
            "prediction": prediction,
        }
