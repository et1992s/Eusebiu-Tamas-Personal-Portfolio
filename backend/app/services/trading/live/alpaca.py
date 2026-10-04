"""
alpaca.py - Alpaca market-data adapter for Zebio live trading data.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os

import pandas as pd

from alpaca.data.enums import DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.historical.crypto import (
    CryptoHistoricalDataClient,
    CryptoBarsRequest,
)
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import (
    AssetClass as TradingAssetClass,
    AssetStatus,
)
from alpaca.trading.requests import GetAssetsRequest

from app.services.trading.live.provider import MarketDataProvider


class AlpacaMarketDataProvider(MarketDataProvider):
    """
    Alpaca implementation of the Zebio market-data provider contract.

    Supports:
        - stocks / ETFs through StockHistoricalDataClient
        - crypto through CryptoHistoricalDataClient

    Both return the same canonical Zebio OHLCV schema.
    """

    HISTORICAL_LOOKBACK_DAYS = 3

    def __init__(
        self,
        api_key=None,
        api_secret=None,
        feed=DataFeed.IEX,
    ):
        self.api_key = (
            api_key
            or os.getenv("ALPACA_API_KEY")
        )

        self.api_secret = (
            api_secret
            or os.getenv("ALPACA_API_SECRET")
        )

        self.feed = feed

        if not self.api_key:
            raise RuntimeError(
                "ALPACA_API_KEY is not configured."
            )

        if not self.api_secret:
            raise RuntimeError(
                "ALPACA_API_SECRET is not configured."
            )

        self.stock_client = StockHistoricalDataClient(
            self.api_key,
            self.api_secret,
        )

        self.crypto_client = CryptoHistoricalDataClient(
            self.api_key,
            self.api_secret,
        )

        self.trading_client = TradingClient(
            self.api_key,
            self.api_secret,
            paper=True,
        )

    @staticmethod
    def _empty_bars() -> pd.DataFrame:
        return pd.DataFrame(
            columns=[
                "first",
                "high",
                "low",
                "last",
                "volume",
            ],
            index=pd.DatetimeIndex(
                [],
                name="timestamp",
            ),
        )

    @staticmethod
    def _normalise_bars(
        dataframe: pd.DataFrame,
        symbol: str,
    ) -> pd.DataFrame:
        """
        Convert Alpaca OHLCV output into Zebio format.
        """

        if (
            dataframe is None
            or dataframe.empty
        ):
            return AlpacaMarketDataProvider._empty_bars()

        if isinstance(
            dataframe.index,
            pd.MultiIndex,
        ):
            dataframe = dataframe.xs(
                symbol,
                level="symbol",
            )

        dataframe = dataframe.rename(
            columns={
                "open": "first",
                "close": "last",
            }
        )

        dataframe = dataframe[
            [
                "first",
                "high",
                "low",
                "last",
                "volume",
            ]
        ].copy()

        dataframe.index = pd.to_datetime(
            dataframe.index,
            utc=True,
        )

        dataframe.index.name = "timestamp"

        return dataframe.sort_index()

    @classmethod
    def _historical_window(cls) -> tuple[datetime, datetime]:
        """
        Return an explicit historical request window.

        The window is deliberately broader than a single trading
        session so the provider continues to work across weekends
        and market closures.
        """

        end = datetime.now(
            timezone.utc,
        )

        start = (
            end
            - timedelta(
                days=cls.HISTORICAL_LOOKBACK_DAYS,
            )
        )

        return start, end

    def get_recent_bars(
        self,
        ticker: str,
        limit: int = 100,
        asset_class: str = "stocks",
    ) -> pd.DataFrame:
        """
        Return the most recent 1-minute bars for the given ticker.

        Routes according to asset class:
            - crypto → CryptoHistoricalDataClient
            - stocks / ETFs → StockHistoricalDataClient

        An explicit historical window is used so the method remains
        useful when the market is closed.
        """

        normalized = ticker.upper().strip()
        normalized_asset_class = asset_class.lower().strip()

        if not normalized:
            raise ValueError(
                "Ticker must not be empty."
            )

        if limit <= 0:
            raise ValueError(
                "limit must be greater than zero."
            )

        if normalized_asset_class == "crypto":
            return self.get_recent_crypto_bars(
                normalized,
                limit=limit,
            )

        if normalized_asset_class not in {
            "stocks",
            "etf",
        }:
            raise ValueError(
                f"Unsupported asset class: {asset_class}"
            )

        start, end = self._historical_window()

        request = StockBarsRequest(
            symbol_or_symbols=[normalized],
            timeframe=TimeFrame.Minute,
            start=start,
            end=end,
            limit=limit,
            feed=self.feed,
        )

        bars = self.stock_client.get_stock_bars(
            request
        )

        dataframe = self._normalise_bars(
            bars.df,
            normalized,
        )

        if dataframe.empty:
            return dataframe

        return dataframe.tail(limit)

    def get_recent_crypto_bars(
        self,
        symbol: str,
        limit: int = 100,
    ) -> pd.DataFrame:
        """
        Return the most recent crypto 1-minute bars.

        Example:
            BTC/USD
            ETH/USD
        """

        normalized = symbol.upper().strip()

        if not normalized:
            raise ValueError(
                "Crypto symbol must not be empty."
            )

        if limit <= 0:
            raise ValueError(
                "limit must be greater than zero."
            )

        start, end = self._historical_window()

        request = CryptoBarsRequest(
            symbol_or_symbols=[normalized],
            timeframe=TimeFrame.Minute,
            start=start,
            end=end,
            limit=limit,
        )

        bars = self.crypto_client.get_crypto_bars(
            request
        )

        dataframe = self._normalise_bars(
            bars.df,
            normalized,
        )

        if dataframe.empty:
            return dataframe

        return dataframe.tail(limit)

    def get_tradable_assets(
        self,
        asset_class: str = "stocks",
    ) -> list[dict]:
        """
        Return tradable assets for the requested asset class.
        """

        normalized = asset_class.lower().strip()

        if normalized == "crypto":
            requested_class = TradingAssetClass.CRYPTO
        elif normalized == "stocks":
            requested_class = TradingAssetClass.US_EQUITY
        elif normalized == "etf":
            requested_class = TradingAssetClass.US_EQUITY
        else:
            raise ValueError(
                f"Unsupported asset class: {asset_class}"
            )

        request = GetAssetsRequest(
            status=AssetStatus.ACTIVE,
            asset_class=requested_class,
        )

        assets = self.trading_client.get_all_assets(
            request
        )

        result = []

        for asset in assets:
            if not asset.tradable:
                continue

            if normalized == "etf":
                if getattr(asset, "class_", None) != "us_equity":
                    continue

                if not getattr(asset, "exchange", None):
                    continue

            result.append(
                {
                    "symbol": asset.symbol,
                    "name": asset.name,
                    "exchange": str(asset.exchange),
                    "tradable": asset.tradable,
                }
            )

        return result