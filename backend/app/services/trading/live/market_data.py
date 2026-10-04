"""
market_data.py - Market-data orchestration for Zebio.

Coordinates live Alpaca data with persistent market-data storage.

Architecture:

    AlpacaMarketDataProvider
            |
            v
      MarketDataService
         |        |
         |        v
         |   MarketDataStore
         |
         v
    canonical 1-minute bars

The service also implements the existing MarketDataProvider
interface so downstream chart and inference services do not need
to know whether data came from Alpaca or persistent storage.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.services.trading.live.market_store import MarketDataStore
from app.services.trading.live.provider import MarketDataProvider


CANONICAL_COLUMNS = [
    "first",
    "high",
    "low",
    "last",
    "volume",
]


@dataclass(frozen=True)
class MarketDataResult:
    """
    Result returned by MarketDataService.

    bars:
        Canonical 1-minute OHLCV market data.

    source:
        "alpaca" when freshly retrieved from Alpaca.
        "historical_cache" when retrieved from persistent storage.
    """

    bars: pd.DataFrame
    source: str

    @property
    def is_live(self) -> bool:
        """
        Whether the bars came directly from Alpaca.
        """

        return self.source == "alpaca"


class MarketDataService(MarketDataProvider):
    """
    Coordinates live market-data retrieval and persistence.

    The live provider is always preferred.

    When the live provider has no data, the most recently persisted
    session is returned instead.

    This class implements MarketDataProvider so existing chart and
    inference services can consume it without knowing about storage.
    """

    LIVE_SOURCE = "alpaca"
    CACHE_SOURCE = "historical_cache"

    def __init__(
        self,
        provider: MarketDataProvider,
        store: MarketDataStore,
    ) -> None:
        self.provider = provider
        self.store = store

    def get_bars(
        self,
        ticker: str,
        limit: int = 100,
        asset_class: str = "stocks",
    ) -> MarketDataResult:
        normalized_ticker = ticker.upper().strip()

        if not normalized_ticker:
            raise ValueError(
                "Ticker must not be empty."
            )

        if limit <= 0:
            raise ValueError(
                "limit must be greater than zero."
            )

        normalized_asset_class = asset_class.lower().strip()

        if not normalized_asset_class:
            raise ValueError(
                "Asset class must not be empty."
            )

        live_bars = self.provider.get_recent_bars(
            normalized_ticker,
            limit=limit,
            asset_class=normalized_asset_class,
        )

        if live_bars is not None and not live_bars.empty:
            self.store.save_bars(
                normalized_ticker,
                live_bars,
                asset_class=normalized_asset_class,
                source=self.LIVE_SOURCE,
            )

            return MarketDataResult(
                bars=live_bars,
                source=self.LIVE_SOURCE,
            )

        cached_bars = self.store.get_latest_session(
            normalized_ticker,
            asset_class=normalized_asset_class,
            limit=limit,
        )

        if cached_bars is not None and not cached_bars.empty:
            return MarketDataResult(
                bars=cached_bars,
                source=self.CACHE_SOURCE,
            )

        return MarketDataResult(
            bars=self._empty_bars(),
            source=self.CACHE_SOURCE,
        )


    def get_recent_bars(
        self,
        ticker: str,
        limit: int = 100,
        asset_class: str = "stocks",
    ) -> pd.DataFrame:
        result = self.get_bars(
            ticker=ticker,
            limit=limit,
            asset_class=asset_class,
        )

        return result.bars

    @staticmethod
    def _empty_bars() -> pd.DataFrame:
        """
        Return an empty canonical market-data DataFrame.
        """

        return pd.DataFrame(
            columns=CANONICAL_COLUMNS,
            index=pd.DatetimeIndex(
                [],
                name="timestamp",
            ),
        )