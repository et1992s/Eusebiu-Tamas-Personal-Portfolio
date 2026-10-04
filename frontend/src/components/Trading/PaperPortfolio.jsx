import React from 'react';

function formatMoney(value, currency = 'GBP') {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return '—';

  const symbol = currency === 'GBP' ? '£' : '$';
  return `${symbol}${numeric.toLocaleString('en-GB', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function formatPct(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return '—';
  const sign = numeric >= 0 ? '+' : '';
  return `${sign}${(numeric * 100).toFixed(2)}%`;
}

function formatSignedMoney(value, currency = 'GBP') {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return '—';
  const symbol = currency === 'GBP' ? '£' : '$';
  const sign = numeric >= 0 ? '+' : '−';
  return `${sign}${symbol}${Math.abs(numeric).toLocaleString('en-GB', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function PaperPortfolio({
  portfolio,
  loading = false,
  error = '',
  lastUpdate = null,
}) {
  if (loading && !portfolio) {
    return (
      <div className="paper-portfolio paper-portfolio-loading">
        <div className="loader-ring" />
        <span>Loading persisted portfolio…</span>
      </div>
    );
  }

  if (error && !portfolio) {
    return (
      <div className="paper-portfolio paper-portfolio-error">
        <strong>Paper portfolio unavailable</strong>
        <span>{error}</span>
      </div>
    );
  }

  if (!portfolio) return null;

  const {
    currency,
    initial_capital,
    cash,
    equity,
    cumulative_pnl,
    cumulative_pnl_pct,
    starting_date,
    trade_count,
    open_positions,
  } = portfolio;

  const positive = cumulative_pnl >= 0;
  const openCount = Array.isArray(open_positions)
    ? open_positions.length
    : 0;

  return (
    <div className="paper-portfolio">
      <div className="paper-portfolio-headline">
        <div>
          <span className="paper-portfolio-kicker">
            PAPER PORTFOLIO · {currency}
          </span>
          <strong
            className={
              positive
                ? 'paper-portfolio-equity positive-value'
                : 'paper-portfolio-equity negative-value'
            }
          >
            {formatMoney(equity, currency)}
          </strong>
          <span
            className={
              positive
                ? 'paper-portfolio-change positive-value'
                : 'paper-portfolio-change negative-value'
            }
          >
            {formatSignedMoney(cumulative_pnl, currency)} ({formatPct(cumulative_pnl_pct)})
          </span>
        </div>

        <div className="paper-portfolio-meta">
          <div>
            <span>Since</span>
            <strong>{starting_date}</strong>
          </div>
          <div>
            <span>Trades</span>
            <strong>{trade_count ?? 0}</strong>
          </div>
          <div>
            <span>Open</span>
            <strong>{openCount}</strong>
          </div>
        </div>
      </div>

      <div className="paper-portfolio-metrics">
        <div>
          <span>INITIAL CAPITAL</span>
          <strong>{formatMoney(initial_capital, currency)}</strong>
        </div>
        <div>
          <span>AVAILABLE CASH</span>
          <strong>{formatMoney(cash, currency)}</strong>
        </div>
        <div>
          <span>CUMULATIVE P/L</span>
          <strong className={positive ? 'positive-value' : 'negative-value'}>
            {formatSignedMoney(cumulative_pnl, currency)}
          </strong>
        </div>
        <div>
          <span>RETURN</span>
          <strong className={positive ? 'positive-value' : 'negative-value'}>
            {formatPct(cumulative_pnl_pct)}
          </strong>
        </div>
      </div>

      {trade_count === 0 && (
        <div className="paper-portfolio-empty">
          <span>AWAITING FIRST TRADE</span>
          <p>
            The portfolio is persisted and running. The strategy engine will
            open its first paper position when a qualifying signal appears.
          </p>
        </div>
      )}

      {lastUpdate && (
        <div className="paper-portfolio-footer">
          Last synced {new Date(lastUpdate).toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
          })}
        </div>
      )}
    </div>
  );
}

export default PaperPortfolio;