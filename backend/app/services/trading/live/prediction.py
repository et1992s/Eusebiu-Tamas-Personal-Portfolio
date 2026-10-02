"""
prediction.py - Live market-data to ML inference orchestration.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.services.trading.live.provider import MarketDataProvider
from app.services.trading.ml.inference import inference_service


class LivePredictionService:
    """
    Orchestrates live market data and the existing production
    inference service.

    This class does not implement feature engineering, scaling,
    model loading, strategy logic, or order execution.
    """

    def __init__(
        self,
        provider: MarketDataProvider,
        bars_limit: int = 100,
    ) -> None:
        if bars_limit <= 0:
            raise ValueError(
                "bars_limit must be greater than zero."
            )

        self.provider = provider
        self.bars_limit = bars_limit

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

    def predict(
        self,
        ticker: str,
    ) -> dict[str, Any]:
        """
        Fetch recent live bars and produce an ML prediction.

        The returned payload contains both the exact market bars
        used for inference and the resulting prediction.
        """

        normalized = ticker.upper().strip()

        if not normalized:
            raise ValueError(
                "Ticker must not be empty."
            )

        bars = self.provider.get_recent_bars(
            normalized,
            limit=self.bars_limit,
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
            "bars": self._serialize_bars(bars),
            "prediction": prediction,
        }