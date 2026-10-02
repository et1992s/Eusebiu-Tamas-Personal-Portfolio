import { useEffect, useState } from 'react';
import { tradingApi } from '../services/api';

const DEFAULT_LIMIT = 200;

/* ------------------------------------------------------------------
   useTickers
   ------------------------------------------------------------------
   Loads the list of available tickers once on mount.
------------------------------------------------------------------ */
export function useTickers(assetClass = 'stocks') {
  const [tickers, setTickers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;

    setLoading(true);
    setTickers([]); // Clear stale tickers immediately when asset class changes
    setError('');

    fetch(`/api/v1/trading/assets?asset_class=${assetClass}`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((payload) => {
        if (cancelled) return;

        const list = Array.isArray(payload?.assets)
          ? payload.assets
          : [];

        setTickers(list);
        setError('');
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err?.message || 'Failed to load tickers');
      })
      .finally(() => {
        if (cancelled) return;
        setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [assetClass]);

  return { tickers, loading, error };
}

/* ------------------------------------------------------------------
   useTradingData
   ------------------------------------------------------------------
   Loads OHLC bars for one ticker whenever ticker/limit change.

   The API can return bars in several shapes depending on which
   backend version is running:
       { ticker, bars: [...] }
       { data: [...] }
       [...]
   The hook normalises them all to the same shape so downstream
   consumers don't have to guess.
------------------------------------------------------------------ */
export function useTradingData(ticker, limit = DEFAULT_LIMIT, assetClass = 'stocks') {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!ticker || assetClass === 'crypto') {
      // No historical pickle data for crypto — backtest falls back to synthetic
      setData({ ticker, bars: [], data: [] });
      setLoading(false);
      setError('');
      return undefined;
    }

    let cancelled = false;
    setLoading(true);

    tradingApi.getBars(ticker, limit)
      .then((payload) => {
        if (cancelled) return;
        const bars = Array.isArray(payload) ? payload
          : Array.isArray(payload?.bars) ? payload.bars
          : Array.isArray(payload?.data) ? payload.data
          : [];
        setData({ ticker, bars, data: bars });
        setError('');
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err?.message || 'Failed to load market data');
        setData(null);
      })
      .finally(() => { if (!cancelled) setLoading(false); });

    return () => { cancelled = true; };
  }, [ticker, limit, assetClass]);

  return { data, loading, error };
}