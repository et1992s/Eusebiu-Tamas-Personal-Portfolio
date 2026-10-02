import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useTradingData, useTickers } from '../hooks/useTradingData';
import { useTradingPrediction } from '../hooks/useTradingPrediction';
import { useLiveTradingChart } from '../hooks/useLiveTradingChart';
import { useLiveTradingPrediction } from '../hooks/useLiveTradingPrediction';
import CandlestickChart from '../components/Chart/CandlestickChart';
import PredictionPanel from '../components/Trading/PredictionPanel';
import TickerSelector from '../components/Trading/TickerSelector';
import '../App.css';

// ─────────────────────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────────────────────

const DEFAULT_STRATEGY = {
  buy_threshold: 0.005,
  sell_threshold: 0.005,
  stop_loss: 0.02,
  take_profit: 0.02,
  position_size: 1000,
};

const SLIDERS = [
  { key: 'buy_threshold', label: 'Buy signal', min: 0, max: 0.05, step: 0.001 },
  { key: 'sell_threshold', label: 'Sell signal', min: 0, max: 0.05, step: 0.001 },
  { key: 'stop_loss', label: 'Stop loss', min: 0, max: 0.10, step: 0.005 },
  { key: 'take_profit', label: 'Take profit', min: 0, max: 0.10, step: 0.005 },
];

const PREFERENCES_KEY = 'zebio:trading:preferences';

// ─────────────────────────────────────────────────────────────
// Preferences persistence
// ─────────────────────────────────────────────────────────────

function loadPreferences() {
  if (typeof window === 'undefined') return {};
  try {
    const raw = window.localStorage.getItem(PREFERENCES_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function savePreferences(prefs) {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(PREFERENCES_KEY, JSON.stringify(prefs));
  } catch {
    /* storage disabled or quota exceeded — non-fatal */
  }
}

// ─────────────────────────────────────────────────────────────
// Sub-components
// ─────────────────────────────────────────────────────────────

function StrategyControls({ params, onChange, disabled }) {
  return (
    <div className="strategy-controls">
      {SLIDERS.map((slider) => (
        <label key={slider.key} className="strategy-slider">
          <span className="strategy-slider-label">
            {slider.label}
            <em>{(params[slider.key] * 100).toFixed(2)}%</em>
          </span>
          <input
            type="range"
            min={slider.min}
            max={slider.max}
            step={slider.step}
            value={params[slider.key]}
            disabled={disabled}
            onChange={(event) =>
              onChange(slider.key, parseFloat(event.target.value))
            }
          />
        </label>
      ))}

      <label className="strategy-slider">
        <span className="strategy-slider-label">
          Position size
          <em>${params.position_size}</em>
        </span>
        <input
          type="range"
          min="100"
          max="10000"
          step="100"
          value={params.position_size}
          disabled={disabled}
          onChange={(event) =>
            onChange('position_size', parseInt(event.target.value, 10))
          }
        />
      </label>
    </div>
  );
}

function PriceSummary({ ticker, bars }) {
  const last = bars.length ? bars[bars.length - 1] : null;
  const previous = bars.length > 1 ? bars[bars.length - 2] : null;

  const lastClose = last ? Number(last.close) : null;
  const previousClose = previous ? Number(previous.close) : null;

  const changePct =
    lastClose != null && previousClose != null && previousClose !== 0
      ? ((lastClose - previousClose) / previousClose) * 100
      : 0;

  const open = last ? Number(last.open) : null;
  const high = last ? Number(last.high) : null;
  const low = last ? Number(last.low) : null;
  const volume = last ? Number(last.volume) : null;

  const positive = changePct >= 0;

  const timestamp = last?.timestamp ? new Date(last.timestamp) : null;
  const formattedTimestamp =
    timestamp && !Number.isNaN(timestamp.getTime())
      ? timestamp.toLocaleTimeString([], {
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
        })
      : null;

  return (
    <div className="price-panel-wrap">
      <div className="market-stats">
        <div>
          <span>OPEN</span>
          <strong>{open != null ? `$${open.toFixed(2)}` : '—'}</strong>
        </div>
        <div>
          <span>HIGH</span>
          <strong>{high != null ? `$${high.toFixed(2)}` : '—'}</strong>
        </div>
        <div>
          <span>LOW</span>
          <strong>{low != null ? `$${low.toFixed(2)}` : '—'}</strong>
        </div>
        <div>
          <span>VOLUME</span>
          <strong>{volume != null ? volume.toLocaleString() : '—'}</strong>
        </div>
      </div>

      <div
        style={{
          display: 'flex',
          alignItems: 'baseline',
          justifyContent: 'space-between',
          padding: '14px 16px 4px',
        }}
      >
        <div>
          <div
            style={{
              fontSize: 22,
              fontWeight: 700,
              letterSpacing: '-0.02em',
            }}
          >
            {ticker}
          </div>

          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 7,
              fontSize: 9,
              color: 'var(--z-muted)',
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              marginTop: 4,
            }}
          >
            <span
              style={{
                width: 6,
                height: 6,
                borderRadius: '50%',
                background: 'var(--z-accent)',
                display: 'inline-block',
              }}
            />
            LIVE ALPACA
          </div>

          {formattedTimestamp && (
            <div
              style={{
                fontSize: 9,
                color: 'var(--z-muted)',
                marginTop: 3,
              }}
            >
              {formattedTimestamp}
            </div>
          )}
        </div>

        <div style={{ textAlign: 'right' }}>
          <div
            style={{
              fontSize: 26,
              fontWeight: 700,
              letterSpacing: '-0.02em',
            }}
          >
            {lastClose != null ? `$${lastClose.toFixed(2)}` : '—'}
          </div>

          <div
            style={{
              fontSize: 11,
              color: positive ? 'var(--z-accent)' : 'var(--z-danger)',
              fontWeight: 600,
            }}
          >
            {positive ? '+' : ''}
            {changePct.toFixed(2)}%
          </div>
        </div>
      </div>

      <div
        style={{
          padding: '4px 16px 10px',
          fontSize: 9,
          color: 'var(--z-muted)',
          letterSpacing: '0.06em',
          textTransform: 'uppercase',
        }}
      >
        {bars.length} live bars • Alpaca market feed
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Normalisation helpers
// ─────────────────────────────────────────────────────────────

function extractBars(hookResult) {
  if (!hookResult) return [];
  if (Array.isArray(hookResult.bars)) return hookResult.bars;
  if (Array.isArray(hookResult.data?.data)) return hookResult.data.data;
  if (Array.isArray(hookResult.data?.bars)) return hookResult.data.bars;
  if (Array.isArray(hookResult.data)) return hookResult.data;
  return [];
}

function extractTickerStrings(rawList) {
  if (!Array.isArray(rawList)) return [];
  return rawList
    .map((item) => {
      if (typeof item === 'string') return item;
      if (typeof item?.symbol === 'string') return item.symbol;
      if (typeof item?.ticker === 'string') return item.ticker;
      return '';
    })
    .filter(Boolean);
}

// ─────────────────────────────────────────────────────────────
// Main Page
// ─────────────────────────────────────────────────────────────

function StrategyOverlay({ lines }) {
  if (!lines) return null;

  const {
    entry,
    stopLoss,
    takeProfitModel,
    takeProfitUser,
    stopLossPct,
    takeProfitPct,
    predictedReturn,
    buyThreshold,
    sellThreshold,
    positionSize,
    model,
    signal,
  } = lines;

  const fmtPrice = (n) => `$${n.toFixed(2)}`;
  const fmtPct = (n) => `${n >= 0 ? '+' : ''}${(n * 100).toFixed(3)}%`;
  const fmtSigned = (n) => `${n >= 0 ? '+' : '−'}$${Math.abs(n).toFixed(2)}`;

  // ── No-signal state ────────────────────────────────────────
  if (signal === 'NONE') {
    const reason =
      predictedReturn > 0
        ? 'below buy threshold'
        : predictedReturn < 0
          ? 'negative prediction'
          : 'neutral prediction';

    return (
      <div className="strategy-overlay strategy-overlay-idle">
        <div className="strategy-overlay-header">
          <span className="strategy-overlay-kicker strategy-overlay-kicker-idle">
            NO SIGNAL
          </span>
          <span className="strategy-overlay-model">{model}</span>
        </div>
        <div className="strategy-overlay-grid">
          <div className="strategy-overlay-row">
            <span className="strategy-overlay-label">Predicted return</span>
            <span
              className={
                predictedReturn >= 0
                  ? 'strategy-positive'
                  : 'strategy-negative'
              }
            >
              {fmtPct(predictedReturn)}
            </span>
          </div>
          <div className="strategy-overlay-row">
            <span className="strategy-overlay-label">Buy threshold</span>
            <span>{fmtPct(buyThreshold)}</span>
          </div>
          <div className="strategy-overlay-row">
            <span className="strategy-overlay-label">Sell threshold</span>
            <span>−{fmtPct(-(-sellThreshold)).replace('+', '')}</span>
          </div>
        </div>
        <div className="strategy-overlay-footer">
          <div style={{ width: '100%' }}>
            <span>Why no trade</span>
            <strong style={{ textTransform: 'none', fontSize: 11 }}>
              Model output is {reason}. Lower the buy threshold or wait for a
              stronger signal.
            </strong>
          </div>
        </div>
      </div>
    );
  }

  // ── Signal state (BUY / SELL) ─────────────────────────────
  const isBuy = signal === 'BUY';
  const modelMove = isBuy ? predictedReturn : -predictedReturn;
  const lossDollar = -positionSize * stopLossPct;
  const profitModelDollar  = positionSize * modelMove;
  const profitUserDollar = positionSize * takeProfitPct;
  const rrModel = stopLossPct > 0 ? Math.abs(modelMove) / stopLossPct : 0;
  const rrUser = stopLossPct > 0 ? takeProfitPct / stopLossPct : 0;

  const showUserTarget = Math.abs(takeProfitUser - takeProfitModel) > 0.01;

  return (
    <div
      className={`strategy-overlay ${
        isBuy ? 'strategy-overlay-buy' : 'strategy-overlay-sell'
      }`}
    >
      <div className="strategy-overlay-header">
        <span
          className={`strategy-overlay-kicker ${
            isBuy ? 'strategy-positive' : 'strategy-negative'
          }`}
        >
          {signal} SIGNAL
        </span>
        <span className="strategy-overlay-model">{model}</span>
      </div>

      <div className="strategy-overlay-grid">
        <div className="strategy-overlay-row">
          <span className="strategy-overlay-label">Predicted return</span>
          <span
            className={
              predictedReturn >= 0 ? 'strategy-positive' : 'strategy-negative'
            }
          >
            {fmtPct(predictedReturn)}
          </span>
        </div>

        <div className="strategy-overlay-row">
          <span className="strategy-overlay-label">Entry</span>
          <span className="strategy-overlay-value">{fmtPrice(entry)}</span>
        </div>

        <div className="strategy-overlay-row">
          <span className="strategy-overlay-label strategy-negative">
            Stop loss
          </span>
          <span className="strategy-overlay-value">
            {fmtPrice(stopLoss)}
            <em> {fmtPct(-stopLossPct)} · {fmtSigned(lossDollar)}</em>
          </span>
        </div>

        <div className="strategy-overlay-row">
          <span className="strategy-overlay-label strategy-positive">
            TP (model)
          </span>
          <span className="strategy-overlay-value">
            {fmtPrice(takeProfitModel)}
            <em>
              {' '}
              {fmtPct(predictedReturn)} · {fmtSigned(profitModelDollar)}
            </em>
          </span>
        </div>

        {showUserTarget && (
          <div className="strategy-overlay-row">
            <span className="strategy-overlay-label">TP (your target)</span>
            <span className="strategy-overlay-value">
              {fmtPrice(takeProfitUser)}
              <em>
                {' '}
                {fmtPct(takeProfitPct)} · {fmtSigned(profitUserDollar)}
              </em>
            </span>
          </div>
        )}
      </div>

      <div className="strategy-overlay-footer">
        <div>
          <span>R:R (model)</span>
          <strong>1 : {rrModel.toFixed(2)}</strong>
        </div>
        <div>
          <span>R:R (your target)</span>
          <strong>1 : {rrUser.toFixed(2)}</strong>
        </div>
        <div>
          <span>Position</span>
          <strong>${positionSize.toLocaleString()}</strong>
        </div>
      </div>
    </div>
  );
}

function TradingProjectPage() {
  // Read stored preferences once per mount
  const initialPrefs = useMemo(() => loadPreferences(), []);

  // --- UI state (all hydrated from localStorage if present) ---
  const [selectedTicker, setSelectedTicker] = useState(
    initialPrefs.selectedTicker ?? 'AAPL',
  );
  const [barLimit, setBarLimit] = useState(initialPrefs.barLimit ?? 200);
  const [strategyParams, setStrategyParams] = useState(
    initialPrefs.strategyParams ?? DEFAULT_STRATEGY,
  );

  const [backtestResult, setBacktestResult] = useState(null);
  const [backtestLoading, setBacktestLoading] = useState(false);
  const [backtestError, setBacktestError] = useState('');

  const [chartTimeframe, setChartTimeframe] = useState(
    initialPrefs.chartTimeframe ?? '1m',
  );
  const [assetClass, setAssetClass] = useState(
    initialPrefs.assetClass ?? 'stocks',
  );
  const [chartType, setChartType] = useState(
    initialPrefs.chartType ?? 'candlestick',
  );
  const [selectedIndicators, setSelectedIndicators] = useState(
    initialPrefs.selectedIndicators ?? ['sma20'],
  );
  const [showVolume, setShowVolume] = useState(
    initialPrefs.showVolume ?? true,
  );
  const [logScale, setLogScale] = useState(initialPrefs.logScale ?? false);
  const [showStrategyLines, setShowStrategyLines] = useState(
    initialPrefs.showStrategyLines ?? true,
  );

  const backtestTimerRef = useRef(null);

  // --- Persist preferences on any change ---
  useEffect(() => {
    savePreferences({
      selectedTicker,
      barLimit,
      strategyParams,
      chartTimeframe,
      assetClass,
      chartType,
      selectedIndicators,
      showVolume,
      logScale,
      showStrategyLines,
    });
  }, [
    selectedTicker,
    barLimit,
    strategyParams,
    chartTimeframe,
    assetClass,
    chartType,
    selectedIndicators,
    showVolume,
    logScale,
    showStrategyLines,
  ]);

  // --- Data hooks ---
  const tickerHook = useTickers(assetClass);
  const tradingHook = useTradingData(selectedTicker, barLimit, assetClass);
  const predictionHook = useTradingPrediction(selectedTicker, barLimit);
  const livePredictionHook = useLiveTradingPrediction(selectedTicker, assetClass);
  const liveChartHook = useLiveTradingChart(
    selectedTicker,
    chartTimeframe,
    assetClass,
  );

  // --- Extract data ---
  const historicalBars = useMemo(() => extractBars(tradingHook), [tradingHook]);
  const liveChartBars = liveChartHook?.bars ?? [];
  const liveChartLoading = liveChartHook?.loading ?? false;
  const liveChartError = liveChartHook?.error ?? '';
  const liveConnected = livePredictionHook?.connected ?? false;
  const livePrediction = livePredictionHook?.prediction ?? null;
  const livePredictionError = livePredictionHook?.error ?? '';
  const liveBars = livePredictionHook?.bars ?? [];

  const tickers = useMemo(
    () => extractTickerStrings(tickerHook?.tickers),
    [tickerHook],
  );
  const tickersLoading = tickerHook?.loading ?? false;
  const historicalError = tradingHook?.error ?? '';
  const prediction = predictionHook?.prediction ?? null;
  const predictionLoading = predictionHook?.loading ?? false;
  const predictionError = predictionHook?.error ?? '';

  // --- Handlers ---
  const handleParamChange = (key, value) => {
    setStrategyParams((previous) => ({ ...previous, [key]: value }));
  };

  const handleIndicatorChange = (e) => {
    const values = Array.from(
      e.target.selectedOptions,
      (option) => option.value,
    );
    setSelectedIndicators(values);
  };

  const handleAssetClassChange = (nextClass) => {
    setAssetClass(nextClass);
    // Reset to a sensible default for the new asset class
    if (nextClass === 'crypto') setSelectedTicker('BTC/USD');
    else if (nextClass === 'etf') setSelectedTicker('SPY');
    else setSelectedTicker('AAPL');
  };

  // --- Calculated indicators (SMA / EMA / VWAP) ---
  const calculatedIndicators = useMemo(() => {
    const indicators = [];
    if (!liveChartBars || liveChartBars.length === 0) return indicators;

    const calculateSMA = (period) => {
      return liveChartBars
        .map((bar, index) => {
          if (index < period - 1) return null;
          const sum = liveChartBars
            .slice(index - period + 1, index + 1)
            .reduce((acc, b) => acc + b.close, 0);
          const time = new Date(bar.timestamp).getTime() / 1000;
          if (!Number.isFinite(time)) return null;
          return { time, value: sum / period };
        })
        .filter(Boolean);
    };

    const calculateEMA = (period) => {
      const emaData = [];
      const k = 2 / (period + 1);
      let prevEma = null;
      liveChartBars.forEach((bar, index) => {
        const time = new Date(bar.timestamp).getTime() / 1000;
        if (!Number.isFinite(time)) return;
        if (index === 0) {
          prevEma = bar.close;
          emaData.push({ time, value: prevEma });
        } else {
          const ema = (bar.close - prevEma) * k + prevEma;
          emaData.push({ time, value: ema });
          prevEma = ema;
        }
      });
      return emaData;
    };

    /**
     * Session-anchored VWAP.
     * Resets at the start of each UTC calendar day (standard for 24/7 crypto,
     * correct for regular-session equities).
     * Uses typical price = (H + L + C) / 3.
     */
    const calculateVWAP = () => {
      const result = [];
      let cumPV = 0;
      let cumV = 0;
      let lastSessionDate = null;

      liveChartBars.forEach((bar) => {
        const time = new Date(bar.timestamp).getTime() / 1000;
        if (!Number.isFinite(time)) return;

        const sessionDate = new Date(bar.timestamp).toISOString().slice(0, 10);
        if (sessionDate !== lastSessionDate) {
          cumPV = 0;
          cumV = 0;
          lastSessionDate = sessionDate;
        }

        const high = Number(bar.high);
        const low = Number(bar.low);
        const close = Number(bar.close);
        const volume = Number(bar.volume) || 0;

        if (
          !Number.isFinite(high) ||
          !Number.isFinite(low) ||
          !Number.isFinite(close)
        ) {
          return;
        }

        const typical = (high + low + close) / 3;
        cumPV += typical * volume;
        cumV += volume;

        if (cumV > 0) {
          result.push({ time, value: cumPV / cumV });
        }
      });

      return result;
    };

    if (selectedIndicators.includes('sma20'))
      indicators.push({
        name: 'SMA 20',
        data: calculateSMA(20),
        color: '#3b82f6',
      });
    if (selectedIndicators.includes('sma50'))
      indicators.push({
        name: 'SMA 50',
        data: calculateSMA(50),
        color: '#f59e0b',
      });
    if (selectedIndicators.includes('ema200'))
      indicators.push({
        name: 'EMA 200',
        data: calculateEMA(200),
        color: '#8b5cf6',
      });
    if (selectedIndicators.includes('vwap'))
      indicators.push({
        name: 'VWAP',
        data: calculateVWAP(),
        color: '#ec4899',
      });

    return indicators;
  }, [liveChartBars, selectedIndicators]);

  // --- Strategy markers (prediction -> arrows) ---
  const strategyMarkers = useMemo(() => {
    if (!livePrediction || liveChartBars.length === 0) return [];

    const lastBar = liveChartBars[liveChartBars.length - 1];
    const predictedReturn = livePrediction.predicted_return;
    const time = new Date(lastBar.timestamp).getTime() / 1000;
    if (!Number.isFinite(time)) return [];

    const markers = [];

    if (predictedReturn > strategyParams.buy_threshold) {
      markers.push({
        time,
        position: 'belowBar',
        color: '#22c55e',
        shape: 'arrowUp',
        text: `BUY (${(predictedReturn * 100).toFixed(3)}%)`,
      });
    } else if (predictedReturn < -strategyParams.sell_threshold) {
      markers.push({
        time,
        position: 'aboveBar',
        color: '#ef4444',
        shape: 'arrowDown',
        text: `SELL (${(predictedReturn * 100).toFixed(3)}%)`,
      });
    }

    return markers;
  }, [livePrediction, liveChartBars, strategyParams]);

  const strategyLines = useMemo(() => {
    if (!showStrategyLines) return null;
    if (!livePrediction) return null;
    if (liveChartBars.length === 0) return null;

    const predictedReturn = Number(livePrediction.predicted_return);
    if (!Number.isFinite(predictedReturn)) return null;

    const lastClose = Number(liveChartBars[liveChartBars.length - 1]?.close);
    if (!Number.isFinite(lastClose) || lastClose <= 0) return null;

    const buyThreshold = strategyParams.buy_threshold;
    const sellThreshold = -strategyParams.sell_threshold;

    const hasBuySignal = predictedReturn > buyThreshold;
    const hasSellSignal = predictedReturn < sellThreshold;
    const signal = hasBuySignal ? 'BUY' : hasSellSignal ? 'SELL' : 'NONE';

    const slPct = strategyParams.stop_loss;
    const tpPct = strategyParams.take_profit;

    // Direction-aware price levels
    let stopLoss, takeProfitUser, takeProfitModel;
    if (signal === 'BUY') {
      stopLoss       = lastClose * (1 - slPct);
      takeProfitUser = lastClose * (1 + tpPct);
      takeProfitModel = lastClose * (1 + predictedReturn);
    } else if (signal === 'SELL') {
      // For a short: SL above, TP below
      stopLoss       = lastClose * (1 + slPct);
      takeProfitUser = lastClose * (1 - tpPct);
      // A negative prediction means price expected to fall → TP below entry
      takeProfitModel = lastClose * (1 + predictedReturn);
    } else {
      // NONE — not used, but avoid NaN downstream
      stopLoss = lastClose;
      takeProfitUser = lastClose;
      takeProfitModel = lastClose;
    }

    return {
      entry: lastClose,
      predictedReturn,
      buyThreshold,
      sellThreshold,
      stopLossPct: slPct,
      takeProfitPct: tpPct,
      positionSize: strategyParams.position_size,
      model: livePrediction.model_type || 'CNN-BiLSTM-LSTM',

      signal,
      hasBuySignal,
      hasSellSignal,

      stopLoss,
      takeProfitUser,
      takeProfitModel,
    };
  }, [liveChartBars, strategyParams, showStrategyLines, livePrediction]);

  // --- Backtest effect ---
  useEffect(() => {
    if (!historicalBars.length) return undefined;

    clearTimeout(backtestTimerRef.current);
    backtestTimerRef.current = setTimeout(async () => {
      setBacktestLoading(true);
      setBacktestError('');

      try {
        const response = await fetch('/api/v1/trading/backtest', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            ticker: selectedTicker,
            limit: barLimit,
            ...strategyParams,
          }),
        });

        const raw = await response.text();
        let json = {};
        try {
          json = raw ? JSON.parse(raw) : {};
        } catch {
          throw new Error('Backtest returned an invalid JSON response.');
        }

        if (!response.ok) {
          throw new Error(
            json.detail ||
              json.message ||
              `Backtest failed with HTTP ${response.status}`,
          );
        }

        setBacktestResult(json);
      } catch (error) {
        setBacktestError(error.message || 'Backtest failed.');
        setBacktestResult(null);
      } finally {
        setBacktestLoading(false);
      }
    }, 300);

    return () => clearTimeout(backtestTimerRef.current);
  }, [selectedTicker, barLimit, strategyParams, historicalBars.length]);

  const statusLabel = liveConnected
    ? 'LIVE'
    : livePredictionError
      ? 'ERROR'
      : 'CONNECTING';

  return (
    <section className="trading-page">
      <aside className="market-column">
        <div className="panel market-panel">

          {/* ── Header ─────────────────────────────────────── */}
          <div className="panel-header">
            <div className="panel-title-group">
              <div className="section-icon market-icon">⌁</div>
              <div>
                <h2>Market Lab</h2>
                <p>Live market intelligence</p>
              </div>
            </div>

            <span className="live-label">
              <span />
              {liveConnected ? 'LIVE' : 'CONNECTING'}
            </span>
          </div>

          {/* ── Market controls ────────────────────────────── */}
          <div className="market-controls">
            <TickerSelector
              tickers={tickers}
              selectedTicker={selectedTicker}
              onSelect={setSelectedTicker}
              loading={tickersLoading}
            />

            <label className="bars-control">
              <span>Asset Class</span>
              <select
                value={assetClass}
                onChange={(e) => handleAssetClassChange(e.target.value)}
              >
                <option value="stocks">Stocks</option>
                <option value="etf">ETFs</option>
                <option value="crypto">Crypto</option>
              </select>
            </label>

            <label className="bars-control">
              <span>Chart timeframe</span>
              <select
                value={chartTimeframe}
                onChange={(event) => setChartTimeframe(event.target.value)}
              >
                <option value="1m">1 minute</option>
                <option value="5m">5 minutes</option>
                <option value="15m">15 minutes</option>
                <option value="30m">30 minutes</option>
                <option value="1h">1 hour</option>
                <option value="4h">4 hours</option>
                <option value="1D">1 day</option>
              </select>
            </label>

            <label className="bars-control">
              <span>Chart Type</span>
              <select
                value={chartType}
                onChange={(e) => setChartType(e.target.value)}
              >
                <option value="candlestick">Candlesticks</option>
                <option value="line">Line</option>
                <option value="area">Mountain (Area)</option>
              </select>
            </label>

            <label className="bars-control">
              <span>Indicators (Ctrl+Click)</span>
              <select
                multiple
                value={selectedIndicators}
                onChange={handleIndicatorChange}
                style={{ height: '60px' }}
              >
                <option value="sma20">SMA 20</option>
                <option value="sma50">SMA 50</option>
                <option value="ema200">EMA 200</option>
                <option value="vwap">VWAP</option>
              </select>
            </label>

            <label
              className="bars-control"
              style={{
                flexDirection: 'row',
                alignItems: 'center',
                gap: 8,
                cursor: 'pointer',
              }}
            >
              <input
                type="checkbox"
                checked={showVolume}
                onChange={(e) => setShowVolume(e.target.checked)}
              />
              <span>Volume</span>
            </label>

            <label
              className="bars-control"
              style={{
                flexDirection: 'row',
                alignItems: 'center',
                gap: 8,
                cursor: 'pointer',
              }}
            >
              <input
                type="checkbox"
                checked={logScale}
                onChange={(e) => setLogScale(e.target.checked)}
              />
              <span>Log scale</span>
            </label>

            <label
              className="bars-control"
              style={{
                flexDirection: 'row',
                alignItems: 'center',
                gap: 8,
                cursor: 'pointer',
              }}
            >
              <input
                type="checkbox"
                checked={showStrategyLines}
                onChange={(e) => setShowStrategyLines(e.target.checked)}
              />
              <span>SL / TP</span>
            </label>

            <label className="bars-control">
              <span>Backtest bars</span>
              <select
                value={barLimit}
                onChange={(event) => setBarLimit(Number(event.target.value))}
              >
                <option value={100}>100</option>
                <option value={200}>200</option>
                <option value={500}>500</option>
                <option value={1000}>1000</option>
              </select>
            </label>
          </div>

          {/* ── Live market status ─────────────────────────── */}
          <div className="market-stats">
            <div>
              <span>SYMBOL</span>
              <strong>{selectedTicker}</strong>
            </div>
            <div>
              <span>LIVE BARS</span>
              <strong>{liveBars.length || '—'}</strong>
            </div>
            <div>
              <span>STATUS</span>
              <strong
                className={liveConnected ? 'positive-value' : 'muted-value'}
              >
                {statusLabel}
              </strong>
            </div>
          </div>

          {/* ── Strategy controls ──────────────────────────── */}
          <StrategyControls
            params={strategyParams}
            onChange={handleParamChange}
            disabled={!historicalBars.length}
          />

          {/* ── Backtest result ────────────────────────────── */}
          {backtestResult && (
            <div className="market-stats">
              <div>
                <span>TRADES</span>
                <strong>{backtestResult.trade_count}</strong>
              </div>
              <div>
                <span>WIN RATE</span>
                <strong>
                  {(backtestResult.win_rate * 100).toFixed(1)}%
                </strong>
              </div>
              <div>
                <span>RETURN</span>
                <strong
                  className={
                    backtestResult.total_return >= 0
                      ? 'positive-value'
                      : 'negative-value'
                  }
                >
                  {(backtestResult.total_return_pct * 100).toFixed(2)}%
                </strong>
              </div>
            </div>
          )}

          {/* ── Errors ─────────────────────────────────────── */}
          {historicalError && (
            <div className="market-error">
              <strong>Backtest data unavailable</strong>
              <span>{historicalError}</span>
            </div>
          )}

          {backtestError && !historicalError && (
            <div className="market-error">
              <strong>Backtest unavailable</strong>
              <span>{backtestError}</span>
            </div>
          )}

          {livePredictionError && (
            <div className="market-error">
              <strong>Live prediction unavailable</strong>
              <span>{livePredictionError}</span>
            </div>
          )}

          {/* ── Live price summary ─────────────────────────── */}
          {liveChartBars.length > 0 && (
            <PriceSummary ticker={selectedTicker} bars={liveChartBars} />
          )}

          {/* ── Prediction panel ───────────────────────────── */}
          <PredictionPanel
            prediction={prediction}
            loading={predictionLoading}
            error={predictionError}
            livePrediction={livePrediction}
            liveConnected={liveConnected}
            liveError={livePredictionError}
          />

          {/* ── Strategy overlay (only shows when model says BUY) ── */}
          <StrategyOverlay lines={strategyLines} />

          {/* ── Live chart ─────────────────────────────────── */}
          <div className="chart-wrap">
            {liveChartBars.length > 0 ? (
              <CandlestickChart
                data={liveChartBars}
                height={390}
                chartType={chartType}
                indicators={calculatedIndicators}
                markers={strategyMarkers}
                showVolume={showVolume}
                logScale={logScale}
                strategyLines={strategyLines}
              />
            ) : (
              <div className="chart-placeholder">
                {liveChartError ? (
                  <span>Live chart data unavailable: {liveChartError}</span>
                ) : liveChartLoading ? (
                  <>
                    <div className="loader-ring" />
                    <span>Loading live {selectedTicker} market data…</span>
                  </>
                ) : (
                  <span>
                    Waiting for live {selectedTicker} market data…
                  </span>
                )}
              </div>
            )}
          </div>

          {/* ── Footer ─────────────────────────────────────── */}
          <div className="market-footer">
            <span>ALPACA LIVE DATA</span>
            <span className="pipeline-state">
              <i />
              {liveConnected
                ? 'LIVE STREAM'
                : backtestLoading
                  ? 'BACKTEST RUNNING'
                  : 'CONNECTING'}
            </span>
          </div>

        </div>
      </aside>
    </section>
  );
}

export default TradingProjectPage;