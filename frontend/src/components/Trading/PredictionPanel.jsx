import React from 'react';

function formatPrediction(value) {
  const numericValue = Number(value);

  if (!Number.isFinite(numericValue)) {
    return '—';
  }

  return `${(numericValue * 100).toFixed(5)}%`;
}

function formatTimestamp(timestamp) {
  if (!timestamp) {
    return '—';
  }

  const date = new Date(timestamp);

  if (Number.isNaN(date.getTime())) {
    return timestamp;
  }

  return date.toLocaleString();
}

function PredictionPanel({
  prediction,
  loading,
  error,
  livePrediction = null,
  liveConnected = false,
  liveError = '',
}) {
  const activePrediction = livePrediction || prediction;
  const isLive = Boolean(livePrediction);

  if (loading && !isLive) {
    return (
      <div className="prediction-panel">
        <div className="prediction-panel-header">
          <div>
            <span className="prediction-kicker">MACHINE LEARNING</span>
            <h3>Prediction</h3>
          </div>
          <span className="prediction-status">RUNNING</span>
        </div>

        <div className="prediction-loading">
          <div className="loader-ring" />
          <span>Running model inference…</span>
        </div>
      </div>
    );
  }

  if (error && !isLive) {
    return (
      <div className="prediction-panel">
        <div className="prediction-panel-header">
          <div>
            <span className="prediction-kicker">MACHINE LEARNING</span>
            <h3>Prediction</h3>
          </div>
          <span className="prediction-status prediction-status-error">
            ERROR
          </span>
        </div>

        <div className="prediction-error">
          <strong>Prediction unavailable</strong>
          <span>{error}</span>
        </div>
      </div>
    );
  }

  if (!activePrediction) {
    return (
      <div className="prediction-panel">
        <div className="prediction-panel-header">
          <div>
            <span className="prediction-kicker">MACHINE LEARNING</span>
            <h3>Prediction</h3>
          </div>

          <span
            className={
              liveConnected
                ? 'prediction-status'
                : 'prediction-status prediction-status-error'
            }
          >
            {liveConnected ? 'LIVE CONNECTED' : 'WAITING'}
          </span>
        </div>

        <div className="prediction-empty">
          {liveError || 'No prediction available.'}
        </div>
      </div>
    );
  }

  const predictedReturn = Number(
    activePrediction.predicted_return,
  );

  const positive = Number.isFinite(predictedReturn)
    ? predictedReturn >= 0
    : null;

  return (
    <div className="prediction-panel">
      <div className="prediction-panel-header">
        <div>
          <span className="prediction-kicker">
            {isLive ? 'LIVE MACHINE LEARNING' : 'MACHINE LEARNING'}
          </span>

          <h3>
            {activePrediction.ticker} Prediction
          </h3>
        </div>

        <span className="prediction-status">
          {isLive
            ? liveConnected
              ? 'LIVE'
              : 'DISCONNECTED'
            : 'INFERENCE READY'}
        </span>
      </div>

      <div className="prediction-main">
        <div>
          <span className="prediction-label">
            PREDICTED RETURN
          </span>

          <strong
            className={
              positive === null
                ? ''
                : positive
                  ? 'prediction-positive'
                  : 'prediction-negative'
            }
          >
            {formatPrediction(predictedReturn)}
          </strong>

          <span className="prediction-target">
            {activePrediction.target || 'forward return'}
          </span>
        </div>

        <div className="prediction-meta">
          <div>
            <span>SOURCE</span>
            <strong>
              {isLive ? 'ALPACA LIVE' : 'HISTORICAL'}
            </strong>
          </div>

          <div>
            <span>MODEL</span>
            <strong>
              {activePrediction.model_type || '—'}
            </strong>
          </div>

          <div>
            <span>SEQUENCE</span>
            <strong>
              {activePrediction.seq_length != null
                ? `${activePrediction.seq_length} bars`
                : '—'}
            </strong>
          </div>

          <div>
            <span>FEATURES</span>
            <strong>
              {Array.isArray(activePrediction.features)
                ? activePrediction.features.length
                : '—'}
            </strong>
          </div>

          <div>
            <span>INFERENCE TIME</span>
            <strong>
              {formatTimestamp(
                activePrediction.timestamp,
              )}
            </strong>
          </div>
        </div>
      </div>

      {liveError && isLive && (
        <div className="prediction-error">
          <span>{liveError}</span>
        </div>
      )}
    </div>
  );
}

export default PredictionPanel;
