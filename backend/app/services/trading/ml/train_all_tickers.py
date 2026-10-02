"""
Train one CNN-BiLSTM forward-return model per ticker.

Training contract
-----------------
Input:
    15 authoritative, session-aware features from feature_engineering.py

Target:
    forward_1min_return

Sequence:
    30 consecutive bars within one trading session

Split:
    70% train sessions
    15% validation sessions
    15% test sessions

Scaling:
    Feature scalers are fitted ONLY on training rows.
    Target scaler is fitted ONLY on training targets.

Memory:
    One ticker is loaded at a time.
    Sequences are streamed in bounded batches.
    Complete sequence tensors are never materialised.

Prediction and strategy are deliberately separate.
This module trains a return predictor only.
"""

from __future__ import annotations

import gc
import json
import pickle
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np
import pandas as pd

from sklearn.preprocessing import StandardScaler

from tensorflow.keras.callbacks import (
    EarlyStopping,
    ModelCheckpoint,
    ReduceLROnPlateau,
)
from tensorflow.keras.layers import (
    BatchNormalization,
    Bidirectional,
    Conv1D,
    Dense,
    Dropout,
    LSTM,
    MaxPooling1D,
)
from tensorflow.keras.models import Sequential
from tensorflow.keras.optimizers import Adam

from app.services.trading.ml.feature_engineering import (
    FEATURES,
    SEQ_LENGTH,
    TARGET,
    build_features,
    iter_sequence_batches,
)


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO = Path(__file__).resolve().parents[4]

DATA = REPO / "data" / "algoseek_preprocessed.pkl"

MODELS = Path(__file__).resolve().parent.parent / "models"
MODELS.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Training configuration
# ---------------------------------------------------------------------------

TRAIN_RATIO = 0.70
VALIDATION_RATIO = 0.15
TEST_RATIO = 0.15

BATCH_SIZE = 256
EPOCHS = 40

CNN_FILTERS = 64
LSTM_UNITS = 64
KERNEL_SIZE = 3
DROPOUT_RATE = 0.30
ACTIVATION = "tanh"
LEARNING_RATE = 1e-3

EARLY_STOPPING_PATIENCE = 6
REDUCE_LR_PATIENCE = 3
MIN_LEARNING_RATE = 1e-6


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_split_ratios() -> None:
    total = (
        TRAIN_RATIO
        + VALIDATION_RATIO
        + TEST_RATIO
    )

    if not np.isclose(total, 1.0):
        raise ValueError(
            "TRAIN_RATIO + VALIDATION_RATIO + TEST_RATIO "
            f"must equal 1.0, got {total}"
        )


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

def build_model(n_features: int) -> Sequential:
    """
    Build the CNN-BiLSTM-LSTM return-prediction model.

    The architecture preserves the core hybrid model used in the
    original project while using the new forward-return target.
    """

    model = Sequential(
        [
            Conv1D(
                filters=CNN_FILTERS,
                kernel_size=KERNEL_SIZE,
                padding="same",
                activation=ACTIVATION,
                input_shape=(
                    SEQ_LENGTH,
                    n_features,
                ),
            ),
            BatchNormalization(),
            MaxPooling1D(pool_size=2),
            Dropout(DROPOUT_RATE),

            Conv1D(
                filters=CNN_FILTERS,
                kernel_size=KERNEL_SIZE,
                padding="same",
                activation=ACTIVATION,
            ),
            BatchNormalization(),
            MaxPooling1D(pool_size=2),
            Dropout(DROPOUT_RATE),

            Dense(
                32,
                activation=ACTIVATION,
            ),

            Bidirectional(
                LSTM(
                    LSTM_UNITS,
                    return_sequences=True,
                    recurrent_dropout=0.1,
                )
            ),

            Dropout(DROPOUT_RATE),

            LSTM(
                LSTM_UNITS,
                recurrent_dropout=0.1,
            ),

            Dropout(DROPOUT_RATE),

            Dense(
                32,
                activation=ACTIVATION,
            ),

            Dense(
                1,
                activation="linear",
            ),
        ]
    )

    model.compile(
        optimizer=Adam(
            learning_rate=LEARNING_RATE,
        ),
        loss="mse",
        metrics=["mae"],
    )

    return model


# ---------------------------------------------------------------------------
# Session splitting
# ---------------------------------------------------------------------------

def split_sessions(
    feature_data: pd.DataFrame,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Split a ticker chronologically by trading session.

    No randomisation is performed.

    Returns
    -------
    train_sessions, validation_sessions, test_sessions
    """

    sessions = np.asarray(
        feature_data["_session"]
        .drop_duplicates()
        .to_numpy()
    )

    if len(sessions) < 3:
        raise ValueError(
            f"Need at least 3 sessions, got {len(sessions)}"
        )

    n_sessions = len(sessions)

    train_count = max(
        1,
        int(np.floor(
            n_sessions * TRAIN_RATIO
        )),
    )

    validation_count = max(
        1,
        int(np.floor(
            n_sessions * VALIDATION_RATIO
        )),
    )

    # Make sure at least one session remains for test.
    if train_count + validation_count >= n_sessions:
        validation_count = max(
            1,
            n_sessions - train_count - 1,
        )

    test_start = train_count + validation_count

    if test_start >= n_sessions:
        raise ValueError(
            "Unable to create a non-empty chronological test split."
        )

    train_sessions = sessions[:train_count]

    validation_sessions = sessions[
        train_count:test_start
    ]

    test_sessions = sessions[test_start:]

    if (
        len(train_sessions) == 0
        or len(validation_sessions) == 0
        or len(test_sessions) == 0
    ):
        raise ValueError(
            "One or more chronological splits is empty."
        )

    return (
        train_sessions,
        validation_sessions,
        test_sessions,
    )


# ---------------------------------------------------------------------------
# Session selection
# ---------------------------------------------------------------------------

def select_sessions(
    feature_data: pd.DataFrame,
    sessions: Sequence,
) -> pd.DataFrame:
    """Return only the requested trading sessions."""

    session_set = set(sessions)

    mask = feature_data["_session"].isin(
        session_set
    )

    return feature_data.loc[mask].copy()


# ---------------------------------------------------------------------------
# Scalers
# ---------------------------------------------------------------------------

def fit_scalers(
    train_data: pd.DataFrame,
) -> Tuple[StandardScaler, StandardScaler]:
    """
    Fit feature and target scalers using training data only.

    Rows containing invalid feature values are excluded from the scaler
    fitting process. No values are imputed.
    """

    feature_values = train_data[
        FEATURES
    ].to_numpy(
        dtype=np.float64,
        copy=False,
    )

    target_values = train_data[
        TARGET
    ].to_numpy(
        dtype=np.float64,
        copy=False,
    )

    feature_valid = np.isfinite(
        feature_values
    ).all(axis=1)

    target_valid = np.isfinite(
        target_values
    )

    if not feature_valid.any():
        raise ValueError(
            "Training data contains no rows with all "
            "features finite."
        )

    if not target_valid.any():
        raise ValueError(
            "Training data contains no finite targets."
        )

    feature_scaler = StandardScaler()

    feature_scaler.fit(
        feature_values[feature_valid]
    )

    target_scaler = StandardScaler()

    target_scaler.fit(
        target_values[target_valid].reshape(-1, 1)
    )

    return (
        feature_scaler,
        target_scaler,
    )


def scale_feature_data(
    feature_data: pd.DataFrame,
    feature_scaler: StandardScaler,
    target_scaler: StandardScaler,
) -> pd.DataFrame:
    """
    Apply already-fitted scalers.

    Invalid feature rows remain NaN so the sequence generator can reject
    sequences containing incomplete feature windows.

    Invalid targets remain NaN.
    """

    data = feature_data.copy()

    feature_values = data[
        FEATURES
    ].to_numpy(
        dtype=np.float64,
        copy=True,
    )

    feature_valid = np.isfinite(
        feature_values
    ).all(axis=1)

    if feature_valid.any():
        feature_values[
            feature_valid
        ] = feature_scaler.transform(
            feature_values[feature_valid]
        )

    data.loc[:, FEATURES] = feature_values

    target_values = data[
        TARGET
    ].to_numpy(
        dtype=np.float64,
        copy=True,
    )

    target_valid = np.isfinite(
        target_values
    )

    if target_valid.any():
        target_values[target_valid] = (
            target_scaler.transform(
                target_values[
                    target_valid
                ].reshape(-1, 1)
            ).ravel()
        )

    data.loc[:, TARGET] = target_values

    return data


# ---------------------------------------------------------------------------
# Sequence counting
# ---------------------------------------------------------------------------

def count_sequences(
    feature_data: pd.DataFrame,
) -> int:
    """
    Count usable sequences without materialising them.

    This intentionally walks the same streaming generator that will be
    used for training.
    """

    total = 0

    for X_batch, _, _ in iter_sequence_batches(
        feature_data,
        sequence_length=SEQ_LENGTH,
        batch_size=BATCH_SIZE,
    ):
        total += len(X_batch)

    return total


# ---------------------------------------------------------------------------
# Keras generator
# ---------------------------------------------------------------------------

def batch_generator(
    feature_data: pd.DataFrame,
) -> Iterable[Tuple[np.ndarray, np.ndarray]]:
    """
    Create an infinite generator suitable for model.fit().

    Each epoch starts again from the beginning of the chronological
    session sequence.
    """

    while True:
        yielded = False

        for X_batch, y_batch, _ in iter_sequence_batches(
            feature_data,
            sequence_length=SEQ_LENGTH,
            batch_size=BATCH_SIZE,
        ):
            yielded = True

            yield (
                X_batch,
                y_batch.reshape(-1, 1),
            )

        if not yielded:
            raise RuntimeError(
                "Sequence generator produced no training batches."
            )


# ---------------------------------------------------------------------------
# Prediction / evaluation
# ---------------------------------------------------------------------------

def predict_split(
    model: Sequential,
    feature_data: pd.DataFrame,
    target_scaler: StandardScaler,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Predict a complete split in bounded batches.

    Returns predictions and actual forward returns in their original
    unscaled units.
    """

    predictions: List[np.ndarray] = []
    actual: List[np.ndarray] = []

    for X_batch, y_batch, _ in iter_sequence_batches(
        feature_data,
        sequence_length=SEQ_LENGTH,
        batch_size=BATCH_SIZE,
    ):
        pred_scaled = model.predict(
            X_batch,
            verbose=0,
        ).reshape(-1, 1)

        pred = target_scaler.inverse_transform(
            pred_scaled
        ).ravel()

        actual_batch = target_scaler.inverse_transform(
            y_batch.reshape(-1, 1)
        ).ravel()

        predictions.append(pred)
        actual.append(actual_batch)

    if not predictions:
        raise ValueError(
            "No sequences available for evaluation."
        )

    return (
        np.concatenate(predictions),
        np.concatenate(actual),
    )


def calculate_metrics(
    predictions: np.ndarray,
    actual: np.ndarray,
) -> Dict[str, float]:
    """Calculate return-prediction regression metrics."""

    errors = predictions - actual

    rmse = float(
        np.sqrt(
            np.mean(
                np.square(errors)
            )
        )
    )

    mae = float(
        np.mean(
            np.abs(errors)
        )
    )

    directional_accuracy = float(
        np.mean(
            np.sign(predictions)
            == np.sign(actual)
        )
    )

    correlation = np.nan

    if (
        len(predictions) > 1
        and np.std(predictions) > 0
        and np.std(actual) > 0
    ):
        correlation = float(
            np.corrcoef(
                predictions,
                actual,
            )[0, 1]
        )

    return {
        "rmse": rmse,
        "mae": mae,
        "directional_accuracy": directional_accuracy,
        "correlation": correlation,
    }


# ---------------------------------------------------------------------------
# Training one ticker
# ---------------------------------------------------------------------------

def train_one(
    ticker: str,
    raw_df: pd.DataFrame,
    verbose: int = 1,
) -> Dict[str, object]:
    """
    Train one ticker using chronological session splits.
    """

    print(
        f"\n[{ticker}] Building features...",
        flush=True,
    )

    feature_data = build_features(
        raw_df,
        require_valid_features=False,
    )

    if feature_data.empty:
        raise ValueError(
            f"{ticker}: feature data is empty."
        )

    train_sessions, validation_sessions, test_sessions = (
        split_sessions(feature_data)
    )

    print(
        f"[{ticker}] Sessions: "
        f"train={len(train_sessions)} "
        f"validation={len(validation_sessions)} "
        f"test={len(test_sessions)}",
        flush=True,
    )

    train_data = select_sessions(
        feature_data,
        train_sessions,
    )

    validation_data = select_sessions(
        feature_data,
        validation_sessions,
    )

    test_data = select_sessions(
        feature_data,
        test_sessions,
    )

    print(
        f"[{ticker}] Fitting scalers on training data only...",
        flush=True,
    )

    feature_scaler, target_scaler = fit_scalers(
        train_data
    )

    train_scaled = scale_feature_data(
        train_data,
        feature_scaler,
        target_scaler,
    )

    validation_scaled = scale_feature_data(
        validation_data,
        feature_scaler,
        target_scaler,
    )

    test_scaled = scale_feature_data(
        test_data,
        feature_scaler,
        target_scaler,
    )

    print(
        f"[{ticker}] Counting usable sequences...",
        flush=True,
    )

    train_sequences = count_sequences(
        train_scaled
    )

    validation_sequences = count_sequences(
        validation_scaled
    )

    test_sequences = count_sequences(
        test_scaled
    )

    if train_sequences == 0:
        raise ValueError(
            f"{ticker}: no usable training sequences."
        )

    if validation_sequences == 0:
        raise ValueError(
            f"{ticker}: no usable validation sequences."
        )

    if test_sequences == 0:
        raise ValueError(
            f"{ticker}: no usable test sequences."
        )

    print(
        f"[{ticker}] Sequences: "
        f"train={train_sequences:,} "
        f"validation={validation_sequences:,} "
        f"test={test_sequences:,}",
        flush=True,
    )

    model = build_model(
        n_features=len(FEATURES)
    )

    model_path = MODELS / f"{ticker}.keras"

    callbacks = [
        EarlyStopping(
            monitor="val_loss",
            patience=EARLY_STOPPING_PATIENCE,
            restore_best_weights=True,
            verbose=1 if verbose else 0,
        ),
        ReduceLROnPlateau(
            monitor="val_loss",
            factor=0.5,
            patience=REDUCE_LR_PATIENCE,
            min_lr=MIN_LEARNING_RATE,
            verbose=1 if verbose else 0,
        ),
        ModelCheckpoint(
            filepath=str(model_path),
            monitor="val_loss",
            save_best_only=True,
            verbose=1 if verbose else 0,
        ),
    ]

    train_steps = int(
        np.ceil(
            train_sequences / BATCH_SIZE
        )
    )

    validation_steps = int(
        np.ceil(
            validation_sequences / BATCH_SIZE
        )
    )

    print(
        f"[{ticker}] Training "
        f"({train_steps} train batches/epoch, "
        f"{validation_steps} validation batches/epoch)...",
        flush=True,
    )

    model.fit(
        batch_generator(train_scaled),
        steps_per_epoch=train_steps,
        validation_data=batch_generator(
            validation_scaled
        ),
        validation_steps=validation_steps,
        epochs=EPOCHS,
        callbacks=callbacks,
        verbose=verbose,
    )

    print(
        f"[{ticker}] Evaluating held-out test set...",
        flush=True,
    )

    test_predictions, test_actual = predict_split(
        model,
        test_scaled,
        target_scaler,
    )

    metrics = calculate_metrics(
        test_predictions,
        test_actual,
    )

    print(
        f"[{ticker}] "
        f"RMSE={metrics['rmse']:.8f} "
        f"MAE={metrics['mae']:.8f} "
        f"Direction={metrics['directional_accuracy']:.4f}",
        flush=True,
    )

    # ------------------------------------------------------------------
    # Save preprocessing contract
    # ------------------------------------------------------------------

    scaler_path = MODELS / f"{ticker}_scalers.pkl"

    with open(
        scaler_path,
        "wb",
    ) as f:
        pickle.dump(
            {
                "input": feature_scaler,
                "target": target_scaler,
                "features": list(FEATURES),
                "target_name": TARGET,
                "seq_length": SEQ_LENGTH,
                "scaler_type": "StandardScaler",
            },
            f,
        )

    # ------------------------------------------------------------------
    # Save metadata
    # ------------------------------------------------------------------

    metadata = {
        "ticker": ticker,
        "features": list(FEATURES),
        "target": TARGET,
        "seq_length": SEQ_LENGTH,
        "model_type": "CNN-BiLSTM-LSTM",
        "split": {
            "method": "chronological_by_session",
            "train_ratio": TRAIN_RATIO,
            "validation_ratio": VALIDATION_RATIO,
            "test_ratio": TEST_RATIO,
            "train_sessions": int(len(train_sessions)),
            "validation_sessions": int(
                len(validation_sessions)
            ),
            "test_sessions": int(
                len(test_sessions)
            ),
        },
        "sequences": {
            "train": int(train_sequences),
            "validation": int(validation_sequences),
            "test": int(test_sequences),
        },
        "rows": {
            "raw": int(len(raw_df)),
            "features": int(len(feature_data)),
            "train": int(len(train_data)),
            "validation": int(len(validation_data)),
            "test": int(len(test_data)),
        },
        "metrics": metrics,
        "hyperparameters": {
            "cnn_filters": CNN_FILTERS,
            "lstm_units": LSTM_UNITS,
            "kernel_size": KERNEL_SIZE,
            "dropout_rate": DROPOUT_RATE,
            "activation": ACTIVATION,
            "learning_rate": LEARNING_RATE,
            "batch_size": BATCH_SIZE,
            "epochs": EPOCHS,
        },
        "strategy": None,
        "notes": [
            "Prediction model only.",
            "Strategy thresholds are intentionally not embedded.",
            "Features are session-aware.",
            "Sequences never cross trading sessions.",
            "Scalers are fitted on training data only.",
        ],
    }

    meta_path = MODELS / f"{ticker}_meta.json"

    meta_path.write_text(
        json.dumps(
            metadata,
            indent=2,
            allow_nan=False,
        ),
        encoding="utf-8",
    )

    # Explicitly release large ticker-specific objects before moving
    # to the next ticker.
    del train_data
    del validation_data
    del test_data
    del train_scaled
    del validation_scaled
    del test_scaled
    del feature_data
    del model

    gc.collect()

    return metadata


# ---------------------------------------------------------------------------
# Dataset loading
# ---------------------------------------------------------------------------

def load_dataset():
    """Load the existing Algoseek dataset."""

    if not DATA.exists():
        raise FileNotFoundError(
            f"Dataset not found: {DATA}"
        )

    print(
        f"Loading dataset: {DATA}",
        flush=True,
    )

    with open(
        DATA,
        "rb",
    ) as f:
        blob = pickle.load(f)

    if (
        isinstance(blob, dict)
        and "data" in blob
    ):
        tickers = list(
            blob.get(
                "tickers",
                blob["data"].keys(),
            )
        )

        def get_df(ticker):
            return blob["data"][ticker]

        return tickers, get_df

    if isinstance(blob, pd.DataFrame):
        if "ticker" not in blob.index.names:
            raise ValueError(
                "Flat DataFrame dataset must have a "
                "'ticker' index level."
            )

        tickers = sorted(
            blob.index
            .get_level_values("ticker")
            .unique()
        )

        def get_df(ticker):
            return blob.xs(
                ticker,
                level="ticker",
            )

        return tickers, get_df

    raise TypeError(
        "Unsupported dataset structure."
    )

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    validate_split_ratios()

    tickers, get_df = load_dataset()

    print(
        f"Training {len(tickers)} tickers",
        flush=True,
    )

    print(
        f"Features: {len(FEATURES)}",
        flush=True,
    )

    print(
        f"Target: {TARGET}",
        flush=True,
    )

    print(
        f"Sequence length: {SEQ_LENGTH}",
        flush=True,
    )

    print(
        f"Batch size: {BATCH_SIZE}",
        flush=True,
    )

    print()

    successful = 0
    failed = 0

    for ticker in tickers:
        started = time.time()

        print(
            "=" * 72,
            flush=True,
        )

        print(
            f"[{ticker}] START",
            flush=True,
        )

        try:
            raw_df = get_df(ticker)

            metadata = train_one(
                ticker,
                raw_df,
                verbose=0,
            )

            elapsed = time.time() - started

            metrics = metadata["metrics"]

            print(
                f"[{ticker}] COMPLETE "
                f"in {elapsed:.1f}s | "
                f"RMSE={metrics['rmse']:.8f} | "
                f"MAE={metrics['mae']:.8f} | "
                f"Direction={metrics['directional_accuracy']:.4f} | "
                f"Correlation={metrics['correlation']:.6f}",
                flush=True,
            )

            successful += 1

            del raw_df
            del metadata
            gc.collect()

        except Exception as exc:
            elapsed = time.time() - started

            failed += 1

            print(
                f"[{ticker}] FAILED after "
                f"{elapsed:.1f}s: {exc}",
                flush=True,
            )

    print()
    print("=" * 72)

    print(
        f"Training finished: "
        f"{successful} successful, "
        f"{failed} failed",
        flush=True,
    )

    print(
        f"Artifacts: {MODELS}",
        flush=True,
    )


if __name__ == "__main__":
    main()
