"""
position_monitor.py - Paper position exit monitoring.

Responsibilities:
    - evaluate an open paper position against the Trading Lab exit rules
    - determine whether stop-loss, take-profit, or sell-signal conditions
      have been met
    - close eligible positions through PaperRepository

This service does not:
    - fetch market data
    - perform ML inference
    - manage market sessions
    - run a background loop
    - expose HTTP endpoints

Exit semantics match the existing Trading Lab backtest:

    current_price <= stop_loss
        -> stop_loss

    current_price >= take_profit
        -> take_profit

    predicted_return < sell_threshold
        -> signal

    otherwise
        -> HOLD
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.trading.paper.repository import PaperRepository


@dataclass(frozen=True)
class PositionMonitorConfig:
    """
    Exit parameters matching the existing Trading Lab strategy.
    """

    sell_threshold: float = 0.005

    def __post_init__(self) -> None:
        if not 0.0 <= self.sell_threshold <= 0.20:
            raise ValueError(
                "sell_threshold must be between 0.0 and 0.20."
            )


class PaperPositionMonitor:
    """
    Evaluate and execute exits for existing paper positions.
    """

    def __init__(
        self,
        repository: PaperRepository,
        config: PositionMonitorConfig | None = None,
    ) -> None:
        self.repository = repository
        self.config = (
            config
            or PositionMonitorConfig()
        )

    def evaluate_exit(
        self,
        position: dict[str, Any],
        current_price: float,
        predicted_return: float,
    ) -> dict[str, Any]:
        """
        Evaluate one open position without modifying database state.
        """

        if not isinstance(position, dict):
            raise TypeError(
                "position must be a dictionary."
            )

        position_id = position.get("id")

        if position_id is None:
            raise ValueError(
                "Position must contain an id."
            )

        ticker = str(
            position.get("ticker", "")
        ).strip().upper()

        if not ticker:
            raise ValueError(
                "Position ticker must not be empty."
            )

        if position.get("status") != "OPEN":
            raise ValueError(
                f"Position {position_id} "
                "is not open."
            )

        if current_price <= 0:
            raise ValueError(
                "current_price must be greater than zero."
            )

        if not isinstance(
            predicted_return,
            (int, float),
        ):
            raise TypeError(
                "predicted_return must be numeric."
            )

        price = float(current_price)
        predicted = float(predicted_return)

        stop_loss = position.get("stop_loss")
        take_profit = position.get("take_profit")

        if stop_loss is None:
            raise ValueError(
                f"Position {position_id} "
                "does not have a stop-loss price."
            )

        if take_profit is None:
            raise ValueError(
                f"Position {position_id} "
                "does not have a take-profit price."
            )

        stop_loss_price = float(stop_loss)
        take_profit_price = float(
            take_profit
        )

        if stop_loss_price <= 0:
            raise ValueError(
                f"Invalid stop-loss price "
                f"for position {position_id}."
            )

        if take_profit_price <= 0:
            raise ValueError(
                f"Invalid take-profit price "
                f"for position {position_id}."
            )

        if price <= stop_loss_price:
            return {
                "position_id": int(
                    position_id
                ),
                "ticker": ticker,
                "should_exit": True,
                "action": "SELL",
                "reason": "stop_loss",
                "current_price": price,
                "predicted_return": predicted,
                "sell_threshold": (
                    self.config.sell_threshold
                ),
                "stop_loss": stop_loss_price,
                "take_profit": take_profit_price,
            }

        if price >= take_profit_price:
            return {
                "position_id": int(
                    position_id
                ),
                "ticker": ticker,
                "should_exit": True,
                "action": "SELL",
                "reason": "take_profit",
                "current_price": price,
                "predicted_return": predicted,
                "sell_threshold": (
                    self.config.sell_threshold
                ),
                "stop_loss": stop_loss_price,
                "take_profit": take_profit_price,
            }

        if predicted < self.config.sell_threshold * -1:
            return {
                "position_id": int(
                    position_id
                ),
                "ticker": ticker,
                "should_exit": True,
                "action": "SELL",
                "reason": "signal",
                "current_price": price,
                "predicted_return": predicted,
                "sell_threshold": (
                    self.config.sell_threshold
                ),
                "stop_loss": stop_loss_price,
                "take_profit": take_profit_price,
            }

        return {
            "position_id": int(
                position_id
            ),
            "ticker": ticker,
            "should_exit": False,
            "action": "HOLD",
            "reason": "exit_conditions_not_met",
            "current_price": price,
            "predicted_return": predicted,
            "sell_threshold": (
                self.config.sell_threshold
            ),
            "stop_loss": stop_loss_price,
            "take_profit": take_profit_price,
        }

    def execute_exit(
        self,
        position: dict[str, Any],
        current_price: float,
        predicted_return: float,
        exit_time: str | None = None,
        fees: float = 0.0,
    ) -> dict[str, Any]:
        """
        Evaluate and, when required, close the paper position.
        """

        evaluation = self.evaluate_exit(
            position=position,
            current_price=current_price,
            predicted_return=predicted_return,
        )

        if not evaluation["should_exit"]:
            return {
                "executed": False,
                "evaluation": evaluation,
            }

        trade = self.repository.close_position(
            position_id=evaluation[
                "position_id"
            ],
            exit_price=evaluation[
                "current_price"
            ],
            exit_reason=evaluation[
                "reason"
            ],
            exit_time=exit_time,
            fees=fees,
        )

        return {
            "executed": True,
            "action": "SELL",
            "evaluation": evaluation,
            "execution": trade,
        }

    def monitor_portfolio(
        self,
        portfolio_id: int,
        market_state: dict[
            str,
            dict[str, float],
        ],
    ) -> list[dict[str, Any]]:
        """
        Evaluate all open positions in a portfolio.

        market_state maps ticker to:

            {
                "current_price": float,
                "predicted_return": float,
            }

        Positions without corresponding market data are skipped.
        """

        positions = self.repository.open_positions(
            portfolio_id
        )

        results: list[dict[str, Any]] = []

        for position in positions:
            ticker = str(
                position["ticker"]
            ).strip().upper()

            state = market_state.get(
                ticker
            )

            if state is None:
                results.append(
                    {
                        "executed": False,
                        "skipped": True,
                        "reason": "market_data_unavailable",
                        "position_id": position[
                            "id"
                        ],
                        "ticker": ticker,
                    }
                )
                continue

            result = self.execute_exit(
                position=position,
                current_price=float(
                    state["current_price"]
                ),
                predicted_return=float(
                    state["predicted_return"]
                ),
            )

            results.append(result)

        return results

    def strategy_parameters(self) -> dict[str, float]:
        """
        Return the active exit strategy configuration.
        """

        return {
            "sell_threshold": (
                self.config.sell_threshold
            ),
        }