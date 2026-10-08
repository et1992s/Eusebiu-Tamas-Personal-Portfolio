"""
api.py - Read-only paper-trading API endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.services.trading.paper.bootstrap import PORTFOLIO_NAME
from app.services.trading.paper.repository import PaperRepository
from app.services.trading.paper.valuation import PaperValuationService


def create_router(
    repository: PaperRepository,
    valuation_service: PaperValuationService,
) -> APIRouter:
    """
    Create the read-only paper-trading API router.

    The application owns the repository and valuation service.
    This factory injects those shared services into the endpoints
    rather than creating separate instances per request.
    """

    router = APIRouter(
        prefix="/api/v1/paper",
        tags=["Paper Trading"],
    )

    def resolve_portfolio(name: str) -> dict:
        portfolio = repository.get_portfolio(name)

        if not portfolio:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Paper portfolio '{name}' not found."
                ),
            )

        return portfolio

    def summarise(portfolio: dict) -> dict:
        """
        Derive summary metrics from the stored portfolio record.
        """
        initial = float(
            portfolio["initial_capital"]
        )
        equity = float(
            portfolio["equity"]
        )
        cash = float(
            portfolio["cash"]
        )

        cumulative_pnl = equity - initial
        cumulative_pnl_pct = (
            cumulative_pnl / initial
            if initial
            else 0.0
        )

        return {
            "name": portfolio["name"],
            "currency": portfolio["currency"],
            "initial_capital": initial,
            "cash": cash,
            "equity": equity,
            "starting_date": portfolio["starting_date"],
            "created_at": portfolio["created_at"],
            "updated_at": portfolio["updated_at"],
            "cumulative_pnl": cumulative_pnl,
            "cumulative_pnl_pct": cumulative_pnl_pct,
        }

    @router.get("/portfolio")
    async def get_portfolio(
        name: str = Query(PORTFOLIO_NAME),
    ):
        """Return the persisted portfolio summary."""
        portfolio = resolve_portfolio(name)

        summary = summarise(portfolio)

        summary["open_positions"] = (
            repository.open_positions(
                portfolio["id"]
            )
        )

        summary["trade_count"] = (
            repository.trade_count(
                portfolio["id"]
            )
        )

        return {
            "status": "success",
            "portfolio": summary,
        }

    @router.get("/equity")
    async def get_equity_curve(
        name: str = Query(PORTFOLIO_NAME),
        limit: int = Query(
            500,
            ge=1,
            le=2000,
        ),
    ):
        """Return the daily equity curve for the portfolio."""
        portfolio = resolve_portfolio(name)

        return {
            "status": "success",
            "currency": portfolio["currency"],
            "initial_capital": float(
                portfolio["initial_capital"]
            ),
            "points": repository.equity_curve(
                portfolio["id"],
                limit=limit,
            ),
        }

    @router.get("/trades")
    async def get_trades(
        name: str = Query(PORTFOLIO_NAME),
        limit: int = Query(
            200,
            ge=1,
            le=2000,
        ),
    ):
        """Return the trade journal, most recent first."""
        portfolio = resolve_portfolio(name)

        trades = repository.recent_trades(
            portfolio["id"],
            limit=limit,
        )

        return {
            "status": "success",
            "currency": portfolio["currency"],
            "count": len(trades),
            "trades": trades,
        }

    @router.get("/valuation")
    async def get_portfolio_valuation(
        name: str = Query(PORTFOLIO_NAME),
        asset_class: str = Query("stocks"),
        bars_limit: int = Query(
            1,
            ge=1,
            le=100,
        ),
    ):
        """
        Return the current read-only mark-to-market valuation.

        The valuation uses the latest available market price for
        each open position.

        During market closure, MarketDataService may return the
        latest persisted market-data session instead of a fresh
        live price.
        """
        try:
            valuation = valuation_service.value_portfolio(
                portfolio_name=name,
                asset_class=asset_class,
                bars_limit=bars_limit,
            )

            return {
                "status": "success",
                "valuation": valuation,
            }

        except ValueError as exc:
            raise HTTPException(
                status_code=404,
                detail=str(exc),
            ) from exc

        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail=(
                    "Paper portfolio valuation failed: "
                    f"{exc}"
                ),
            ) from exc

    return router
