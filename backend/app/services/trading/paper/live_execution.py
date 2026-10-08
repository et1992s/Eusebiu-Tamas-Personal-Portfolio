"""
live_execution.py - Live signal to paper-position execution.

This service bridges the live ML/strategy layer and the paper-trading
repository.

Responsibilities:
    - evaluate a live prediction against the Trading Lab entry threshold
    - calculate paper position quantity from configured capital
    - calculate absolute stop-loss and take-profit prices
    - persist an approved paper position transactionally
    - return a structured execution result

This service does not:
    - fetch market data
    - perform ML inference
    - determine market-session state
    - calculate model features
    - close positions
    - perform portfolio valuation
    - expose HTTP endpoints
    - run a background loop

Lifecycle:

    LivePredictionService
            |
            v
    predicted return + current price
            |
            v
    LivePaperExecutionService
            |
            v
    PaperRepository.open_position()
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.trading.paper.repository import PaperRepository


@dataclass(frozen=True)
class LiveStrategyConfig:
    """
    Trading Lab strategy parameters used for live paper execution.

    The defaults intentionally match the existing backtest defaults in
    app.api.trading.BacktestRequest.
    """

    buy_threshold: float = 0.005
    sell_threshold: float = 0.005
    stop_loss: float = 0.02
    take_profit: float = 0.02
    position_size: float = 1000.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.buy_threshold <= 0.20:
            raise ValueError(
                "buy_threshold must be between 0.0 and 0.20."
            )

        if not 0.0 <= self.sell_threshold <= 0.20:
            raise ValueError(
                "sell_threshold must be between 0.0 and 0.20."
            )

        if not 0.0 <= self.stop_loss <= 0.50:
            raise ValueError(
                "stop_loss must be between 0.0 and 0.50."
            )

        if not 0.0 <= self.take_profit <= 0.50:
            raise ValueError(
                "take_profit must be between 0.0 and 0.50."
            )

        if self.position_size <= 0:
            raise ValueError(
                "position_size must be greater than zero."
            )


class LivePaperExecutionService:
    """
    Convert a validated live trading signal into a paper position.

    The service deliberately operates on primitive trading inputs rather
    than the full LivePredictionService payload. This keeps the execution
    boundary independent from the ML inference response structure.

    Entry semantics match the existing Trading Lab backtest:

        predicted_return > buy_threshold
            -> eligible for LONG entry

        predicted_return <= buy_threshold
            -> no entry
    """

    def __init__(
        self,
        repository: PaperRepository,
        portfolio_name: str = "default",
        strategy: LiveStrategyConfig | None = None,
    ) -> None:
        normalized_name = portfolio_name.strip()

        if not normalized_name:
            raise ValueError(
                "portfolio_name must not be empty."
            )

        self.repository = repository
        self.portfolio_name = normalized_name
        self.strategy = (
            strategy
            or LiveStrategyConfig()
        )

    def evaluate_entry(
        self,
        ticker: str,
        current_price: float,
        predicted_return: float,
    ) -> dict[str, Any]:
        """
        Evaluate whether the current prediction qualifies for entry.

        This method does not modify paper-trading state.
        """

        normalized_ticker = ticker.strip().upper()

        if not normalized_ticker:
            raise ValueError(
                "Ticker must not be empty."
            )

        if current_price <= 0:
            raise ValueError(
                "current_price must be greater than zero."
            )

        if not isinstance(predicted_return, (int, float)):
            raise TypeError(
                "predicted_return must be numeric."
            )

        predicted = float(predicted_return)
        price = float(current_price)

        eligible = (
            predicted
            > self.strategy.buy_threshold
        )

        if not eligible:
            return {
                "ticker": normalized_ticker,
                "eligible": False,
                "action": "HOLD",
                "reason": "buy_threshold_not_met",
                "current_price": price,
                "predicted_return": predicted,
                "buy_threshold": (
                    self.strategy.buy_threshold
                ),
            }

        quantity = (
            self.strategy.position_size
            / price
        )

        stop_loss_price = (
            price
            * (1.0 - self.strategy.stop_loss)
        )

        take_profit_price = (
            price
            * (1.0 + self.strategy.take_profit)
        )

        return {
            "ticker": normalized_ticker,
            "eligible": True,
            "action": "BUY",
            "reason": "buy_threshold_met",
            "current_price": price,
            "predicted_return": predicted,
            "buy_threshold": (
                self.strategy.buy_threshold
            ),
            "position_size": (
                self.strategy.position_size
            ),
            "quantity": quantity,
            "stop_loss": (
                self.strategy.stop_loss
            ),
            "take_profit": (
                self.strategy.take_profit
            ),
            "stop_loss_price": stop_loss_price,
            "take_profit_price": take_profit_price,
        }

    def execute_entry(
        self,
        ticker: str,
        current_price: float,
        predicted_return: float,
        signal: str = "BUY",
        entry_time: str | None = None,
    ) -> dict[str, Any]:
        """
        Evaluate and, when eligible, persist a new paper position.

        A signal that does not satisfy the buy threshold is returned as a
        HOLD result and does not modify the database.

        Repository-level duplicate-position and cash validation remains
        authoritative.
        """

        evaluation = self.evaluate_entry(
            ticker=ticker,
            current_price=current_price,
            predicted_return=predicted_return,
        )

        if not evaluation["eligible"]:
            return {
                "executed": False,
                "evaluation": evaluation,
            }

        portfolio = self.repository.get_portfolio(
            self.portfolio_name
        )

        if portfolio is None:
            raise ValueError(
                f"Paper portfolio "
                f"'{self.portfolio_name}' "
                f"not found."
            )

        portfolio_id = int(
            portfolio["id"]
        )

        result = self.repository.open_position(
            portfolio_id=portfolio_id,
            ticker=evaluation["ticker"],
            quantity=evaluation["quantity"],
            entry_price=evaluation["current_price"],
            predicted_return=evaluation[
                "predicted_return"
            ],
            signal=signal,
            stop_loss=evaluation[
                "stop_loss_price"
            ],
            take_profit=evaluation[
                "take_profit_price"
            ],
            entry_time=entry_time,
        )

        return {
            "executed": True,
            "action": "BUY",
            "evaluation": evaluation,
            "execution": result,
        }

    def strategy_parameters(self) -> dict[str, float]:
        """
        Return the active strategy configuration.
        """

        return {
            "buy_threshold": (
                self.strategy.buy_threshold
            ),
            "sell_threshold": (
                self.strategy.sell_threshold
            ),
            "stop_loss": (
                self.strategy.stop_loss
            ),
            "take_profit": (
                self.strategy.take_profit
            ),
            "position_size": (
                self.strategy.position_size
            ),
        }