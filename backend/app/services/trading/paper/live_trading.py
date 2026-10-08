"""
live_trading.py - Live prediction to paper-trading orchestration.
"""

from __future__ import annotations

from typing import Any

from app.services.trading.live.prediction import (
    LivePredictionService,
)
from app.services.trading.paper.live_execution import (
    LivePaperExecutionService,
)
from app.services.trading.paper.position_monitor import (
    PaperPositionMonitor,
)
from app.services.trading.paper.repository import (
    PaperRepository,
)


class LivePaperTradingService:
    """
    Orchestrate live ML predictions through the paper-trading lifecycle.

    A ticker with no open position is evaluated for entry.

    A ticker with an existing open position is evaluated for exit.

    This service does not fetch market data or perform ML inference.
    """

    def __init__(
        self,
        prediction_service: LivePredictionService,
        repository: PaperRepository,
        entry_service: LivePaperExecutionService,
        position_monitor: PaperPositionMonitor,
        portfolio_name: str = "default",
    ) -> None:
        normalized_name = portfolio_name.strip()

        if not normalized_name:
            raise ValueError(
                "portfolio_name must not be empty."
            )

        self.prediction_service = prediction_service
        self.repository = repository
        self.entry_service = entry_service
        self.position_monitor = position_monitor
        self.portfolio_name = normalized_name

    def _portfolio_id(self) -> int:
        portfolio = self.repository.get_portfolio(
            self.portfolio_name
        )

        if portfolio is None:
            raise ValueError(
                f"Paper portfolio "
                f"'{self.portfolio_name}' "
                f"not found."
            )

        return int(portfolio["id"])

    def _find_open_position(
        self,
        portfolio_id: int,
        ticker: str,
    ) -> dict[str, Any] | None:
        normalized_ticker = ticker.strip().upper()

        for position in self.repository.open_positions(
            portfolio_id
        ):
            position_ticker = str(
                position.get("ticker", "")
            ).strip().upper()

            if position_ticker == normalized_ticker:
                return position

        return None

    @staticmethod
    def _extract_prediction(
        prediction_payload: dict[str, Any],
    ) -> float:
        prediction = prediction_payload.get(
            "prediction"
        )

        if not isinstance(prediction, dict):
            raise ValueError(
                "Live prediction payload must contain "
                "a dictionary under 'prediction'."
            )

        predicted_return = prediction.get(
            "predicted_return"
        )

        if not isinstance(
            predicted_return,
            (int, float),
        ):
            raise ValueError(
                "Live prediction payload must contain "
                "a numeric 'predicted_return'."
            )

        return float(predicted_return)

    @staticmethod
    def _extract_current_price(
        prediction_payload: dict[str, Any],
    ) -> float:
        bars = prediction_payload.get("bars")

        if not isinstance(bars, list) or not bars:
            raise ValueError(
                "Live prediction payload must contain "
                "at least one market bar."
            )

        latest_bar = bars[-1]

        if not isinstance(latest_bar, dict):
            raise ValueError(
                "Latest market bar must be a dictionary."
            )

        close = latest_bar.get("close")

        if not isinstance(
            close,
            (int, float),
        ):
            raise ValueError(
                "Latest market bar must contain "
                "a numeric 'close' value."
            )

        price = float(close)

        if price <= 0:
            raise ValueError(
                "Latest market close must be greater "
                "than zero."
            )

        return price

    def process_prediction(
        self,
        prediction_payload: dict[str, Any],
        entry_time: str | None = None,
        exit_time: str | None = None,
        fees: float = 0.0,
    ) -> dict[str, Any]:
        """
        Process an already-generated live prediction.

        This method deliberately does not call LivePredictionService.
        The prediction has already been produced by LivePredictionStream.
        """

        if not isinstance(prediction_payload, dict):
            raise TypeError(
                "prediction_payload must be a dictionary."
            )

        ticker = str(
            prediction_payload.get("ticker", "")
        ).strip().upper()

        if not ticker:
            raise ValueError(
                "Prediction payload must contain a ticker."
            )

        asset_class = str(
            prediction_payload.get(
                "asset_class",
                "stocks",
            )
        ).strip().lower()

        current_price = self._extract_current_price(
            prediction_payload
        )

        predicted_return = self._extract_prediction(
            prediction_payload
        )

        portfolio_id = self._portfolio_id()

        position = self._find_open_position(
            portfolio_id=portfolio_id,
            ticker=ticker,
        )

        if position is None:
            execution = self.entry_service.execute_entry(
                ticker=ticker,
                current_price=current_price,
                predicted_return=predicted_return,
                signal="BUY",
                entry_time=entry_time,
            )

            return {
                "ticker": ticker,
                "asset_class": asset_class,
                "mode": "ENTRY",
                "current_price": current_price,
                "predicted_return": predicted_return,
                "prediction": prediction_payload[
                    "prediction"
                ],
                "executed": bool(
                    execution.get(
                        "executed",
                        False,
                    )
                ),
                "evaluation": execution.get(
                    "evaluation"
                ),
                "execution": execution.get(
                    "execution"
                ),
            }

        execution = self.position_monitor.execute_exit(
            position=position,
            current_price=current_price,
            predicted_return=predicted_return,
            exit_time=exit_time,
            fees=fees,
        )

        return {
            "ticker": ticker,
            "asset_class": asset_class,
            "mode": "EXIT",
            "current_price": current_price,
            "predicted_return": predicted_return,
            "prediction": prediction_payload[
                "prediction"
            ],
            "position": position,
            "executed": bool(
                execution.get(
                    "executed",
                    False,
                )
            ),
            "evaluation": execution.get(
                "evaluation"
            ),
            "execution": execution.get(
                "execution"
            ),
        }

    def process_ticker(
        self,
        ticker: str,
        asset_class: str = "stocks",
        entry_time: str | None = None,
        exit_time: str | None = None,
        fees: float = 0.0,
    ) -> dict[str, Any]:
        """
        Request one live prediction and process it.

        This convenience method is retained for callers that do not
        already have a prediction stream.
        """

        normalized_ticker = ticker.strip().upper()

        if not normalized_ticker:
            raise ValueError(
                "ticker must not be empty."
            )

        prediction_payload = (
            self.prediction_service.predict(
                normalized_ticker,
                asset_class=asset_class,
            )
        )

        return self.process_prediction(
            prediction_payload=prediction_payload,
            entry_time=entry_time,
            exit_time=exit_time,
            fees=fees,
        )

    def strategy_parameters(self) -> dict[str, Any]:
        return {
            "entry": (
                self.entry_service.strategy_parameters()
            ),
            "exit": (
                self.position_monitor.strategy_parameters()
            ),
        }