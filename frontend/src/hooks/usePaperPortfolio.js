import { useEffect, useState } from 'react';

const API_BASE_URL =
  window.location.hostname === 'localhost' ||
  window.location.hostname === '127.0.0.1'
    ? ''
    : 'https://api.eusebiutamas.com';

const POLL_MS = 60_000;

export function usePaperPortfolio(portfolioName = 'default') {
  const [portfolio, setPortfolio] = useState(null);
  const [equity, setEquity] = useState([]);
  const [trades, setTrades] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [lastUpdate, setLastUpdate] = useState(null);

  useEffect(() => {
    let active = true;
    let timer = null;

    async function fetchAll() {
      try {
        const [pRes, eRes, tRes] = await Promise.all([
          fetch(`${API_BASE_URL}/api/v1/paper/portfolio?name=${portfolioName}`),
          fetch(`${API_BASE_URL}/api/v1/paper/equity?name=${portfolioName}&limit=500`),
          fetch(`${API_BASE_URL}/api/v1/paper/trades?name=${portfolioName}&limit=100`),
        ]);

        if (!pRes.ok) throw new Error(`Portfolio HTTP ${pRes.status}`);

        const [pJson, eJson, tJson] = await Promise.all([
          pRes.json(),
          eRes.ok ? eRes.json() : { points: [] },
          tRes.ok ? tRes.json() : { trades: [] },
        ]);

        if (!active) return;

        setPortfolio(pJson.portfolio || null);
        setEquity(eJson.points || []);
        setTrades(tJson.trades || []);
        setError('');
        setLastUpdate(new Date().toISOString());
      } catch (err) {
        if (!active) return;
        setError(err.message || 'Failed to load portfolio');
      } finally {
        if (active) setLoading(false);
      }
    }

    fetchAll();
    timer = setInterval(fetchAll, POLL_MS);

    return () => {
      active = false;
      if (timer) clearInterval(timer);
    };
  }, [portfolioName]);

  return { portfolio, equity, trades, loading, error, lastUpdate };
}