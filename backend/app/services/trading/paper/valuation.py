"""
valuation.py - Read-only mark-to-market valuation for Zebio paper trading.

Coordinates:

    PaperRepository
            |
            v
      open positions
            |
            v
    MarketDataService
            |
            v
      current prices
            |
            v
    PaperValuationService
            |
            v
 current portfolio valuation

Responsibilities:
    - read the current paper portfolio
    - read open positions
    - obtain the latest market price for each position
    - calculate market value and unrealised P&L
    - calculate current portfolio equity
    - report the source of market data

This service is intentionally read-only.

It does not:
    - modify portfolio cash
    - modify positions
    - persist equity
    - create snapshots
    - execute trades
    - access Alpaca directly
"""

from __future__ import annotations

from typing import Any

from app.services.trading.live.market_data import MarketDataService
from app.services.trading.paper.repository import PaperRepository


class PaperValuationService:
    """
    Calculate the current mark-to-market value of a paper portfolio.

    The service consumes the existing MarketDataService abstraction so
    it remains independent of the underlying market-data provider.
    """

    def __init__(
        self,
        market_data: MarketDataService,
        repository: PaperRepository,
    ) -> None:
        self.market_data = market_data
        self.repository = repository

    def value_portfolio(
        self,
        portfolio_name: str = "default",
        asset_class: str = "stocks",
        bars_limit: int = 1,
    ) -> dict[str, Any]:
        """
        Calculate the current mark-to-market valuation.

        No database state is modified.

        Args:
            portfolio_name:
                Name of the paper portfolio to value.

            asset_class:
                Market-data asset class used when retrieving prices.

            bars_limit:
                Number of recent market bars requested per ticker.
                Valuation only requires the latest bar.

        Returns:
            A structured valuation containing portfolio-level metrics
            and per-position mark-to-market details.
        """
        normalized_name = portfolio_name.strip()

        if not normalized_name:
            raise ValueError("portfolio_name must not be empty.")

        normalized_asset_class = asset_class.strip().lower()

        if not normalized_asset_class:
            raise ValueError("asset_class must not be empty.")

        if bars_limit <= 0:
            raise ValueError("bars_limit must be greater than zero.")

        portfolio = self.repository.get_portfolio(normalized_name)

        if portfolio is None:
            raise ValueError(
                f"Paper portfolio '{normalized_name}' not found."
            )

        portfolio_id = int(portfolio["id"])
        cash = float(portfolio["cash"])
        initial_capital = float(portfolio["initial_capital"])

        open_positions = self.repository.open_positions(portfolio_id)

        valued_positions: list[dict[str, Any]] = []
        total_market_value = 0.0
        total_unrealised_pnl = 0.0
        market_data_sources: set[str] = set()

        for position in open_positions:
            valued_position = self._value_position(
                position=position,
                asset_class=normalized_asset_class,
                bars_limit=bars_limit,
            )

            valued_positions.append(valued_position)

            total_market_value += float(
                valued_position["market_value"]
            )

            total_unrealised_pnl += float(
                valued_position["unrealised_pnl"]
            )

            market_data_sources.add(
                str(valued_position["market_data_source"])
            )

        current_equity = cash + total_market_value
        cumulative_pnl = current_equity - initial_capital
        cumulative_pnl_pct = (
            cumulative_pnl / initial_capital
            if initial_capital
            else 0.0
        )

        market_data_source = self._resolve_source(
            market_data_sources
        )

        return {
            "portfolio": {
                "id": portfolio_id,
                "name": portfolio["name"],
                "currency": portfolio["currency"],
                "initial_capital": initial_capital,
                "cash": cash,
                "stored_equity": float(portfolio["equity"]),
                "equity": current_equity,
                "market_value": total_market_value,
                "unrealised_pnl": total_unrealised_pnl,
                "cumulative_pnl": cumulative_pnl,
                "cumulative_pnl_pct": cumulative_pnl_pct,
                "open_position_count": len(valued_positions),
                "market_data_source": market_data_source,
            },
            "positions": valued_positions,
        }

    def _value_position(
        self,
        position: dict[str, Any],
        asset_class: str,
        bars_limit: int,
    ) -> dict[str, Any]:
        ticker = str(position["ticker"]).strip().upper()
        quantity = float(position["quantity"])
        entry_price = float(position["entry_price"])

        if not ticker:
            raise ValueError("Open position contains an empty ticker.")

        if quantity <= 0:
            raise ValueError(
                f"Invalid quantity for {ticker}: {quantity}."
            )

        if entry_price <= 0:
            raise ValueError(
                f"Invalid entry price for {ticker}: {entry_price}."
            )

        market_data_result = self.market_data.get_bars(
            ticker=ticker,
            limit=bars_limit,
            asset_class=asset_class,
        )

        bars = market_data_result.bars

        if bars is None or bars.empty:
            raise ValueError(
                f"No market data available for {ticker}."
            )

        if "last" not in bars.columns:
            raise ValueError(
                f"Market data for {ticker} does not contain "
                "the required 'last' price column."
            )

        latest_price = bars["last"].iloc[-1]

        if latest_price is None:
            raise ValueError(
                f"Latest market price for {ticker} is missing."
            )

        current_price = float(latest_price)

        if current_price <= 0:
            raise ValueError(
                f"Invalid current market price for "
                f"{ticker}: {current_price}."
            )

        market_value = quantity * current_price
        entry_value = quantity * entry_price
        unrealised_pnl = market_value - entry_value

        unrealised_pnl_pct = (
            unrealised_pnl / entry_value
            if entry_value
            else 0.0
        )

        position_weight = 0.0

        return {
            "position_id": int(position["id"]),
            "portfolio_id": int(position["portfolio_id"]),
            "ticker": ticker,
            "side": position["side"],
            "quantity": quantity,
            "entry_price": entry_price,
            "current_price": current_price,
            "entry_value": entry_value,
            "market_value": market_value,
            "unrealised_pnl": unrealised_pnl,
            "unrealised_pnl_pct": unrealised_pnl_pct,
            "position_weight": position_weight,
            "entry_time": position["entry_time"],
            "predicted_return": position["predicted_return"],
            "signal": position["signal"],
            "market_data_source": market_data_result.source,
        }

    @staticmethod
    def _resolve_source(sources: set[str]) -> str:
        """
        Resolve the portfolio-level market-data source.

        With no open positions, there is no market-data source.

        If all positions use the same source, return that source.

        If positions were valued using different sources, explicitly
        report the mixed state rather than hiding the distinction.
        """
        if not sources:
            return "none"

        if len(sources) == 1:
            return next(iter(sources))

        return "mixed"