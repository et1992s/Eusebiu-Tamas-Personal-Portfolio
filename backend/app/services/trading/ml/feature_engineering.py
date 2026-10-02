"""
Authoritative, session-aware feature engineering for Zebio Trading ML.

Contract
--------
For each valid bar t:

    X[t-29:t] -> forward_1min_return[t]

Every feature at t uses only information available at or before t.
Targets describe the next 1-minute bar.

This module intentionally contains no:
- model training
- scaling
- strategy thresholds
- backtesting
- genetic optimisation
- plotting / EDA
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd


SEQ_LENGTH = 30

FEATURES: List[str] = [
    "return_1",
    "return_5",
    "return_15",
    "range_pct",
    "body_pct",
    "close_location",
    "volatility_10",
    "volatility_30",
    "volume_ratio_20",
    "distance_ema_5",
    "distance_ema_20",
    "rsi_14",
    "macd",
    "macd_signal",
    "macd_hist",
]

TARGET = "forward_1min_return"

OHLCV_COLUMNS = ["first", "high", "low", "last", "volume"]


@dataclass(frozen=True)
class FeatureResult:
    """Feature-engineering result for one ticker."""

    data: pd.DataFrame
    features: Tuple[str, ...] = tuple(FEATURES)
    target: str = TARGET
    sequence_length: int = SEQ_LENGTH


def _session_id(index: pd.DatetimeIndex) -> np.ndarray:
    """
    Generate a stable session identifier from the calendar date.

    The source dataset has already been validated as chronological with
    complete 391-bar sessions. Using the raw nanosecond representation
    avoids problematic DatetimeIndex rendering behaviour observed in the
    local environment.
    """
    return index.asi8 // 86_400_000_000_000


def _group_ewm(
    series: pd.Series,
    session: pd.Series,
    span: int,
) -> pd.Series:
    """Calculate an EMA independently inside each trading session."""
    return series.groupby(session, sort=False).transform(
        lambda s: s.ewm(span=span, adjust=False).mean()
    )


def _group_rolling_std(
    series: pd.Series,
    session: pd.Series,
    window: int,
) -> pd.Series:
    """Calculate rolling standard deviation independently per session."""
    return series.groupby(session, sort=False).transform(
        lambda s: s.rolling(window=window, min_periods=window).std()
    )


def _group_rolling_mean(
    series: pd.Series,
    session: pd.Series,
    window: int,
) -> pd.Series:
    """Calculate rolling mean independently per session."""
    return series.groupby(session, sort=False).transform(
        lambda s: s.rolling(window=window, min_periods=window).mean()
    )


def _rsi(
    close: pd.Series,
    session: pd.Series,
    period: int = 14,
) -> pd.Series:
    """
    Calculate Wilder-style RSI independently per session.

    The first `period` observations of each session remain NaN because
    there is insufficient historical information to calculate RSI.
    """
    delta = close.groupby(session, sort=False).diff()

    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)

    avg_gain = gain.groupby(session, sort=False).transform(
        lambda s: s.ewm(
            alpha=1.0 / period,
            adjust=False,
            min_periods=period,
        ).mean()
    )

    avg_loss = loss.groupby(session, sort=False).transform(
        lambda s: s.ewm(
            alpha=1.0 / period,
            adjust=False,
            min_periods=period,
        ).mean()
    )

    rs = avg_gain / avg_loss.replace(0.0, np.nan)

    return 100.0 - (100.0 / (1.0 + rs))


def _validate_input(df: pd.DataFrame) -> None:
    """Validate the minimum raw OHLCV contract."""
    missing = [column for column in OHLCV_COLUMNS if column not in df.columns]

    if missing:
        raise KeyError(
            f"Missing required OHLCV columns: {missing}. "
            f"Available columns: {df.columns.tolist()}"
        )

    if not isinstance(df.index, pd.DatetimeIndex):
        raise TypeError(
            "Feature engineering requires a DatetimeIndex."
        )


def build_features(
    df: pd.DataFrame,
    *,
    require_valid_features: bool = False,
) -> pd.DataFrame:
    """
    Build session-aware ML features and the forward 1-minute target.

    Parameters
    ----------
    df:
        One ticker's raw OHLCV DataFrame.

    require_valid_features:
        If True, return only rows where every feature and the target are
        finite. If False, preserve NaNs so callers can inspect warm-up
        periods and data quality.

    Returns
    -------
    pandas.DataFrame
        Raw OHLCV plus `_session`, all authoritative features, and target.
    """
    _validate_input(df)

    # The dataset has already been validated as chronological. Avoid
    # sort_index() here because the local pandas environment exhibited
    # abnormal behaviour around DatetimeIndex sorting/rendering.
    data = df[OHLCV_COLUMNS].copy()

    # Remove only rows with missing OHLC. Do not fill market prices.
    valid_ohlc = data[["first", "high", "low", "last"]].notna().all(axis=1)
    data = data.loc[valid_ohlc].copy()

    if data.empty:
        result = data.copy()
        result["_session"] = np.array([], dtype=np.int64)
        for feature in FEATURES:
            result[feature] = np.nan
        result[TARGET] = np.nan
        return result

    data["_session"] = _session_id(data.index)

    session = data["_session"]
    open_price = data["first"].astype(float)
    high = data["high"].astype(float)
    low = data["low"].astype(float)
    close = data["last"].astype(float)
    volume = data["volume"].astype(float)

    # ------------------------------------------------------------------
    # Returns
    # ------------------------------------------------------------------

    data["return_1"] = close.groupby(session, sort=False).pct_change(1)
    data["return_5"] = (
        close.groupby(session, sort=False).pct_change(5)
    )
    data["return_15"] = (
        close.groupby(session, sort=False).pct_change(15)
    )

    # ------------------------------------------------------------------
    # Candle structure
    # ------------------------------------------------------------------

    data["range_pct"] = (high - low) / close
    data["body_pct"] = (close - open_price) / open_price

    candle_range = high - low

    # A zero-range candle has no mathematically valid close location.
    # Preserve it as NaN rather than inventing a value.
    data["close_location"] = np.where(
        candle_range != 0.0,
        (close - low) / candle_range,
        np.nan,
    )

    # ------------------------------------------------------------------
    # Volatility / volume
    # ------------------------------------------------------------------

    data["volatility_10"] = _group_rolling_std(
        data["return_1"],
        session,
        10,
    )

    data["volatility_30"] = _group_rolling_std(
        data["return_1"],
        session,
        30,
    )

    volume_mean_20 = _group_rolling_mean(volume, session, 20)

    data["volume_ratio_20"] = np.where(
        volume_mean_20 != 0.0,
        volume / volume_mean_20,
        np.nan,
    )

    # ------------------------------------------------------------------
    # Moving-average distance
    # ------------------------------------------------------------------

    ema_5 = _group_ewm(close, session, 5)
    ema_20 = _group_ewm(close, session, 20)

    data["distance_ema_5"] = close / ema_5 - 1.0
    data["distance_ema_20"] = close / ema_20 - 1.0

    # ------------------------------------------------------------------
    # RSI
    # ------------------------------------------------------------------

    data["rsi_14"] = _rsi(close, session, 14)

    # ------------------------------------------------------------------
    # MACD
    #
    # MACD      = EMA12(close) - EMA26(close)
    # SIGNAL    = EMA9(MACD)
    # HIST      = MACD - SIGNAL
    #
    # Everything is calculated independently within each session.
    # ------------------------------------------------------------------

    ema_12 = _group_ewm(close, session, 12)
    ema_26 = _group_ewm(close, session, 26)

    data["macd"] = ema_12 - ema_26

    data["macd_signal"] = _group_ewm(
        data["macd"],
        session,
        9,
    )

    data["macd_hist"] = (
        data["macd"] - data["macd_signal"]
    )

    # ------------------------------------------------------------------
    # Forward 1-minute target
    #
    # pct_change(-1) is NOT used because we explicitly need the next
    # close within the same session.
    # ------------------------------------------------------------------

    next_close = close.groupby(session, sort=False).shift(-1)

    data[TARGET] = np.where(
        next_close.notna() & close.notna(),
        next_close / close - 1.0,
        np.nan,
    )

    if require_valid_features:
        required = FEATURES + [TARGET]

        finite = np.ones(len(data), dtype=bool)

        for column in required:
            finite &= np.isfinite(
                data[column].to_numpy(dtype=np.float64)
            )

        data = data.loc[finite].copy()

    return data


def make_sequences(
    feature_data: pd.DataFrame,
    *,
    sequence_length: int = SEQ_LENGTH,
) -> Tuple[np.ndarray, np.ndarray, pd.DatetimeIndex]:
    """
    Construct model sequences without crossing trading sessions.

    For every target timestamp t:

        X = [t-sequence_length+1 ... t]
        y = forward_1min_return[t]

    A sequence is accepted only when:
    - every feature value in the window is finite;
    - the target is finite;
    - the complete sequence belongs to one trading session.

    Sessions are processed independently so memory usage remains bounded.
    """
    if sequence_length < 1:
        raise ValueError("sequence_length must be >= 1")

    missing = [
        column
        for column in FEATURES + [TARGET, "_session"]
        if column not in feature_data.columns
    ]

    if missing:
        raise KeyError(f"Missing sequence columns: {missing}")

    X_values = feature_data[FEATURES].to_numpy(dtype=np.float32)
    y_values = feature_data[TARGET].to_numpy(dtype=np.float32)
    sessions = feature_data["_session"].to_numpy()
    timestamps = feature_data.index

    n_rows = len(feature_data)
    n_features = len(FEATURES)

    if n_rows < sequence_length:
        return (
            np.empty(
                (0, sequence_length, n_features),
                dtype=np.float32,
            ),
            np.empty((0,), dtype=np.float32),
            pd.DatetimeIndex([]),
        )

    # ------------------------------------------------------------------
    # Locate session boundaries.
    # ------------------------------------------------------------------

    changes = (
        np.flatnonzero(
            sessions[1:] != sessions[:-1]
        )
        + 1
    )

    session_starts = np.r_[0, changes]
    session_ends = np.r_[changes, n_rows]

    # ------------------------------------------------------------------
    # First pass: count valid sequences.
    # ------------------------------------------------------------------

    total_sequences = 0

    for session_start, session_end in zip(
        session_starts,
        session_ends,
    ):
        session_X = X_values[
            session_start:session_end
        ]

        session_y = y_values[
            session_start:session_end
        ]

        current_length = len(session_X)

        if current_length < sequence_length:
            continue

        # One boolean per row: does this row contain an invalid feature?
        row_invalid = ~np.isfinite(session_X).all(axis=1)

        # Prefix sum lets us determine whether any invalid row exists
        # inside each candidate sequence.
        invalid_prefix = np.concatenate(
            (
                np.array([0], dtype=np.int32),
                np.cumsum(
                    row_invalid.astype(np.int32)
                ),
            )
        )

        window_invalid = (
            invalid_prefix[sequence_length:]
            - invalid_prefix[:-sequence_length]
        )

        feature_valid = window_invalid == 0

        target_valid = np.isfinite(
            session_y[sequence_length - 1:]
        )

        total_sequences += int(
            np.count_nonzero(
                feature_valid & target_valid
            )
        )

    if total_sequences == 0:
        return (
            np.empty(
                (0, sequence_length, n_features),
                dtype=np.float32,
            ),
            np.empty((0,), dtype=np.float32),
            pd.DatetimeIndex([]),
        )

    # ------------------------------------------------------------------
    # Allocate final arrays once.
    # ------------------------------------------------------------------

    X_sequences = np.empty(
        (
            total_sequences,
            sequence_length,
            n_features,
        ),
        dtype=np.float32,
    )

    y_targets = np.empty(
        total_sequences,
        dtype=np.float32,
    )

    target_timestamps = np.empty(
        total_sequences,
        dtype="datetime64[ns]",
    )

    write_position = 0

    # ------------------------------------------------------------------
    # Second pass: populate the final arrays.
    # ------------------------------------------------------------------

    for session_start, session_end in zip(
        session_starts,
        session_ends,
    ):
        session_X = X_values[
            session_start:session_end
        ]

        session_y = y_values[
            session_start:session_end
        ]

        session_timestamps = timestamps[
            session_start:session_end
        ]

        current_length = len(session_X)

        if current_length < sequence_length:
            continue

        row_invalid = ~np.isfinite(
            session_X
        ).all(axis=1)

        invalid_prefix = np.concatenate(
            (
                np.array([0], dtype=np.int32),
                np.cumsum(
                    row_invalid.astype(np.int32)
                ),
            )
        )

        window_invalid = (
            invalid_prefix[sequence_length:]
            - invalid_prefix[:-sequence_length]
        )

        feature_valid = window_invalid == 0

        target_valid = np.isfinite(
            session_y[sequence_length - 1:]
        )

        valid = feature_valid & target_valid

        valid_ends = np.flatnonzero(valid)

        if len(valid_ends) == 0:
            continue

        # Only this session's windows are materialised.
        windows = np.lib.stride_tricks.sliding_window_view(
            session_X,
            window_shape=sequence_length,
            axis=0,
        )

        windows = np.transpose(
            windows,
            (0, 2, 1),
        )

        valid_windows = windows[valid_ends]

        count = len(valid_ends)

        X_sequences[
            write_position:
            write_position + count
        ] = valid_windows

        y_targets[
            write_position:
            write_position + count
        ] = session_y[
            sequence_length - 1:
        ][valid]

        timestamp_values = (
            session_timestamps[
                sequence_length - 1:
            ].to_numpy(dtype="datetime64[ns]")
        )

        target_timestamps[
            write_position:
            write_position + count
        ] = timestamp_values[valid]

        write_position += count

    if write_position != total_sequences:
        raise RuntimeError(
            "Sequence allocation mismatch: "
            f"expected {total_sequences}, "
            f"wrote {write_position}."
        )

    return (
        X_sequences,
        y_targets,
        pd.DatetimeIndex(target_timestamps),
    )

def iter_sequence_batches(
    feature_data: pd.DataFrame,
    *,
    sequence_length: int = SEQ_LENGTH,
    batch_size: int = 256,
):
    """
    Yield valid model sequences in bounded batches.

    The input is processed one trading session at a time. This prevents
    the complete feature matrix and complete sequence tensor from being
    materialised for a ticker simultaneously.

    Sequences never cross trading-session boundaries.
    """
    if sequence_length < 1:
        raise ValueError("sequence_length must be >= 1")

    if batch_size < 1:
        raise ValueError("batch_size must be >= 1")

    required = FEATURES + [TARGET, "_session"]

    missing = [
        column
        for column in required
        if column not in feature_data.columns
    ]

    if missing:
        raise KeyError(f"Missing sequence columns: {missing}")

    if feature_data.empty:
        return

    # Work session-by-session instead of converting the complete ticker
    # into large NumPy matrices.
    for _, session_data in feature_data.groupby(
        "_session",
        sort=False,
    ):
        if len(session_data) < sequence_length:
            continue

        X_values = session_data[FEATURES].to_numpy(
            dtype=np.float32,
            copy=True,
        )

        y_values = session_data[TARGET].to_numpy(
            dtype=np.float32,
            copy=True,
        )

        timestamps = session_data.index.asi8

        # A sequence ending at position i uses:
        #
        #     i - sequence_length + 1 ... i
        #
        # and predicts y[i].
        #
        # Therefore the first possible sequence ends at
        # sequence_length - 1.
        row_invalid = ~np.isfinite(X_values).all(axis=1)

        invalid_prefix = np.concatenate(
            (
                np.array([0], dtype=np.int32),
                np.cumsum(
                    row_invalid.astype(np.int32)
                ),
            )
        )

        window_invalid = (
            invalid_prefix[sequence_length:]
            - invalid_prefix[:-sequence_length]
        )

        valid_ends = (
            np.flatnonzero(
                (window_invalid == 0)
                & np.isfinite(
                    y_values[sequence_length - 1:]
                )
            )
            + (sequence_length - 1)
        )

        if len(valid_ends) == 0:
            continue

        offsets = np.arange(
            sequence_length,
            dtype=np.int64,
        )

        for batch_start in range(
            0,
            len(valid_ends),
            batch_size,
        ):
            batch_ends = valid_ends[
                batch_start:
                batch_start + batch_size
            ]

            indices = (
                batch_ends[:, None]
                - (sequence_length - 1)
                + offsets[None, :]
            )

            X_batch = np.ascontiguousarray(
                X_values[indices],
                dtype=np.float32,
            )

            y_batch = np.asarray(
                y_values[batch_ends],
                dtype=np.float32,
            )

            timestamp_batch = session_data.index[batch_ends]

            yield (
                X_batch,
                y_batch,
                timestamp_batch,
            )

def prepare_ticker_batches(
    df: pd.DataFrame,
    *,
    sequence_length: int = SEQ_LENGTH,
    batch_size: int = 256,
):
    """
    Build features for one ticker and stream model-ready sequence batches.

    The complete sequence tensor is never materialised. Sequence batches
    are generated session-by-session.
    """
    data = build_features(
        df,
        require_valid_features=False,
    )

    for X_batch, y_batch, timestamps in iter_sequence_batches(
        data,
        sequence_length=sequence_length,
        batch_size=batch_size,
    ):
        yield (
            FeatureResult(
                data=data,
                features=tuple(FEATURES),
                target=TARGET,
                sequence_length=sequence_length,
            ),
            X_batch,
            y_batch,
            timestamps,
        )

def prepare_ticker(
    df: pd.DataFrame,
    *,
    sequence_length: int = SEQ_LENGTH,
) -> Tuple[FeatureResult, np.ndarray, np.ndarray, pd.DatetimeIndex]:
    """
    Build features and model-ready sequences for one ticker.
    """
    data = build_features(df, require_valid_features=False)

    X, y, timestamps = make_sequences(
        data,
        sequence_length=sequence_length,
    )

    result = FeatureResult(
        data=data,
        features=tuple(FEATURES),
        target=TARGET,
        sequence_length=sequence_length,
    )

    return result, X, y, timestamps


def feature_summary(df: pd.DataFrame) -> Dict[str, int]:
    """
    Return finite/invalid counts for the authoritative features and target.
    """
    summary: Dict[str, int] = {}

    for column in FEATURES + [TARGET]:
        if column not in df.columns:
            summary[column] = 0
            continue

        values = df[column].to_numpy(dtype=np.float64)
        summary[column] = int(np.isfinite(values).sum())

    return summary

