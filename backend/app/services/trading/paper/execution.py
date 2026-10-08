"""
execution.py - Paper-trading orchestration for Zebio.

Coordinates:

    ModelRankingService
            |
            v
    PortfolioAllocator
            |
            v
      PaperRepository

Responsibilities:
    - read the current paper portfolio state
    - obtain the current model ranking
    - build a deterministic allocation proposal
    - persist approved allocation positions
    - report successful and failed position openings

This service does not:
    - train models
    - perform inference directly
    - access market-data providers directly
    - calculate portfolio allocation rules
    - implement portfolio accounting
    - expose HTTP endpoints
    - run a background trading loop

Those responsibilities remain in their dedicated services.
"""

from __future__ import annotations

from typing import Any

from app.services.trading.ml.ranking import ModelRankingService
from app.services.trading.paper.allocator import PortfolioAllocator
from app.services.trading.paper.repository import PaperRepository


class PaperExecutionService:
    """
    Orchestrate model ranking, portfolio allocation, and paper execution.

    The service deliberately keeps ranking, allocation, and persistence
    separate. This allows allocation proposals to be inspected and tested
    before any paper-trading state is modified.
    """

    def __init__(
        self,
        ranking_service: ModelRankingService,
        allocator: PortfolioAllocator,
        repository: PaperRepository,
        portfolio_name: str = "default",
    ) -> None:
        normalized_name = portfolio_name.strip()

        if not normalized_name:
            raise ValueError(
                "portfolio_name must not be empty."
            )

        self.ranking_service = ranking_service
        self.allocator = allocator
        self.repository = repository
        self.portfolio_name = normalized_name

    def build_allocation(
        self,
        top_n: int = 10,
        asset_class: str = "stocks",
    ) -> dict[str, Any]:
        """
        Build an allocation proposal without modifying paper state.

        The portfolio is read immediately before ranking/allocation so the
        proposal reflects the current cash, equity, and open positions.
        """

        portfolio = self._get_portfolio()

        portfolio_id = int(
            portfolio["id"]
        )

        existing_positions = (
            self.repository.open_positions(
                portfolio_id
            )
        )

        ranking_result = self.ranking_service.rank(
            top_n=top_n,
            asset_class=asset_class,
        )

        ranking = ranking_result.get(
            "ranking",
            [],
        )

        if not isinstance(ranking, list):
            raise ValueError(
                "Ranking service returned an invalid ranking payload."
            )

        allocation = self.allocator.allocate(
            ranking=ranking,
            equity=float(
                portfolio["equity"]
            ),
            cash=float(
                portfolio["cash"]
            ),
            existing_positions=existing_positions,
        )

        return {
            "portfolio": {
                "id": portfolio_id,
                "name": portfolio["name"],
                "currency": portfolio["currency"],
                "initial_capital": float(
                    portfolio["initial_capital"]
                ),
                "cash": float(
                    portfolio["cash"]
                ),
                "equity": float(
                    portfolio["equity"]
                ),
            },
            "ranking": ranking_result,
            "allocation": allocation,
        }

    def execute_allocation(
        self,
        allocation_result: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Persist an allocation proposal as paper positions.

        The supplied allocation is treated as a proposal. Each position is
        opened through PaperRepository.open_position(), which performs its
        own duplicate-position, cash, and transaction-integrity checks.

        A failure opening one position does not erase positions that were
        already opened successfully. The result explicitly reports both
        successful and failed executions.
        """

        if not isinstance(
            allocation_result,
            dict,
        ):
            raise ValueError(
                "allocation_result must be a dictionary."
            )

        portfolio_data = allocation_result.get(
            "portfolio"
        )

        allocation = allocation_result.get(
            "allocation"
        )

        if not isinstance(
            portfolio_data,
            dict,
        ):
            raise ValueError(
                "allocation_result is missing portfolio data."
            )

        if not isinstance(
            allocation,
            dict,
        ):
            raise ValueError(
                "allocation_result is missing allocation data."
            )

        portfolio_id = portfolio_data.get(
            "id"
        )

        if portfolio_id is None:
            raise ValueError(
                "allocation_result is missing portfolio id."
            )

        positions = allocation.get(
            "positions",
            [],
        )

        if not isinstance(
            positions,
            list,
        ):
            raise ValueError(
                "allocation positions must be a list."
            )

        executed: list[dict[str, Any]] = []
        failed: list[dict[str, Any]] = []

        for position in positions:
            if not isinstance(
                position,
                dict,
            ):
                failed.append(
                    {
                        "position": position,
                        "error": (
                            "Allocation position "
                            "must be a dictionary."
                        ),
                    }
                )
                continue

            ticker = str(
                position.get(
                    "ticker",
                    ""
                )
            ).upper().strip()

            try:
                result = self.repository.open_position(
                    portfolio_id=int(
                        portfolio_id
                    ),
                    ticker=ticker,
                    quantity=float(
                        position["quantity"]
                    ),
                    entry_price=float(
                        position["entry_price"]
                    ),
                    predicted_return=(
                        float(
                            position["predicted_return"]
                        )
                        if position.get(
                            "predicted_return"
                        ) is not None
                        else None
                    ),
                    signal=position.get(
                        "signal"
                    ),
                )

                executed.append(result)

            except (
                KeyError,
                TypeError,
                ValueError,
            ) as exc:
                failed.append(
                    {
                        "ticker": ticker,
                        "error": str(exc),
                    }
                )

        refreshed_portfolio = (
            self.repository.get_portfolio(
                self.portfolio_name
            )
        )

        if refreshed_portfolio is None:
            raise RuntimeError(
                "Paper portfolio disappeared during execution."
            )

        return {
            "portfolio": {
                "id": int(
                    refreshed_portfolio["id"]
                ),
                "name": refreshed_portfolio["name"],
                "currency": refreshed_portfolio["currency"],
                "initial_capital": float(
                    refreshed_portfolio[
                        "initial_capital"
                    ]
                ),
                "cash": float(
                    refreshed_portfolio["cash"]
                ),
                "equity": float(
                    refreshed_portfolio["equity"]
                ),
            },
            "proposed_position_count": len(
                positions
            ),
            "executed_position_count": len(
                executed
            ),
            "failed_position_count": len(
                failed
            ),
            "executed": executed,
            "failed": failed,
        }

    def run(
        self,
        top_n: int = 10,
        asset_class: str = "stocks",
    ) -> dict[str, Any]:
        """
        Build and execute the current paper-trading allocation.
        """

        allocation_result = self.build_allocation(
            top_n=top_n,
            asset_class=asset_class,
        )

        execution_result = self.execute_allocation(
            allocation_result
        )

        return {
            "allocation": allocation_result,
            "execution": execution_result,
        }

    def _get_portfolio(self) -> dict[str, Any]:
        """
        Resolve the configured paper portfolio.
        """

        portfolio = self.repository.get_portfolio(
            self.portfolio_name
        )

        if portfolio is None:
            raise ValueError(
                f"Paper portfolio "
                f"'{self.portfolio_name}' "
                f"not found."
            )

        return portfolio
