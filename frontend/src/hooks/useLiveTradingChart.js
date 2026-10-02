import { useEffect, useState, useRef } from 'react';
import { encodeTicker } from '../utils/ticker';

export function useLiveTradingChart(ticker, timeframe = '1m', assetClass = 'stocks') {
  const [bars, setBars] = useState([]);
  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const wsRef = useRef(null);

  useEffect(() => {
    if (!ticker) return;

    setLoading(true);
    setBars([]);
    setError('');

    const safeTicker = encodeTicker(ticker);

    // 1. Fetch initial historical bars
    const fetchInitialBars = async () => {
      try {
        const res = await fetch(
          `/api/v1/trading/live/chart/${safeTicker}?timeframe=${timeframe}&limit=200&asset_class=${assetClass}`
        );
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        setBars(data.data || []);
      } catch (err) {
        setError(err.message || 'Failed to load initial chart data');
      } finally {
        setLoading(false);
      }
    };
    fetchInitialBars();

    // 2. WebSocket for live updates — ticker is dash-encoded, no slash issue
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//localhost:8000/api/v1/trading/live/chart/stream/${safeTicker}?asset_class=${assetClass}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onmessage = (event) => {
      try {
        const messages = JSON.parse(event.data);
        messages.forEach((msg) => {
          if (msg.T === 'b') {
            const newBar = {
              timestamp: msg.t,
              open: parseFloat(msg.o),
              high: parseFloat(msg.h),
              low: parseFloat(msg.l),
              close: parseFloat(msg.c),
              volume: parseFloat(msg.v),
            };
            setBars((prev) => {
              const last = prev[prev.length - 1];
              const newTime = new Date(newBar.timestamp).getTime();
              const lastTime = last ? new Date(last.timestamp).getTime() : 0;
              if (newTime === lastTime) {
                const updated = [...prev];
                updated[updated.length - 1] = newBar;
                return updated;
              }
              if (newTime > lastTime) {
                return [...prev, newBar];
              }
              return prev;
            });
          }
        });
      } catch (err) {
        console.error('Bad WS message', err);
      }
    };
    ws.onerror = () => setError('Live chart WebSocket error');
    ws.onclose = () => setConnected(false);

    return () => {
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        ws.close();
      }
    };
  }, [ticker, timeframe, assetClass]);

  return { bars, connected, loading, error };
}