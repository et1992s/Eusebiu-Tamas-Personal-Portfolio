"""
chart.py - Live market-chart data aggregation for Zebio.

This module sits between the canonical live market-data provider and
the frontend charting layer.

Architecture:

    AlpacaMarketDataProvider
            |
            | canonical 1-minute OHLCV
            v
    LiveChartService
            |
            | regular-session filtering
            | session-anchored aggregation
            v
    aggregated OHLCV

The chart timeframe is deliberately independent from the ML inference
timeframe. The production ML model remains fixed at 1-minute resolution.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.services.trading.live.provider import MarketDataProvider


@dataclass(frozen=True)
class ChartTimeframe:
    """
    Definition of a supported chart timeframe.
    """

    code: str
    pandas_rule: str
    source_bars_per_candle: int


TIMEFRAMES: dict[str, ChartTimeframe] = {
    "1m": ChartTimeframe(
        code="1m",
        pandas_rule="1min",
        source_bars_per_candle=1,
    ),
    "5m": ChartTimeframe(
        code="5m",
        pandas_rule="5min",
        source_bars_per_candle=5,
    ),
    "15m": ChartTimeframe(
        code="15m",
        pandas_rule="15min",
        source_bars_per_candle=15,
    ),
    "30m": ChartTimeframe(
        code="30m",
        pandas_rule="30min",
        source_bars_per_candle=30,
    ),
    "1h": ChartTimeframe(
        code="1h",
        pandas_rule="1h",
        source_bars_per_candle=60,
    ),
    "4h": ChartTimeframe(
        code="4h",
        pandas_rule="4h",
        source_bars_per_candle=240,
    ),
    "1D": ChartTimeframe(
        code="1D",
        pandas_rule="1D",
        source_bars_per_candle=390,
    ),
}


CANONICAL_COLUMNS = [
    "first",
    "high",
    "low",
    "last",
    "volume",
]


class LiveChartService:
    """
    Transform canonical live 1-minute OHLCV data into chart candles.

    The service does not:

        - perform ML inference;
        - modify feature engineering;
        - modify the historical TradingEngine;
        - create synthetic OHLCV observations;
        - mix live data into historical datasets.

    The provider remains responsible for obtaining raw market data.

    This service is responsible for:

        - validating provider data;
        - restricting equity charts to regular US market hours;
        - anchoring candles to the regular-session open;
        - aggregating 1-minute observations into display candles.
    """

    MARKET_TIMEZONE = "America/New_York"

    REGULAR_SESSION_START = "09:30"
    REGULAR_SESSION_END = "16:00"

    # The provider currently uses Alpaca's `limit` parameter. A bounded
    # source request prevents accidental requests of unreasonable size.
    MAX_SOURCE_BARS = 10_000

    def __init__(
        self,
        provider: MarketDataProvider,
        default_limit: int = 100,
    ) -> None:
        if default_limit <= 0:
            raise ValueError(
                "default_limit must be greater than zero."
            )

        self.provider = provider
        self.default_limit = default_limit

    @staticmethod
    def normalize_timeframe(
        timeframe: str,
    ) -> str:
        """
        Validate and normalize a public chart timeframe.

        Examples:

            "5m"  -> "5m"
            "15M" -> "15m"
            "1d"  -> "1D"
        """

        if not isinstance(timeframe, str):
            raise ValueError(
                "Timeframe must be a string."
            )

        normalized = timeframe.strip()

        if not normalized:
            raise ValueError(
                "Timeframe must not be empty."
            )

        aliases = {
            "1m": "1m",
            "5m": "5m",
            "15m": "15m",
            "30m": "30m",
            "1h": "1h",
            "4h": "4h",
            "1d": "1D",
        }

        normalized = aliases.get(
            normalized.lower(),
            normalized,
        )

        if normalized not in TIMEFRAMES:
            supported = ", ".join(TIMEFRAMES)

            raise ValueError(
                f"Unsupported timeframe '{timeframe}'. "
                f"Supported timeframes: {supported}."
            )

        return normalized

    @staticmethod
    def _empty_bars() -> pd.DataFrame:
        """
        Return an empty canonical OHLCV DataFrame.
        """

        return pd.DataFrame(
            columns=CANONICAL_COLUMNS,
            index=pd.DatetimeIndex(
                [],
                name="timestamp",
            ),
        )

    @staticmethod
    def _validate_bars(
        bars: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Validate and normalize provider output.

        The provider contract requires a DatetimeIndex and the canonical
        OHLCV columns.
        """

        if bars is None:
            return LiveChartService._empty_bars()

        if not isinstance(bars, pd.DataFrame):
            raise TypeError(
                "Market-data provider must return a pandas DataFrame."
            )

        missing = [
            column
            for column in CANONICAL_COLUMNS
            if column not in bars.columns
        ]

        if missing:
            raise ValueError(
                "Market-data provider returned an invalid schema. "
                f"Missing columns: {missing}."
            )

        if not isinstance(
            bars.index,
            pd.DatetimeIndex,
        ):
            raise ValueError(
                "Market-data provider must return a DatetimeIndex."
            )

        if bars.empty:
            return LiveChartService._empty_bars()

        normalized = bars[
            CANONICAL_COLUMNS
        ].copy()

        normalized.index = pd.to_datetime(
            normalized.index,
            utc=True,
        )

        normalized.index.name = "timestamp"

        normalized = normalized.sort_index()

        normalized = normalized[
            ~normalized.index.duplicated(
                keep="last",
            )
        ]

        return normalized

    @classmethod
    def _source_limit(
        cls,
        timeframe: ChartTimeframe,
        requested_candles: int,
    ) -> int:
        """
        Calculate a bounded source-bar request.

        The provider returns raw 1-minute bars, so higher chart
        timeframes require more source observations.

        Extra observations are requested because Alpaca may return
        extended-hours observations and because source data can contain
        missing minutes.

        The result is bounded by MAX_SOURCE_BARS because the current
        provider contract uses a single bounded `limit` request.
        """

        if requested_candles <= 0:
            raise ValueError(
                "limit must be greater than zero."
            )

        bars_per_candle = (
            timeframe.source_bars_per_candle
        )

        # At least two additional candle widths are requested.
        # For 1-minute charts this also deliberately overfetches so
        # that pre-market observations can be removed without reducing
        # the requested regular-session chart history.
        buffer = max(
            bars_per_candle * 2,
            30,
        )

        required = (
            requested_candles
            * bars_per_candle
        ) + buffer

        return min(
            required,
            cls.MAX_SOURCE_BARS,
        )

    @classmethod
    def _filter_regular_session(
        cls,
        bars: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Keep only regular US equity-session observations.

        Provider timestamps are UTC. They are converted to
        America/New_York solely for session filtering so daylight
        saving time is handled correctly.

        Regular session:

            09:30 <= timestamp < 16:00

        The returned index remains UTC.
        """

        if bars.empty:
            return bars

        local_index = bars.index.tz_convert(
            cls.MARKET_TIMEZONE,
        )

        session_start = pd.to_datetime(
            cls.REGULAR_SESSION_START,
        ).time()

        session_end = pd.to_datetime(
            cls.REGULAR_SESSION_END,
        ).time()

        local_times = local_index.time

        mask = (
            (local_times >= session_start)
            & (local_times < session_end)
        )

        return bars.loc[mask].copy()

    @classmethod
    def _session_key(
        cls,
        index: pd.DatetimeIndex,
    ) -> pd.Series:
        """
        Return a regular-market-session key for each timestamp.

        Sessions are identified using the local New York calendar date,
        rather than UTC date. This is important around daylight-saving
        transitions and makes the session boundary explicit.
        """

        local_index = index.tz_convert(
            cls.MARKET_TIMEZONE,
        )

        session_dates = local_index.date

        return pd.Series(
            session_dates,
            index=index,
            dtype="object",
        )

    @classmethod
    def _session_open(
        cls,
        session_bars: pd.DataFrame,
    ) -> pd.Timestamp:
        """
        Return the UTC timestamp corresponding to 09:30 New York time
        for the session represented by `session_bars`.
        """

        if session_bars.empty:
            raise ValueError(
                "Cannot determine session open from empty data."
            )

        first_timestamp = session_bars.index[0]

        local_first = first_timestamp.tz_convert(
            cls.MARKET_TIMEZONE,
        )

        session_date = local_first.date()

        local_open = pd.Timestamp(
            year=session_date.year,
            month=session_date.month,
            day=session_date.day,
            hour=9,
            minute=30,
            tz=cls.MARKET_TIMEZONE,
        )

        return local_open.tz_convert("UTC")

    @classmethod
    def _aggregate_session(
        cls,
        session_bars: pd.DataFrame,
        timeframe: ChartTimeframe,
    ) -> pd.DataFrame:
        """
        Aggregate one regular market session.

        Candle boundaries are anchored to 09:30 America/New_York.

        Examples:

            5m:
                09:30, 09:35, 09:40, ...

            1h:
                09:30, 10:30, 11:30, ...

            4h:
                09:30, 13:30, ...

        The final candle may be shorter than the nominal timeframe
        because the regular session closes at 16:00.

        Only actual source observations contribute to a candle.
        """

        if session_bars.empty:
            return cls._empty_bars()

        if timeframe.code == "1m":
            return session_bars[
                CANONICAL_COLUMNS
            ].copy()

        session_open = cls._session_open(
            session_bars,
        )

        if timeframe.code == "1D":
            first_row = session_bars.iloc[0]

            return pd.DataFrame(
                {
                    "first": [
                        float(first_row["first"])
                    ],
                    "high": [
                        session_bars["high"].max()
                    ],
                    "low": [
                        session_bars["low"].min()
                    ],
                    "last": [
                        float(
                            session_bars.iloc[-1]["last"]
                        )
                    ],
                    "volume": [
                        session_bars["volume"].sum()
                    ],
                },
                index=pd.DatetimeIndex(
                    [session_open],
                    name="timestamp",
                ),
            )

        aggregated = (
            session_bars[
                CANONICAL_COLUMNS
            ]
            .resample(
                timeframe.pandas_rule,
                origin=session_open,
                label="left",
                closed="left",
            )
            .agg(
                {
                    "first": "first",
                    "high": "max",
                    "low": "min",
                    "last": "last",
                    "volume": "sum",
                }
            )
        )

        aggregated = aggregated.dropna(
            subset=[
                "first",
                "high",
                "low",
                "last",
            ],
            how="all",
        )

        aggregated.index.name = "timestamp"

        return aggregated

    def _aggregate(
        self,
        bars: pd.DataFrame,
        timeframe: ChartTimeframe,
    ) -> pd.DataFrame:
        """
        Aggregate regular-session bars without crossing sessions.
        """

        if bars.empty:
            return self._empty_bars()

        if timeframe.code == "1m":
            return bars[
                CANONICAL_COLUMNS
            ].copy()

        session_keys = self._session_key(
            bars.index,
        )

        groups: list[pd.DataFrame] = []

        for _, session_bars in bars.groupby(
            session_keys,
            sort=True,
        ):
            aggregated_session = (
                self._aggregate_session(
                    session_bars,
                    timeframe,
                )
            )

            if not aggregated_session.empty:
                groups.append(
                    aggregated_session
                )

        if not groups:
            return self._empty_bars()

        aggregated = pd.concat(
            groups,
            axis=0,
        )

        aggregated = aggregated.sort_index()

        aggregated = aggregated[
            CANONICAL_COLUMNS
        ]

        aggregated.index = pd.to_datetime(
            aggregated.index,
            utc=True,
        )

        aggregated.index.name = "timestamp"

        return aggregated

    def get_bars(
        self,
        ticker: str,
        timeframe: str = "1m",
        limit: int | None = None,
        asset_class: str = "stocks",   # <-- MUST accept this
    ) -> pd.DataFrame:
        """
        Return live chart bars for a ticker and display timeframe.

        The provider always supplies 1-minute source bars.

        Higher chart timeframes are derived locally.

        The chart layer represents regular US equity market hours
        only.

        Note:
            The current provider contract uses one bounded historical
            request. Very long daily lookbacks may therefore return
            fewer candles than requested until the provider supports
            paginated/date-range retrieval.
        """

        normalized_ticker = ticker.upper().strip()

        if not normalized_ticker:
            raise ValueError(
                "Ticker must not be empty."
            )

        normalized_timeframe = (
            self.normalize_timeframe(
                timeframe,
            )
        )

        requested_limit = (
            self.default_limit
            if limit is None
            else limit
        )

        if requested_limit <= 0:
            raise ValueError(
                "limit must be greater than zero."
            )

        chart_timeframe = TIMEFRAMES[
            normalized_timeframe
        ]

        source_limit = self._source_limit(
            chart_timeframe,
            requested_limit,
        )

        source_bars = self.provider.get_recent_bars(
            normalized_ticker,
            limit=source_limit,
        )

        source_bars = self._validate_bars(source_bars)
        if source_bars.empty:
            return source_bars

        # BYPASS regular session filtering for crypto
        if asset_class != "crypto":
            source_bars = self._filter_regular_session(source_bars)
            if source_bars.empty:
                return source_bars

        chart_bars = self._aggregate(source_bars, chart_timeframe)

        if chart_bars.empty:
            return chart_bars
        return chart_bars

    @staticmethod
    def supported_timeframes() -> list[str]:
        """
        Return supported public timeframe identifiers in UI order.
        """

        return list(TIMEFRAMES.keys())
