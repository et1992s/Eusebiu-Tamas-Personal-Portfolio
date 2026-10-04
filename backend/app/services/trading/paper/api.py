"""
api.py - Read-only paper-trading API endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.services.trading.paper.bootstrap import PORTFOLIO_NAME
from app.services.trading.paper.repository import PaperRepository

router = APIRouter(prefix="/api/v1/paper", tags=["Paper Trading"])


def _resolve_portfolio(repo: PaperRepository, name: str) -> dict:
    portfolio = repo.get_portfolio(name)
    if not portfolio:
        raise HTTPException(
            status_code=404,
            detail=f"Paper portfolio '{name}' not found.",
        )
    return portfolio


def _summarise(portfolio: dict) -> dict:
    """
    Derive summary metrics from the stored portfolio record.
    Trades and positions are added by the caller when relevant.
    """
    initial = float(portfolio["initial_capital"])
    equity = float(portfolio["equity"])
    cash = float(portfolio["cash"])

    cumulative_pnl = equity - initial
    cumulative_pnl_pct = (cumulative_pnl / initial) if initial else 0.0

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
    repo = PaperRepository()
    portfolio = _resolve_portfolio(repo, name)

    summary = _summarise(portfolio)
    summary["open_positions"] = repo.open_positions(portfolio["id"])
    summary["trade_count"] = repo.trade_count(portfolio["id"])

    return {"status": "success", "portfolio": summary}


@router.get("/equity")
async def get_equity_curve(
    name: str = Query(PORTFOLIO_NAME),
    limit: int = Query(500, ge=1, le=2000),
):
    """Return the daily equity curve for the portfolio."""
    repo = PaperRepository()
    portfolio = _resolve_portfolio(repo, name)

    return {
        "status": "success",
        "currency": portfolio["currency"],
        "initial_capital": float(portfolio["initial_capital"]),
        "points": repo.equity_curve(portfolio["id"], limit=limit),
    }


@router.get("/trades")
async def get_trades(
    name: str = Query(PORTFOLIO_NAME),
    limit: int = Query(200, ge=1, le=2000),
):
    """Return the trade journal (most recent first)."""
    repo = PaperRepository()
    portfolio = _resolve_portfolio(repo, name)

    trades = repo.recent_trades(portfolio["id"], limit=limit)

    return {
        "status": "success",
        "currency": portfolio["currency"],
        "count": len(trades),
        "trades": trades,
    }