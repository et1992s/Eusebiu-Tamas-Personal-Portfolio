"""
allocator.py - Portfolio capital allocation for Zebio paper trading.

The allocator converts ranked trading opportunities into a deterministic
portfolio allocation proposal.

Responsibilities:
    - validate ranked long candidates
    - enforce portfolio and position constraints
    - avoid duplicate existing positions
    - calculate capital allocation
    - calculate position quantities
    - preserve unused cash when insufficient candidates qualify

This module does not:
    - access SQLite
    - access market-data providers
    - load ML models
    - execute trades
    - modify portfolio state

Execution and persistence remain separate concerns.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


DEFAULT_MAX_POSITIONS = 10
DEFAULT_MAX_POSITION_WEIGHT = 0.20
DEFAULT_MIN_OPPORTUNITY_SCORE = 0.50
DEFAULT_MIN_MODEL_QUALITY_SCORE = 0.50


@dataclass(frozen=True)
class AllocationConfig:
    """
    Configuration governing portfolio capital allocation.
    """

    max_positions: int = DEFAULT_MAX_POSITIONS
    max_position_weight: float = DEFAULT_MAX_POSITION_WEIGHT
    min_opportunity_score: float = DEFAULT_MIN_OPPORTUNITY_SCORE
    min_model_quality_score: float = DEFAULT_MIN_MODEL_QUALITY_SCORE

    def __post_init__(self) -> None:
        if self.max_positions <= 0:
            raise ValueError(
                "max_positions must be greater than zero."
            )

        if not 0.0 < self.max_position_weight <= 1.0:
            raise ValueError(
                "max_position_weight must be greater than 0 "
                "and less than or equal to 1."
            )

        if not 0.0 <= self.min_opportunity_score <= 1.0:
            raise ValueError(
                "min_opportunity_score must be between 0 and 1."
            )

        if not 0.0 <= self.min_model_quality_score <= 1.0:
            raise ValueError(
                "min_model_quality_score must be between 0 and 1."
            )


class PortfolioAllocator:
    """
    Convert ranked long opportunities into a capital allocation proposal.

    The allocator is intentionally stateless.

    The caller supplies:
        - current portfolio equity
        - currently available cash
        - existing open positions
        - ranked opportunities

    The allocator returns a proposal without changing persistent state.
    """

    def __init__(
        self,
        config: AllocationConfig | None = None,
    ) -> None:
        self.config = config or AllocationConfig()

    def allocate(
        self,
        ranking: list[dict[str, Any]],
        equity: float,
        cash: float,
        existing_positions: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """
        Build a portfolio allocation proposal.

        Parameters
        ----------
        ranking:
            Ranked candidate dictionaries produced by the ranking service.

        equity:
            Current total portfolio equity.

        cash:
            Currently available portfolio cash.

        existing_positions:
            Existing open paper positions. Existing tickers are excluded
            from new allocations.

        Returns
        -------
        dict[str, Any]
            Deterministic allocation proposal.
        """

        equity_value = self._validate_positive(
            equity,
            "equity",
        )

        cash_value = self._validate_non_negative(
            cash,
            "cash",
        )

        if cash_value > equity_value:
            raise ValueError(
                "cash cannot be greater than equity."
            )

        positions = existing_positions or []

        existing_tickers = {
            str(position.get("ticker", "")).upper().strip()
            for position in positions
            if str(position.get("ticker", "")).strip()
        }

        available_slots = max(
            0,
            self.config.max_positions
            - len(existing_tickers),
        )

        if available_slots == 0:
            return self._empty_result(
                equity=equity_value,
                cash=cash_value,
                existing_position_count=len(existing_tickers),
                reason="maximum_positions_reached",
            )

        candidates = self._filter_candidates(
            ranking=ranking,
            existing_tickers=existing_tickers,
        )

        candidates = candidates[:available_slots]

        if not candidates:
            return self._empty_result(
                equity=equity_value,
                cash=cash_value,
                existing_position_count=len(existing_tickers),
                reason="no_eligible_candidates",
            )

        max_position_capital = (
            equity_value
            * self.config.max_position_weight
        )

        allocations = self._calculate_allocations(
            candidates=candidates,
            available_cash=cash_value,
            max_position_capital=max_position_capital,
            equity=equity_value,
        )

        capital_allocated = sum(
            item["allocation"]
            for item in allocations
        )

        cash_remaining = max(
            0.0,
            cash_value - capital_allocated,
        )

        return {
            "equity": equity_value,
            "cash_available": cash_value,
            "capital_allocated": capital_allocated,
            "cash_remaining": cash_remaining,
            "existing_position_count": len(
                existing_tickers
            ),
            "new_position_count": len(
                allocations
            ),
            "max_positions": self.config.max_positions,
            "max_position_weight": (
                self.config.max_position_weight
            ),
            "positions": allocations,
            "config": {
                "max_positions": (
                    self.config.max_positions
                ),
                "max_position_weight": (
                    self.config.max_position_weight
                ),
                "min_opportunity_score": (
                    self.config.min_opportunity_score
                ),
                "min_model_quality_score": (
                    self.config.min_model_quality_score
                ),
            },
        }

    def _filter_candidates(
        self,
        ranking: list[dict[str, Any]],
        existing_tickers: set[str],
    ) -> list[dict[str, Any]]:
        """
        Filter ranked candidates without changing ranking order.
        """

        eligible: list[dict[str, Any]] = []
        seen: set[str] = set()

        for candidate in ranking:
            ticker = str(
                candidate.get("ticker", "")
            ).upper().strip()

            if not ticker:
                continue

            if ticker in existing_tickers:
                continue

            if ticker in seen:
                continue

            direction = str(
                candidate.get("direction", "")
            ).lower().strip()

            if direction != "long":
                continue

            latest_price = self._safe_float(
                candidate.get("latest_price")
            )

            opportunity_score = self._safe_float(
                candidate.get("opportunity_score")
            )

            model_quality_score = self._safe_float(
                candidate.get("model_quality_score")
            )

            predicted_return = self._safe_float(
                candidate.get("predicted_return")
            )

            if (
                latest_price is None
                or latest_price <= 0.0
            ):
                continue

            if opportunity_score is None:
                continue

            if model_quality_score is None:
                continue

            if predicted_return is None:
                continue

            if (
                opportunity_score
                < self.config.min_opportunity_score
            ):
                continue

            if (
                model_quality_score
                < self.config.min_model_quality_score
            ):
                continue

            if predicted_return <= 0.0:
                continue

            seen.add(ticker)
            eligible.append(candidate)

        return eligible

    def _calculate_allocations(
        self,
        candidates: list[dict[str, Any]],
        available_cash: float,
        max_position_capital: float,
        equity: float,
    ) -> list[dict[str, Any]]:
        """
        Allocate capital according to opportunity score.

        Each position is capped at max_position_capital.

        The allocator does not force capital deployment. If there are fewer
        qualifying opportunities than the portfolio can support, unused cash
        remains available.
        """

        if not candidates or available_cash <= 0.0:
            return []

        remaining_cash = available_cash
        remaining_candidates = list(candidates)
        allocations: list[dict[str, Any]] = []

        while (
            remaining_candidates
            and remaining_cash > 1e-12
        ):
            total_score = sum(
                max(
                    0.0,
                    self._safe_float(
                        candidate.get(
                            "opportunity_score"
                        )
                    ) or 0.0,
                )
                for candidate in remaining_candidates
            )

            if total_score <= 0.0:
                break

            round_allocations: list[
                tuple[dict[str, Any], float]
            ] = []

            capped_tickers: set[str] = set()

            for candidate in remaining_candidates:
                score = max(
                    0.0,
                    self._safe_float(
                        candidate.get(
                            "opportunity_score"
                        )
                    ) or 0.0,
                )

                proportional_allocation = (
                    remaining_cash
                    * score
                    / total_score
                )

                allocation = min(
                    proportional_allocation,
                    max_position_capital,
                    remaining_cash,
                )

                if allocation <= 0.0:
                    continue

                round_allocations.append(
                    (
                        candidate,
                        allocation,
                    )
                )

                if (
                    proportional_allocation
                    > max_position_capital
                ):
                    capped_tickers.add(
                        str(
                            candidate["ticker"]
                        ).upper().strip()
                    )

            if not round_allocations:
                break

            allocated_this_round = 0.0
            newly_allocated_tickers: set[str] = set()

            for candidate, allocation in round_allocations:
                latest_price = float(
                    candidate["latest_price"]
                )

                quantity = (
                    allocation
                    / latest_price
                )

                if quantity <= 0.0:
                    continue

                actual_allocation = (
                    quantity
                    * latest_price
                )

                if actual_allocation <= 0.0:
                    continue

                ticker = str(
                    candidate["ticker"]
                ).upper().strip()

                allocations.append(
                    self._build_position(
                        candidate=candidate,
                        allocation=actual_allocation,
                        quantity=quantity,
                        equity=equity,
                    )
                )

                allocated_this_round += actual_allocation
                newly_allocated_tickers.add(ticker)

            remaining_cash -= allocated_this_round

            if remaining_cash <= 1e-12:
                break

            if allocated_this_round <= 1e-12:
                break

            remaining_candidates = [
                candidate
                for candidate in remaining_candidates
                if str(
                    candidate["ticker"]
                ).upper().strip()
                not in newly_allocated_tickers
            ]

            if not remaining_candidates:
                break

        return allocations

    @staticmethod
    def _build_position(
        candidate: dict[str, Any],
        allocation: float,
        quantity: float,
        equity: float,
    ) -> dict[str, Any]:
        """
        Convert one ranked candidate into an allocation record.
        """

        latest_price = float(
            candidate["latest_price"]
        )

        portfolio_weight = (
            allocation / equity
        )

        return {
            "ticker": str(
                candidate["ticker"]
            ).upper().strip(),
            "side": "LONG",
            "quantity": float(quantity),
            "allocation": float(allocation),
            "weight": float(portfolio_weight),
            "entry_price": latest_price,
            "predicted_return": float(
                candidate["predicted_return"]
            ),
            "model_quality_score": float(
                candidate["model_quality_score"]
            ),
            "opportunity_score": float(
                candidate["opportunity_score"]
            ),
            "normalised_signal": float(
                candidate.get(
                    "normalised_signal",
                    0.0,
                )
            ),
            "signal": (
                f"predicted_return="
                f"{candidate['predicted_return']:+.8f};"
                f"opportunity="
                f"{candidate['opportunity_score']:.4f}"
            ),
        }

    @staticmethod
    def _empty_result(
        equity: float,
        cash: float,
        existing_position_count: int,
        reason: str,
    ) -> dict[str, Any]:
        """
        Return a consistent empty allocation proposal.
        """

        return {
            "equity": equity,
            "cash_available": cash,
            "capital_allocated": 0.0,
            "cash_remaining": cash,
            "existing_position_count": (
                existing_position_count
            ),
            "new_position_count": 0,
            "max_positions": DEFAULT_MAX_POSITIONS,
            "max_position_weight": (
                DEFAULT_MAX_POSITION_WEIGHT
            ),
            "positions": [],
            "reason": reason,
        }

    @staticmethod
    def _safe_float(
        value: Any,
    ) -> float | None:
        try:
            result = float(value)
        except (TypeError, ValueError):
            return None

        if not math.isfinite(result):
            return None

        return result

    @classmethod
    def _validate_positive(
        cls,
        value: Any,
        name: str,
    ) -> float:
        result = cls._safe_float(value)

        if result is None or result <= 0.0:
            raise ValueError(
                f"{name} must be greater than zero."
            )

        return result

    @classmethod
    def _validate_non_negative(
        cls,
        value: Any,
        name: str,
    ) -> float:
        result = cls._safe_float(value)

        if result is None or result < 0.0:
            raise ValueError(
                f"{name} must be greater than or equal to zero."
            )

        return result
