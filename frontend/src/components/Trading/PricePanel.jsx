import React from 'react';

const PricePanel = ({ data }) => {
  if (!data || !data.data || data.data.length === 0) {
    return <div style={{ color: 'var(--text)' }}>No data available</div>;
  }

  const lastBar = data.data[data.data.length - 1];
  const prevBar = data.data[data.data.length - 2];
  const change = prevBar ? ((lastBar.close - prevBar.close) / prevBar.close * 100) : 0;

  return (
    <div className="trading-card">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold" style={{ color: 'var(--text-h)' }}>
            {data.ticker}
          </h2>
          <p className="text-sm" style={{ color: 'var(--text)' }}>
            {data.bars} bars loaded
          </p>
        </div>
        <div className="text-right">
          <p className="text-3xl font-bold" style={{ color: 'var(--text-h)' }}>
            ${lastBar.close.toFixed(2)}
          </p>
          <p className={`text-sm ${change >= 0 ? 'text-green-500' : 'text-red-500'}`}>
            {change >= 0 ? '+' : ''}{change.toFixed(2)}%
          </p>
        </div>
      </div>
      <div className="grid grid-cols-4 gap-4 mt-4 text-center">
        <div className="rounded p-2" style={{ background: 'var(--code-bg)' }}>
          <p className="text-xs" style={{ color: 'var(--text)' }}>Open</p>
          <p className="text-xs font-semibold" style={{ color: 'var(--text-h)' }}>
            ${lastBar.open.toFixed(2)}
          </p>
        </div>
        <div className="rounded p-2" style={{ background: 'var(--code-bg)' }}>
          <p className="text-xs" style={{ color: 'var(--text)' }}>High</p>
          <p className="text-xs font-semibold" style={{ color: 'var(--text-h)' }}>
            ${lastBar.high.toFixed(2)}
          </p>
        </div>
        <div className="rounded p-2" style={{ background: 'var(--code-bg)' }}>
          <p className="text-xs" style={{ color: 'var(--text)' }}>Low</p>
          <p className="text-xs font-semibold" style={{ color: 'var(--text-h)' }}>
            ${lastBar.low.toFixed(2)}
          </p>
        </div>
        <div className="rounded p-2" style={{ background: 'var(--code-bg)' }}>
          <p className="text-xs" style={{ color: 'var(--text)' }}>Volume</p>
          <p className="text-xs font-semibold" style={{ color: 'var(--text-h)' }}>
            {lastBar.volume.toLocaleString()}
          </p>
        </div>
      </div>
    </div>
  );
};

export default PricePanel;