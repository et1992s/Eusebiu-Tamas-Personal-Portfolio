"""
alpaca.py - Alpaca market-data adapter for Zebio live trading data.
"""

import os

import pandas as pd

from alpaca.data.enums import DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.historical.crypto import (
    CryptoHistoricalDataClient,
)
from alpaca.data.requests import StockBarsRequest
from alpaca.data.historical.crypto import (
    CryptoBarsRequest,
)
from alpaca.data.timeframe import TimeFrame

from app.services.trading.live.provider import MarketDataProvider

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetAssetsRequest
from alpaca.trading.enums import AssetClass as TradingAssetClass, AssetStatus


class AlpacaMarketDataProvider(MarketDataProvider):
    """
    Alpaca implementation of the Zebio market-data provider contract.

    Supports:
        - stocks / ETFs through StockHistoricalDataClient
        - crypto through CryptoHistoricalDataClient

    Both return the same canonical Zebio OHLCV schema.
    """

    def __init__(
        self,
        api_key=None,
        api_secret=None,
        feed= DataFeed.IEX,
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


    def get_recent_bars(
        self,
        ticker: str,
        limit: int = 100,
    ) -> pd.DataFrame:
        """
        Return recent 1-minute bars for the given ticker.

        Routes automatically:
            - Crypto symbols (containing '/') use the crypto client
            - Everything else (stocks, ETFs) uses the equity client
        """

        normalized = ticker.upper().strip()

        if not normalized:
            raise ValueError(
                "Ticker must not be empty."
            )

        # ── Crypto routing ──────────────────────────────────────
        # Alpaca crypto symbols look like "BTC/USD", "ETH/USD".
        if "/" in normalized:
            return self.get_recent_crypto_bars(
                normalized,
                limit=limit,
            )

        # ── Equity / ETF path (unchanged) ───────────────────────
        request = StockBarsRequest(
            symbol_or_symbols=[normalized],
            timeframe=TimeFrame.Minute,
            limit=limit,
            feed=self.feed,
        )

        bars = self.stock_client.get_stock_bars(request)

        return self._normalise_bars(bars.df, normalized)


    def get_recent_crypto_bars(
        self,
        symbol: str,
        limit: int = 100,
    ) -> pd.DataFrame:
        """
        Return recent crypto 1-minute bars.

        Example:
            BTC/USD
            ETH/USD
        """

        normalized = symbol.upper().strip()

        if not normalized:
            raise ValueError(
                "Crypto symbol must not be empty."
            )

        request = CryptoBarsRequest(
            symbol_or_symbols=[
                normalized
            ],
            timeframe=TimeFrame.Minute,
            limit=limit,
        )

        bars = self.crypto_client.get_crypto_bars(
            request
        )

        return self._normalise_bars(
            bars.df,
            normalized,
        )

    def get_tradable_assets(self, asset_class: str = "stocks") -> list[dict]:
        """
        Fetch tradable symbols directly from Alpaca.

        asset_class: "stocks" | "etf" | "crypto"
        """
        if asset_class == "crypto":
            request = GetAssetsRequest(asset_class=TradingAssetClass.CRYPTO)
        else:
            request = GetAssetsRequest(asset_class=TradingAssetClass.US_EQUITY)

        assets = self.trading_client.get_all_assets(request)

        result: list[dict] = []

        for asset in assets:
            if not asset.tradable:
                continue
            if asset.status != AssetStatus.ACTIVE:
                continue

            attributes = [a.lower() for a in (asset.attributes or [])]
            is_etf = "etf" in attributes

            if asset_class == "crypto":
                result.append({
                    "symbol": asset.symbol,
                    "name": asset.name,
                    "asset_class": "crypto",
                })
            elif asset_class == "etf" and is_etf:
                result.append({
                    "symbol": asset.symbol,
                    "name": asset.name,
                    "asset_class": "etf",
                })
            elif asset_class == "stocks" and not is_etf:
                result.append({
                    "symbol": asset.symbol,
                    "name": asset.name,
                    "asset_class": "stocks",
                })

        result.sort(key=lambda x: x["symbol"])
        return result