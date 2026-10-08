"""
session.py - Market-session state for Zebio live trading.

The session service determines whether an asset class is currently
eligible for fresh market-data-driven inference.

Responsibilities:
    - determine whether US equity markets are currently open
    - distinguish stocks/ETFs from continuously traded crypto
    - expose the current market clock without owning credentials
    - provide a small, testable abstraction for downstream services

This service does not:
    - retrieve market bars
    - perform ML inference
    - rank models
    - execute trades
    - value paper positions
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from alpaca.trading.client import TradingClient


SUPPORTED_ASSET_CLASSES = {
    "stocks",
    "etf",
    "crypto",
}


@dataclass(frozen=True)
class MarketSessionStatus:
    """
    Current market-session state for an asset class.

    asset_class:
        Normalised Zebio asset class.

    is_open:
        Whether fresh market-driven inference is currently permitted.

    status:
        Human-readable session state.

    next_open:
        Next known market-open timestamp when supplied by Alpaca.

    next_close:
        Next known market-close timestamp when supplied by Alpaca.
    """

    asset_class: str
    is_open: bool
    status: str
    next_open: str | None = None
    next_close: str | None = None


class MarketSessionService:
    """
    Determine whether an asset class is currently in an active
    trading session.

    Alpaca's TradingClient is injected rather than constructed here.
    This keeps authentication and provider configuration in the
    existing Alpaca adapter.
    """

    def __init__(
        self,
        trading_client: TradingClient,
    ) -> None:
        self.trading_client = trading_client

    def get_status(
        self,
        asset_class: str = "stocks",
    ) -> MarketSessionStatus:
        """
        Return the current market-session status.

        Stocks and ETFs use Alpaca's market clock.

        Crypto is treated as continuously open because it trades
        outside the US equity regular session.
        """

        normalized = asset_class.lower().strip()

        if normalized not in SUPPORTED_ASSET_CLASSES:
            raise ValueError(
                f"Unsupported asset class: {asset_class}"
            )

        if normalized == "crypto":
            return MarketSessionStatus(
                asset_class=normalized,
                is_open=True,
                status="open",
            )

        clock = self.trading_client.get_clock()

        is_open = bool(
            getattr(clock, "is_open", False)
        )

        next_open = self._serialize_timestamp(
            getattr(clock, "next_open", None)
        )

        next_close = self._serialize_timestamp(
            getattr(clock, "next_close", None)
        )

        return MarketSessionStatus(
            asset_class=normalized,
            is_open=is_open,
            status="open" if is_open else "closed",
            next_open=next_open,
            next_close=next_close,
        )

    def is_open(
        self,
        asset_class: str = "stocks",
    ) -> bool:
        """
        Return whether fresh inference is currently permitted.
        """

        return self.get_status(
            asset_class=asset_class,
        ).is_open

    @staticmethod
    def _serialize_timestamp(
        value: Any,
    ) -> str | None:
        """
        Convert an Alpaca timestamp into an ISO-8601 string.

        Alpaca normally returns timezone-aware datetime values.
        """

        if value is None:
            return None

        if hasattr(value, "isoformat"):
            return value.isoformat()

        return str(value)
