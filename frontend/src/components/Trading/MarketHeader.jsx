import React, { useMemo } from 'react';

function formatPrice(value) {
  const numericValue = Number(value);

  if (!Number.isFinite(numericValue)) {
    return '—';
  }

  return `$${numericValue.toFixed(2)}`;
}

function formatPercent(value) {
  const numericValue = Number(value);

  if (!Number.isFinite(numericValue)) {
    return '—';
  }

  return `${numericValue >= 0 ? '+' : ''}${numericValue.toFixed(2)}%`;
}

function formatVolume(value) {
  const numericValue = Number(value);

  if (!Number.isFinite(numericValue)) {
    return '—';
  }

  if (numericValue >= 1_000_000_000) {
    return `${(numericValue / 1_000_000_000).toFixed(2)}B`;
  }

  if (numericValue >= 1_000_000) {
    return `${(numericValue / 1_000_000).toFixed(2)}M`;
  }

  if (numericValue >= 1_000) {
    return `${(numericValue / 1_000).toFixed(1)}K`;
  }

  return numericValue.toLocaleString();
}

function getTickerName(ticker) {
  const names = {
    AAPL: 'Apple Inc.',
    AMZN: 'Amazon.com Inc.',
    GOOGL: 'Alphabet Inc.',
    META: 'Meta Platforms Inc.',
    MSFT: 'Microsoft Corp.',
    NVDA: 'NVIDIA Corp.',
    TSLA: 'Tesla Inc.',
    SPY: 'SPDR S&P 500 ETF',
    QQQ: 'Invesco QQQ Trust',
    BTC: 'Bitcoin',
    'BTC/USD': 'Bitcoin',
  };

  return names[ticker] || ticker;
}

function MarketHeader({
  ticker,
  bars = [],
  connected = false,
  loading = false,
  source = null,
}) {
  const market = useMemo(() => {
    if (!Array.isArray(bars) || bars.length === 0) {
      return null;
    }

    const lastBar = bars[bars.length - 1];
    const previousBar =
      bars.length > 1 ? bars[bars.length - 2] : null;

    const close = Number(lastBar?.close);
    const previousClose = Number(previousBar?.close);

    const change =
      Number.isFinite(close) &&
      Number.isFinite(previousClose) &&
      previousClose !== 0
        ? ((close - previousClose) / previousClose) * 100
        : null;

    return {
      close,
      change,
      open: Number(lastBar?.open),
      high: Number(lastBar?.high),
      low: Number(lastBar?.low),
      volume: Number(lastBar?.volume),
      timestamp: lastBar?.timestamp || null,
    };
  }, [bars]);

  const isLive = connected || source === 'alpaca';
  const statusLabel = loading
    ? 'LOADING'
    : isLive
      ? 'LIVE'
      : 'LAST SESSION';

  const statusClass = loading
    ? 'market-status market-status-loading'
    : isLive
      ? 'market-status market-status-live'
      : 'market-status';

  return (
    <section className="market-header">
      <div className="market-header-main">
        <div className="market-identity">
          <div className="market-symbol-row">
            <h1>{ticker || '—'}</h1>

            <span className={statusClass}>
              <span className="market-status-dot" />
              {statusLabel}
            </span>
          </div>

          <span className="market-company">
            {getTickerName(ticker)}
          </span>
        </div>

        <div className="market-price">
          <strong>
            {market ? formatPrice(market.close) : '—'}
          </strong>

          <span
            className={
              market?.change == null
                ? 'market-change'
                : market.change >= 0
                  ? 'market-change market-change-positive'
                  : 'market-change market-change-negative'
            }
          >
            {market ? formatPercent(market.change) : '—'}
          </span>
        </div>
      </div>

      <div className="market-metrics">
        <div className="market-metric">
          <span>OPEN</span>
          <strong>
            {market ? formatPrice(market.open) : '—'}
          </strong>
        </div>

        <div className="market-metric">
          <span>HIGH</span>
          <strong>
            {market ? formatPrice(market.high) : '—'}
          </strong>
        </div>

        <div className="market-metric">
          <span>LOW</span>
          <strong>
            {market ? formatPrice(market.low) : '—'}
          </strong>
        </div>

        <div className="market-metric">
          <span>CLOSE</span>
          <strong>
            {market ? formatPrice(market.close) : '—'}
          </strong>
        </div>

        <div className="market-metric">
          <span>VOLUME</span>
          <strong>
            {market ? formatVolume(market.volume) : '—'}
          </strong>
        </div>
      </div>
    </section>
  );
}

export default MarketHeader;