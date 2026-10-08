"""
chart_stream.py - Shared Alpaca WebSocket manager for live trading charts.

Maintains one upstream Alpaca WebSocket connection per market feed and
fans incoming bar messages out only to frontend clients subscribed to
the corresponding ticker.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any

import websockets
from fastapi import WebSocket, WebSocketDisconnect


logger = logging.getLogger(__name__)


STOCKS_URL = "wss://stream.data.alpaca.markets/v2/iex"
CRYPTO_URL = "wss://stream.data.alpaca.markets/v1beta3/crypto/us"

SUPPORTED_ASSET_CLASSES = {"stocks", "etf", "crypto"}


@dataclass
class ChartClient:
    """Frontend chart client registered with the shared stream."""

    websocket: WebSocket
    ticker: str


@dataclass
class ChartStream:
    """Shared upstream Alpaca stream for one market feed."""

    asset_class: str
    websocket: Any | None = None
    clients: dict[str, ChartClient] = field(default_factory=dict)
    task: asyncio.Task | None = None
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    subscriptions: set[str] = field(default_factory=set)


class ChartStreamManager:
    """
    Manage shared Alpaca WebSocket connections for frontend chart clients.

    A single Alpaca connection is maintained for each upstream feed:
        - stocks/ETF -> IEX
        - crypto -> crypto/us

    Multiple frontend clients can share the same upstream connection.
    Each frontend client receives only bars for its selected ticker.
    """

    def __init__(self) -> None:
        self._streams: dict[str, ChartStream] = {}
        self._running = False

    async def start(self) -> None:
        """Start the manager."""

        self._running = True
        logger.info("Chart stream manager started")

    async def stop(self) -> None:
        """Stop all upstream streams and clear registered clients."""

        self._running = False

        streams = list(self._streams.values())

        for stream in streams:
            await self._stop_stream(stream)

        self._streams.clear()

        logger.info("Chart stream manager stopped")

    async def connect(
        self,
        client_id: str,
        websocket: WebSocket,
        ticker: str,
        asset_class: str,
    ) -> None:
        """Register a frontend client with a shared market stream."""

        normalized_asset_class = self._normalize_asset_class(
            asset_class,
        )

        stream = self._streams.get(normalized_asset_class)

        if stream is None:
            stream = ChartStream(
                asset_class=normalized_asset_class,
            )
            self._streams[normalized_asset_class] = stream

        stream.clients[client_id] = ChartClient(
            websocket=websocket,
            ticker=ticker,
        )

        stream.subscriptions.add(ticker)

        if stream.task is None or stream.task.done():
            stream.task = asyncio.create_task(
                self._run_stream(stream),
            )

        elif stream.websocket is not None:
            await self._send_subscription(
                stream,
                ticker,
            )

        logger.info(
            "Chart client connected: client=%s ticker=%s asset=%s clients=%d",
            client_id,
            ticker,
            normalized_asset_class,
            len(stream.clients),
        )

    async def disconnect(
        self,
        client_id: str,
        asset_class: str,
    ) -> None:
        """Remove a frontend client from the shared stream."""

        normalized_asset_class = self._normalize_asset_class(
            asset_class,
        )

        stream = self._streams.get(normalized_asset_class)

        if stream is None:
            return

        client = stream.clients.pop(client_id, None)

        if client is None:
            return

        ticker = client.ticker

        if not any(
            remaining.ticker == ticker
            for remaining in stream.clients.values()
        ):
            stream.subscriptions.discard(ticker)

        if stream.clients:
            logger.info(
                "Chart client disconnected: client=%s ticker=%s asset=%s clients=%d",
                client_id,
                ticker,
                normalized_asset_class,
                len(stream.clients),
            )
            return

        logger.info(
            "No chart clients remain: asset=%s",
            normalized_asset_class,
        )

        await self._stop_stream(stream)
        self._streams.pop(normalized_asset_class, None)

    async def _run_stream(
        self,
        stream: ChartStream,
    ) -> None:
        """Maintain one upstream Alpaca connection for the shared stream."""

        url = self._url_for(stream.asset_class)

        while self._running and stream.clients:
            try:
                async with websockets.connect(
                    url,
                    ping_interval=20,
                    ping_timeout=20,
                ) as alpaca_ws:
                    stream.websocket = alpaca_ws

                    await self._authenticate(alpaca_ws)

                    tickers = sorted(stream.subscriptions)

                    if tickers:
                        await self._send_subscription_message(
                            alpaca_ws,
                            tickers,
                        )

                    logger.info(
                        "Alpaca chart stream connected: asset=%s subscriptions=%s",
                        stream.asset_class,
                        tickers,
                    )

                    async for message in alpaca_ws:
                        if not self._running:
                            break

                        await self._broadcast(
                            stream,
                            message,
                        )

            except asyncio.CancelledError:
                raise

            except Exception:
                if self._running and stream.clients:
                    logger.exception(
                        "Alpaca chart stream error: asset=%s",
                        stream.asset_class,
                    )

                    await asyncio.sleep(2)

            finally:
                stream.websocket = None

        logger.info(
            "Alpaca chart stream stopped: asset=%s",
            stream.asset_class,
        )

    async def _authenticate(
        self,
        websocket: Any,
    ) -> None:
        """Authenticate the Alpaca upstream connection."""

        key = os.getenv("ALPACA_API_KEY")
        secret = os.getenv("ALPACA_API_SECRET")

        if not key or not secret:
            raise RuntimeError(
                "ALPACA_API_KEY and ALPACA_API_SECRET must be configured",
            )

        await websocket.send(
            json.dumps(
                {
                    "action": "auth",
                    "key": key,
                    "secret": secret,
                },
            ),
        )

        while True:
            response = await websocket.recv()

            logger.info(
                "Alpaca chart auth response: %s",
                response,
            )

            messages = json.loads(response)

            if not isinstance(messages, list):
                continue

            for message in messages:
                if not isinstance(message, dict):
                    continue

                if (
                    message.get("T") == "success"
                    and message.get("msg") == "authenticated"
                ):
                    logger.info("Alpaca chart authenticated successfully")
                    return

                if message.get("T") == "error":
                    raise RuntimeError(
                        f"Alpaca chart authentication failed: {messages}",
                    )

    async def _send_subscription(
        self,
        stream: ChartStream,
        ticker: str,
    ) -> None:
        """Subscribe the existing upstream connection to one ticker."""

        if stream.websocket is None:
            return

        async with stream.send_lock:
            await self._send_subscription_message(
                stream.websocket,
                [ticker],
            )

    async def _send_subscription_message(
        self,
        websocket: Any,
        tickers: list[str],
    ) -> None:
        """Send an Alpaca bar subscription without reading its response."""

        await websocket.send(
            json.dumps(
                {
                    "action": "subscribe",
                    "bars": tickers,
                },
            ),
        )

        logger.info(
            "Alpaca chart subscription requested: tickers=%s",
            tickers,
        )

    async def _broadcast(
        self,
        stream: ChartStream,
        message: str,
    ) -> None:
        """Forward each Alpaca bar only to matching frontend clients."""

        try:
            messages = json.loads(message)
        except json.JSONDecodeError:
            logger.warning(
                "Ignoring invalid Alpaca chart message: %s",
                message[:200],
            )
            return

        if not isinstance(messages, list):
            return

        for item in messages:
            if not isinstance(item, dict):
                continue

            if item.get("T") != "b":
                continue

            ticker = item.get("S")

            if not ticker:
                continue

            stale_clients: list[str] = []

            for client_id, client in list(stream.clients.items()):
                if client.ticker != ticker:
                    continue

                try:
                    await client.websocket.send_text(
                        json.dumps([item]),
                    )

                except (
                    WebSocketDisconnect,
                    RuntimeError,
                ):
                    stale_clients.append(client_id)

                except Exception:
                    logger.exception(
                        "Failed to send chart update: "
                        "client=%s ticker=%s",
                        client_id,
                        ticker,
                    )
                    stale_clients.append(client_id)

            for client_id in stale_clients:
                stream.clients.pop(client_id, None)

    async def _stop_stream(
        self,
        stream: ChartStream,
    ) -> None:
        """Stop one shared upstream stream."""

        task = stream.task
        stream.task = None

        if task is not None and task is not asyncio.current_task():
            task.cancel()

            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.exception(
                    "Chart stream task failed during shutdown: asset=%s",
                    stream.asset_class,
                )

        stream.websocket = None
        stream.subscriptions.clear()

    @staticmethod
    def _auth_succeeded(messages: Any) -> bool:
        """Return whether Alpaca authentication succeeded."""

        if not isinstance(messages, list):
            return False

        return any(
            isinstance(message, dict)
            and message.get("T") == "success"
            and message.get("msg") == "authenticated"
            for message in messages
        )

    @staticmethod
    def _normalize_asset_class(
        asset_class: str,
    ) -> str:
        """Validate and normalize an asset class."""

        normalized = asset_class.lower().strip()

        if normalized not in SUPPORTED_ASSET_CLASSES:
            raise ValueError(
                f"Unsupported asset class: {asset_class}",
            )

        return normalized

    @staticmethod
    def _url_for(
        asset_class: str,
    ) -> str:
        """Return the Alpaca stream URL for an asset class."""

        if asset_class == "crypto":
            return CRYPTO_URL

        return STOCKS_URL
