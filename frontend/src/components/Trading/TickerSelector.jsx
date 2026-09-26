import React from 'react';

const TickerSelector = ({ tickers, selectedTicker, onSelect, loading }) => {
  if (loading) {
    return <div style={{ color: 'var(--text)' }}>Loading tickers...</div>;
  }

  return (
    <div className="flex items-center gap-4">
      <label className="text-sm font-medium" style={{ color: 'var(--text-h)' }}>
        Ticker:
      </label>
      <select
        value={selectedTicker}
        onChange={(e) => onSelect(e.target.value)}
        className="px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
        style={{
          borderColor: 'var(--border)',
          background: 'var(--bg)',
          color: 'var(--text-h)',
        }}
      >
        {tickers.map((ticker) => (
          <option key={ticker} value={ticker}>
            {ticker}
          </option>
        ))}
      </select>
    </div>
  );
};

export default TickerSelector;