"""
bootstrap.py - Ensure the paper-trading portfolio exists on startup.

Idempotent: safe to call on every application start.
"""

from __future__ import annotations

import logging

from app.services.trading.paper.repository import PaperRepository

logger = logging.getLogger(__name__)

PORTFOLIO_NAME = "default"
STARTING_CAPITAL = 100_000.0
STARTING_CURRENCY = "GBP"
STARTING_DATE = "2026-10-02"  # last completed session (Friday)


def ensure_portfolio() -> dict:
    repo = PaperRepository()
    existing = repo.get_portfolio(PORTFOLIO_NAME)

    if existing:
        logger.info(
            "Paper portfolio '%s' present: equity=%.2f %s, cash=%.2f",
            PORTFOLIO_NAME,
            existing["equity"],
            existing["currency"],
            existing["cash"],
        )
        return existing

    repo.create_portfolio(
        name=PORTFOLIO_NAME,
        initial_capital=STARTING_CAPITAL,
        currency=STARTING_CURRENCY,
        starting_date=STARTING_DATE,
    )

    created = repo.get_portfolio(PORTFOLIO_NAME)
    logger.info(
        "Paper portfolio '%s' initialised: %.2f %s from %s",
        PORTFOLIO_NAME,
        STARTING_CAPITAL,
        STARTING_CURRENCY,
        STARTING_DATE,
    )
    return created