"""
provider.py - Market-data provider contract for live trading data.
"""

from abc import ABC, abstractmethod

import pandas as pd


class MarketDataProvider(ABC):
    """
    Abstract interface for live market-data providers.

    Providers must return Zebio's canonical OHLCV schema so that
    downstream feature engineering and ML inference remain
    provider-independent.
    """

    @abstractmethod
    def get_recent_bars(
        self,
        ticker: str,
        limit: int = 100,
        asset_class: str = "stocks",
    ) -> pd.DataFrame:
        """
        Return the most recent bars for a ticker and asset class.

        The returned DataFrame must contain:

            first
            high
            low
            last
            volume

        and must use a DatetimeIndex.

        Supported asset classes currently include:

            stocks
            etf
            crypto
        """
        raise NotImplementedError