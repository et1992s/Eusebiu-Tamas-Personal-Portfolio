"""
Runtime inference service for Zebio's production trading models.

Responsibilities
----------------
- Discover complete per-ticker model artifacts.
- Load and cache Keras models.
- Load matching feature/target scalers and metadata.
- Build the latest valid 30-row feature sequence.
- Apply the training-time input scaler.
- Predict 1-minute forward return.
- Inverse-transform the model output.

This module does NOT:
- train models;
- define trading strategies;
- generate buy/sell signals;
- perform backtesting;
- modify market data;
- hard-code excluded tickers.

The model universe is defined entirely by complete artifact triplets:

    <ticker>.keras
    <ticker>_scalers.pkl
    <ticker>_meta.json
"""

from __future__ import annotations

import json
import logging
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from tensorflow.keras.models import load_model

from app.services.trading.ml.feature_engineering import (
    FEATURES,
    SEQ_LENGTH,
    TARGET,
    build_features,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

DEFAULT_MODELS_DIR = (
    Path(__file__).resolve().parent.parent / "models"
)


# ---------------------------------------------------------------------------
# Runtime model bundle
# ---------------------------------------------------------------------------


@dataclass
class ModelBundle:
    """
    All runtime artifacts belonging to one ticker.
    """

    ticker: str
    model: object
    input_scaler: object
    target_scaler: object
    metadata: dict


# ---------------------------------------------------------------------------
# Inference service
# ---------------------------------------------------------------------------


class TradingInferenceService:
    """
    Runtime loader and inference service for the production trading models.

    Models are loaded lazily and cached in memory.

    A ticker is considered ML-supported only when all three artifacts exist:

        <ticker>.keras
        <ticker>_scalers.pkl
        <ticker>_meta.json
    """

    def __init__(
        self,
        models_dir: str | Path = DEFAULT_MODELS_DIR,
    ) -> None:
        self.models_dir = Path(models_dir)

        self._available_tickers: Optional[List[str]] = None
        self._models: Dict[str, ModelBundle] = {}

    # ------------------------------------------------------------------
    # Artifact discovery
    # ------------------------------------------------------------------

    def discover_tickers(self, refresh: bool = False) -> List[str]:
        """
        Discover tickers with a complete model artifact triplet.

        Incomplete artifacts are ignored.

        Returns
        -------
        list[str]
            Sorted ticker symbols supported by ML inference.
        """

        if self._available_tickers is not None and not refresh:
            return list(self._available_tickers)

        if not self.models_dir.exists():
            logger.warning(
                "Model directory does not exist: %s",
                self.models_dir,
            )
            self._available_tickers = []
            return []

        keras_tickers = {
            path.stem
            for path in self.models_dir.glob("*.keras")
        }

        scaler_tickers = {
            path.name.removesuffix("_scalers.pkl")
            for path in self.models_dir.glob("*_scalers.pkl")
        }

        metadata_tickers = {
            path.name.removesuffix("_meta.json")
            for path in self.models_dir.glob("*_meta.json")
        }

        complete = (
            keras_tickers
            & scaler_tickers
            & metadata_tickers
        )

        self._available_tickers = sorted(complete)

        logger.info(
            "Discovered %d complete ML model artifacts.",
            len(self._available_tickers),
        )

        return list(self._available_tickers)

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    def supports_ticker(self, ticker: str) -> bool:
        """
        Return whether a ticker has a complete production model.
        """

        normalized = ticker.upper().strip()

        return normalized in set(
            self.discover_tickers()
        )

    # ------------------------------------------------------------------
    # Artifact paths
    # ------------------------------------------------------------------

    def _model_path(self, ticker: str) -> Path:
        return self.models_dir / f"{ticker}.keras"

    def _scaler_path(self, ticker: str) -> Path:
        return self.models_dir / f"{ticker}_scalers.pkl"

    def _metadata_path(self, ticker: str) -> Path:
        return self.models_dir / f"{ticker}_meta.json"

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    def _load_metadata(self, ticker: str) -> dict:
        path = self._metadata_path(ticker)

        with path.open("r", encoding="utf-8") as handle:
            metadata = json.load(handle)

        if not isinstance(metadata, dict):
            raise ValueError(
                f"{ticker}: metadata must contain a JSON object."
            )

        return metadata

    # ------------------------------------------------------------------
    # Scalers
    # ------------------------------------------------------------------

    def _load_scalers(
        self,
        ticker: str,
    ) -> Tuple[object, object]:
        path = self._scaler_path(ticker)

        with path.open("rb") as handle:
            scalers = pickle.load(handle)

        if not isinstance(scalers, dict):
            raise ValueError(
                f"{ticker}: scaler artifact must contain a dictionary."
            )

        required_keys = {
            "input",
            "target",
            "features",
            "target_name",
            "seq_length",
            "scaler_type",
        }

        missing = required_keys - set(scalers)

        if missing:
            raise ValueError(
                f"{ticker}: scaler artifact missing keys: "
                f"{sorted(missing)}"
            )

        input_scaler = scalers["input"]
        target_scaler = scalers["target"]

        if not hasattr(input_scaler, "transform"):
            raise TypeError(
                f"{ticker}: input scaler does not support transform()."
            )

        if not hasattr(target_scaler, "inverse_transform"):
            raise TypeError(
                f"{ticker}: target scaler does not support "
                "inverse_transform()."
            )

        if getattr(input_scaler, "n_features_in_", None) != len(FEATURES):
            raise ValueError(
                f"{ticker}: input scaler expects "
                f"{getattr(input_scaler, 'n_features_in_', None)} "
                f"features, expected {len(FEATURES)}."
            )

        return input_scaler, target_scaler

    # ------------------------------------------------------------------
    # Contract validation
    # ------------------------------------------------------------------

    def _validate_metadata(
        self,
        ticker: str,
        metadata: dict,
    ) -> None:
        metadata_ticker = metadata.get("ticker")

        if metadata_ticker != ticker:
            raise ValueError(
                f"{ticker}: metadata ticker is "
                f"{metadata_ticker!r}."
            )

        metadata_features = metadata.get("features")

        if metadata_features != FEATURES:
            raise ValueError(
                f"{ticker}: metadata feature contract does not "
                "match the runtime feature contract."
            )

        metadata_target = metadata.get("target")

        if metadata_target != TARGET:
            raise ValueError(
                f"{ticker}: metadata target is "
                f"{metadata_target!r}; expected {TARGET!r}."
            )

        metadata_seq_length = metadata.get("seq_length")

        if metadata_seq_length != SEQ_LENGTH:
            raise ValueError(
                f"{ticker}: metadata sequence length is "
                f"{metadata_seq_length}; expected {SEQ_LENGTH}."
            )

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------

    def load_ticker(
        self,
        ticker: str,
    ) -> ModelBundle:
        """
        Load one ticker's complete model bundle.

        The bundle is cached after the first successful load.
        """

        normalized = ticker.upper().strip()

        if normalized in self._models:
            return self._models[normalized]

        if not self.supports_ticker(normalized):
            raise ValueError(
                f"{normalized}: no complete production model "
                "artifact set is available."
            )

        model_path = self._model_path(normalized)

        logger.info(
            "Loading ML model for %s from %s",
            normalized,
            model_path,
        )

        model = load_model(
            model_path,
            compile=False,
        )

        metadata = self._load_metadata(normalized)

        self._validate_metadata(
            normalized,
            metadata,
        )

        input_scaler, target_scaler = self._load_scalers(
            normalized,
        )

        bundle = ModelBundle(
            ticker=normalized,
            model=model,
            input_scaler=input_scaler,
            target_scaler=target_scaler,
            metadata=metadata,
        )

        self._models[normalized] = bundle

        logger.info(
            "Loaded ML model for %s successfully.",
            normalized,
        )

        return bundle

    # ------------------------------------------------------------------
    # Feature-window construction
    # ------------------------------------------------------------------

    @staticmethod
    def _latest_feature_window(
        feature_data: pd.DataFrame,
        sequence_length: int,
    ) -> Tuple[np.ndarray, pd.Timestamp]:
        """
        Extract the latest valid feature window.

        Unlike training sequence generation, inference does not require
        TARGET to be finite because the target for the current/latest
        observation is unknown at prediction time.

        The window must:
        - contain exactly sequence_length rows;
        - belong to one trading session;
        - contain finite values for every feature.
        """

        if sequence_length < 1:
            raise ValueError(
                "sequence_length must be >= 1."
            )

        if len(feature_data) < sequence_length:
            raise ValueError(
                "Not enough rows to construct an inference sequence: "
                f"{len(feature_data)} < {sequence_length}."
            )

        if "_session" not in feature_data.columns:
            raise KeyError(
                "Feature data is missing '_session'."
            )

        feature_values = feature_data[
            FEATURES
        ].to_numpy(dtype=np.float64)

        sessions = feature_data[
            "_session"
        ].to_numpy()

        timestamps = feature_data.index

        end_position = len(feature_data)

        # Work backwards from the newest row until a valid
        # session-contained feature window is found.
        for end in range(
            end_position,
            sequence_length - 1,
            -1,
        ):
            start = end - sequence_length

            window_sessions = sessions[
                start:end
            ]

            if len(window_sessions) != sequence_length:
                continue

            if not np.all(
                window_sessions == window_sessions[0]
            ):
                continue

            window = feature_values[
                start:end
            ]

            if not np.isfinite(window).all():
                continue

            return (
                window.astype(
                    np.float32,
                    copy=False,
                ),
                pd.Timestamp(timestamps[end - 1]),
            )

        raise ValueError(
            "No valid session-contained feature window "
            f"of length {sequence_length} was found."
        )

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------

    def predict(
        self,
        ticker: str,
        bars: pd.DataFrame,
    ) -> dict:
        """
        Predict the next one-minute return for a ticker.

        Parameters
        ----------
        ticker:
            Ticker symbol.

        bars:
            Raw OHLCV DataFrame using the production market-data schema:

                first
                high
                low
                last
                volume

            with a DatetimeIndex.

        Returns
        -------
        dict
            Structured prediction result.
        """

        normalized = ticker.upper().strip()

        bundle = self.load_ticker(normalized)

        # Build the exact same production features used during training.
        feature_data = build_features(
            bars,
            require_valid_features=False,
        )

        sequence, timestamp = self._latest_feature_window(
            feature_data,
            sequence_length=SEQ_LENGTH,
        )

        # StandardScaler expects rows of shape:
        #
        #     (n_samples, n_features)
        #
        # so flatten the sequence temporarily, scale each feature row,
        # then restore the model's 3-D sequence shape.
        flat_sequence = sequence.reshape(
            -1,
            len(FEATURES),
        )

        scaled_flat_sequence = bundle.input_scaler.transform(
            flat_sequence
        )

        scaled_sequence = scaled_flat_sequence.reshape(
            1,
            SEQ_LENGTH,
            len(FEATURES),
        ).astype(
            np.float32,
            copy=False,
        )

        prediction_scaled = bundle.model.predict(
            scaled_sequence,
            verbose=0,
        )

        prediction_scaled = np.asarray(
            prediction_scaled,
            dtype=np.float64,
        ).reshape(-1, 1)

        prediction_return = (
            bundle.target_scaler
            .inverse_transform(prediction_scaled)
            .reshape(-1)
        )

        predicted_return = float(
            prediction_return[0]
        )

        return {
            "ticker": normalized,
            "timestamp": timestamp.isoformat(),
            "target": TARGET,
            "predicted_return": predicted_return,
            "model_type": bundle.metadata.get(
                "model_type"
            ),
            "seq_length": SEQ_LENGTH,
            "features": list(FEATURES),
        }

    # ------------------------------------------------------------------
    # Cache management
    # ------------------------------------------------------------------

    def loaded_tickers(self) -> List[str]:
        """
        Return tickers whose model bundles are currently loaded.
        """

        return sorted(self._models)

    def clear_cache(self) -> None:
        """
        Release all cached model bundles.
        """

        self._models.clear()

    def clear_ticker(self, ticker: str) -> None:
        """
        Release one cached model bundle.
        """

        self._models.pop(
            ticker.upper().strip(),
            None,
        )


# ---------------------------------------------------------------------------
# Shared service instance
# ---------------------------------------------------------------------------

inference_service = TradingInferenceService()