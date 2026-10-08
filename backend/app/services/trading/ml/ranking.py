"""
ranking.py - Model quality and current long opportunity ranking for Zebio.

The ranking layer combines:

1. Historical out-of-sample model quality from model metadata.
2. Current production inference.
3. Current short-term market volatility.
4. A volatility-normalised positive prediction signal.
5. The latest market price used for downstream portfolio allocation.

This service is intentionally long-only.

It does not:
    - train models
    - load Keras models directly
    - implement feature engineering
    - execute trades
    - modify paper-trading state
    - allocate portfolio capital

Those responsibilities remain in their existing services.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from app.services.trading.live.provider import MarketDataProvider
from app.services.trading.ml.inference import inference_service


MODELS_DIR = Path(__file__).resolve().parent.parent / "models"

DEFAULT_BARS_LIMIT = 100
DEFAULT_VOLATILITY_WINDOW = 30

DEFAULT_MIN_CORRELATION = 0.0
DEFAULT_MIN_DIRECTIONAL_ACCURACY = 0.50
DEFAULT_MIN_PREDICTED_RETURN = 0.0

DEFAULT_QUALITY_WEIGHT = 0.60
DEFAULT_SIGNAL_WEIGHT = 0.40


@dataclass(frozen=True)
class RankingConfig:
    bars_limit: int = DEFAULT_BARS_LIMIT
    volatility_window: int = DEFAULT_VOLATILITY_WINDOW

    min_correlation: float = DEFAULT_MIN_CORRELATION
    min_directional_accuracy: float = 0.50
    min_predicted_return: float = DEFAULT_MIN_PREDICTED_RETURN

    quality_weight: float = DEFAULT_QUALITY_WEIGHT
    signal_weight: float = DEFAULT_SIGNAL_WEIGHT

    def __post_init__(self) -> None:
        if self.bars_limit <= 0:
            raise ValueError("bars_limit must be greater than zero.")

        if self.volatility_window < 2:
            raise ValueError(
                "volatility_window must be at least 2."
            )

        if not 0.0 <= self.quality_weight <= 1.0:
            raise ValueError(
                "quality_weight must be between 0 and 1."
            )

        if not 0.0 <= self.signal_weight <= 1.0:
            raise ValueError(
                "signal_weight must be between 0 and 1."
            )

        weight_sum = (
            self.quality_weight
            + self.signal_weight
        )

        if not math.isclose(
            weight_sum,
            1.0,
            rel_tol=1e-9,
            abs_tol=1e-9,
        ):
            raise ValueError(
                "quality_weight and signal_weight "
                "must sum to 1."
            )


class ModelRankingService:
    """
    Rank production models by historical quality and current
    long-side opportunity.

    Historical model quality answers:

        "How trustworthy has this model been on unseen data?"

    Current opportunity answers:

        "How attractive is the model's current positive
        prediction relative to recent volatility?"

    The ranking layer only identifies candidates.

    It does not decide position size or execute trades.
    """

    def __init__(
        self,
        provider: MarketDataProvider,
        config: RankingConfig | None = None,
        models_dir: Path | None = None,
    ) -> None:
        self.provider = provider
        self.config = config or RankingConfig()
        self.models_dir = models_dir or MODELS_DIR

    def discover_models(self) -> list[dict[str, Any]]:
        """
        Discover complete production model bundles.
        """

        if not self.models_dir.exists():
            raise FileNotFoundError(
                f"Model directory does not exist: {self.models_dir}"
            )

        models: list[dict[str, Any]] = []

        for metadata_path in sorted(
            self.models_dir.glob("*_meta.json")
        ):
            ticker = metadata_path.name.removesuffix(
                "_meta.json"
            ).upper()

            model_path = (
                self.models_dir / f"{ticker}.keras"
            )

            scaler_path = (
                self.models_dir
                / f"{ticker}_scalers.pkl"
            )

            if (
                not model_path.exists()
                or not scaler_path.exists()
            ):
                continue

            try:
                with metadata_path.open(
                    "r",
                    encoding="utf-8",
                ) as handle:
                    metadata = json.load(handle)
            except (OSError, json.JSONDecodeError):
                continue

            metrics = metadata.get("metrics")

            if not isinstance(metrics, dict):
                continue

            models.append(
                {
                    "ticker": ticker,
                    "metadata": metadata,
                    "metrics": metrics,
                }
            )

        return models

    def _calculate_model_quality(
        self,
        correlation: float,
        directional_accuracy: float,
    ) -> float:
        """
        Calculate historical model quality.

        Correlation is mapped from [-1, 1] to [0, 1].

        Directional accuracy already occupies [0, 1].
        """

        correlation_score = (
            correlation + 1.0
        ) / 2.0

        quality = (
            self.config.quality_weight
            * correlation_score
            + self.config.signal_weight
            * directional_accuracy
        )

        return float(
            max(
                0.0,
                min(1.0, quality),
            )
        )

    def _is_model_eligible(
        self,
        correlation: float,
        directional_accuracy: float,
    ) -> bool:
        """
        Apply historical predictive-quality gates.

        Current prediction is deliberately handled separately.
        """

        return (
            correlation
            >= self.config.min_correlation
            and directional_accuracy
            >= self.config.min_directional_accuracy
        )

    @staticmethod
    def _calculate_recent_volatility(
        bars: pd.DataFrame,
        window: int,
    ) -> float:
        """
        Calculate recent close-to-close return volatility.
        """

        if "last" not in bars.columns:
            raise ValueError(
                "Market data must contain a 'last' column."
            )

        closes = pd.to_numeric(
            bars["last"],
            errors="coerce",
        ).dropna()

        if len(closes) < 2:
            return float("nan")

        returns = (
            closes
            .pct_change()
            .dropna()
        )

        if returns.empty:
            return float("nan")

        returns = returns.tail(window)

        if len(returns) < 2:
            return float("nan")

        volatility = float(
            returns.std(ddof=1)
        )

        if not math.isfinite(volatility):
            return float("nan")

        return volatility

    @staticmethod
    def _calculate_normalised_signal(
        predicted_return: float,
        recent_volatility: float,
    ) -> float:
        """
        Express predicted return in units of recent volatility.
        """

        if (
            not math.isfinite(predicted_return)
            or not math.isfinite(recent_volatility)
            or recent_volatility <= 0.0
        ):
            return float("nan")

        return float(
            predicted_return
            / recent_volatility
        )

    @staticmethod
    def _signal_score(
        normalised_signal: float,
    ) -> float:
        """
        Map a positive normalised signal to [0.5, 1.0].

        0.5 represents a zero prediction.

        Positive predictions approach 1.0 as their
        volatility-normalised magnitude increases.
        """

        if not math.isfinite(normalised_signal):
            return float("nan")

        if normalised_signal < 0.0:
            return float("nan")

        return float(
            0.5
            + 0.5 * math.tanh(
                normalised_signal
            )
        )

    def evaluate_ticker(
        self,
        ticker: str,
        asset_class: str = "stocks",
    ) -> dict[str, Any] | None:
        """
        Evaluate one ticker as a long candidate.

        A ticker must satisfy both:

        1. Historical model-quality requirements.
        2. A positive current predicted return.

        This keeps the ranking layer aligned with the
        long-only paper-trading implementation.
        """

        normalized = ticker.upper().strip()

        if not normalized:
            raise ValueError(
                "Ticker must not be empty."
            )

        metadata_path = (
            self.models_dir
            / f"{normalized}_meta.json"
        )

        if not metadata_path.exists():
            return None

        try:
            with metadata_path.open(
                "r",
                encoding="utf-8",
            ) as handle:
                metadata = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return None

        metrics = metadata.get("metrics")

        if not isinstance(metrics, dict):
            return None

        correlation = self._safe_float(
            metrics.get("correlation")
        )

        directional_accuracy = self._safe_float(
            metrics.get("directional_accuracy")
        )

        if (
            correlation is None
            or directional_accuracy is None
        ):
            return None

        if not self._is_model_eligible(
            correlation,
            directional_accuracy,
        ):
            return None

        model_quality_score = (
            self._calculate_model_quality(
                correlation,
                directional_accuracy,
            )
        )

        normalized_asset_class = (
            asset_class.lower().strip()
        )

        if not normalized_asset_class:
            raise ValueError(
                "Asset class must not be empty."
            )

        try:
            bars = self.provider.get_recent_bars(
                normalized,
                limit=self.config.bars_limit,
                asset_class=normalized_asset_class,
            )
        except Exception:
            return None

        if bars is None or bars.empty:
            return None

        if "last" not in bars.columns:
            return None

        latest_price = self._safe_float(
            pd.to_numeric(
                bars["last"],
                errors="coerce",
            ).dropna().iloc[-1]
            if not pd.to_numeric(
                bars["last"],
                errors="coerce",
            ).dropna().empty
            else None
        )

        if (
            latest_price is None
            or latest_price <= 0.0
        ):
            return None

        try:
            prediction = inference_service.predict(
                normalized,
                bars,
            )
        except Exception:
            return None

        predicted_return = self._safe_float(
            prediction.get("predicted_return")
        )

        if predicted_return is None:
            return None

        if (
            predicted_return
            < self.config.min_predicted_return
        ):
            return None

        recent_volatility = (
            self._calculate_recent_volatility(
                bars,
                self.config.volatility_window,
            )
        )

        normalised_signal = (
            self._calculate_normalised_signal(
                predicted_return,
                recent_volatility,
            )
        )

        if not math.isfinite(
            normalised_signal
        ):
            return None

        signal_score = self._signal_score(
            normalised_signal
        )

        if not math.isfinite(signal_score):
            return None

        opportunity_score = (
            self.config.quality_weight
            * model_quality_score
            + self.config.signal_weight
            * signal_score
        )

        return {
            "ticker": normalized,
            "latest_price": latest_price,
            "model_quality_score": (
                model_quality_score
            ),
            "correlation": correlation,
            "directional_accuracy": (
                directional_accuracy
            ),
            "predicted_return": predicted_return,
            "recent_volatility": (
                recent_volatility
            ),
            "normalised_signal": (
                normalised_signal
            ),
            "signal_score": signal_score,
            "opportunity_score": float(
                opportunity_score
            ),
            "direction": "long",
            "prediction_timestamp": (
                prediction.get("timestamp")
            ),
            "model_type": prediction.get(
                "model_type"
            ),
            "seq_length": prediction.get(
                "seq_length"
            ),
            "asset_class": (
                normalized_asset_class
            ),
        }

    def rank(
        self,
        top_n: int = 10,
        asset_class: str = "stocks",
    ) -> dict[str, Any]:
        """
        Rank all complete production models
        as long candidates.
        """

        if top_n <= 0:
            raise ValueError(
                "top_n must be greater than zero."
            )

        normalized_asset_class = (
            asset_class.lower().strip()
        )

        if not normalized_asset_class:
            raise ValueError(
                "Asset class must not be empty."
            )

        models = self.discover_models()

        ranking: list[dict[str, Any]] = []

        for model in models:
            result = self.evaluate_ticker(
                model["ticker"],
                asset_class=normalized_asset_class,
            )

            if result is not None:
                ranking.append(result)

        ranking.sort(
            key=lambda item: (
                item["opportunity_score"],
                item["model_quality_score"],
                item["normalised_signal"],
            ),
            reverse=True,
        )

        selected = ranking[:top_n]

        for rank, item in enumerate(
            selected,
            start=1,
        ):
            item["rank"] = rank

        return {
            "universe_size": len(models),
            "eligible_count": len(ranking),
            "selected_count": len(selected),
            "top_n": top_n,
            "asset_class": normalized_asset_class,
            "config": {
                "bars_limit": (
                    self.config.bars_limit
                ),
                "volatility_window": (
                    self.config.volatility_window
                ),
                "min_correlation": (
                    self.config.min_correlation
                ),
                "min_directional_accuracy": (
                    self.config.min_directional_accuracy
                ),
                "min_predicted_return": (
                    self.config.min_predicted_return
                ),
                "quality_weight": (
                    self.config.quality_weight
                ),
                "signal_weight": (
                    self.config.signal_weight
                ),
            },
            "ranking": selected,
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