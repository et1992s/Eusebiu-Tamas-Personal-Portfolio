import React, { useState, useMemo, useRef, useEffect } from 'react';

const TickerSelector = ({ tickers, selectedTicker, onSelect, loading }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState('');
  const wrapperRef = useRef(null);

  // Close on outside click
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) {
        setIsOpen(false);
        setSearch('');
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const filtered = useMemo(() => {
    if (!Array.isArray(tickers)) return [];

    // If nothing typed, show a sensible subset (first 50 alphabetically)
    if (!search) return tickers.slice(0, 50);

    const q = search.toUpperCase();

    return tickers
      .filter((t) => {
        const symbol = (t.symbol || t).toUpperCase();
        const name = (t.name || '').toUpperCase();
        return symbol.includes(q) || name.includes(q);
      })
      .slice(0, 50);
  }, [tickers, search]);

  return (
    <div
      ref={wrapperRef}
      className="bars-control"
      style={{ position: 'relative' }}
    >
      <span>Ticker</span>

      <input
        type="text"
        value={isOpen ? search : selectedTicker}
        placeholder={loading ? 'Loading…' : 'Search symbol…'}
        onFocus={() => {
          setIsOpen(true);
          setSearch('');
        }}
        onChange={(e) => setSearch(e.target.value)}
        style={{
          borderColor: 'var(--border)',
          background: 'var(--bg)',
          color: 'var(--text-h)',
          padding: '6px 10px',
          width: '100%',
        }}
      />

      {isOpen && (
        <div
          style={{
            position: 'absolute',
            top: '100%',
            left: 0,
            right: 0,
            maxHeight: 280,
            overflowY: 'auto',
            background: 'var(--bg)',
            border: '1px solid var(--border)',
            borderRadius: 4,
            zIndex: 100,
            boxShadow: '0 4px 12px rgba(0,0,0,0.35)',
          }}
        >
          {loading && (
            <div style={{ padding: 10, fontSize: 11, color: 'var(--text)' }}>
              Fetching assets from Alpaca…
            </div>
          )}

          {!loading && filtered.length === 0 && (
            <div style={{ padding: 10, fontSize: 11, color: 'var(--text)' }}>
              No matches for "{search}"
            </div>
          )}

          {!loading &&
            filtered.map((t) => {
              const symbol = t.symbol || t;
              const name = t.name || '';
              const isSelected = symbol === selectedTicker;

              return (
                <div
                  key={symbol}
                  onMouseDown={() => {
                    onSelect(symbol);
                    setIsOpen(false);
                    setSearch('');
                  }}
                  style={{
                    padding: '7px 10px',
                    cursor: 'pointer',
                    borderBottom: '1px solid var(--border)',
                    background: isSelected
                      ? 'var(--code-bg)'
                      : 'transparent',
                  }}
                  onMouseEnter={(e) => {
                    if (!isSelected) e.currentTarget.style.background = 'var(--code-bg)';
                  }}
                  onMouseLeave={(e) => {
                    if (!isSelected) e.currentTarget.style.background = 'transparent';
                  }}
                >
                  <div style={{ fontWeight: 600, fontSize: 12 }}>{symbol}</div>
                  {name && (
                    <div style={{ fontSize: 10, color: 'var(--text)', marginTop: 2 }}>
                      {name}
                    </div>
                  )}
                </div>
              );
            })}

          {!loading && !search && tickers.length > 50 && (
            <div
              style={{
                padding: '6px 10px',
                fontSize: 10,
                color: 'var(--text)',
                textAlign: 'center',
                fontStyle: 'italic',
              }}
            >
              Type to search {tickers.length.toLocaleString()} symbols…
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default TickerSelector;