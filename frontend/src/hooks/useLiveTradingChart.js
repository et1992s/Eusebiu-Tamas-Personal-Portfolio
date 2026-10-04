import { useEffect, useState, useRef } from 'react';
import { encodeTicker } from '../utils/ticker';

const API_BASE_URL =
  window.location.hostname === 'localhost' ||
  window.location.hostname === '127.0.0.1'
    ? ''
    : 'https://api.eusebiutamas.com';

const WS_BASE_URL =
  window.location.hostname === 'localhost' ||
  window.location.hostname === '127.0.0.1'
    ? 'ws://localhost:8000'
    : 'wss://api.eusebiutamas.com';

export function useLiveTradingChart(
  ticker,
  timeframe = '1m',
  assetClass = 'stocks',
) {
  const [bars, setBars] = useState([]);
  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const wsRef = useRef(null);

  useEffect(() => {
    if (!ticker) {
      setBars([]);
      setConnected(false);
      setLoading(false);
      setError('');
      return undefined;
    }

    let active = true;

    setLoading(true);
    setBars([]);
    setConnected(false);
    setError('');

    const safeTicker = encodeTicker(ticker);

    const fetchInitialBars = async () => {
      try {
        const response = await fetch(
          `${API_BASE_URL}/api/v1/trading/live/chart/${safeTicker}?timeframe=${timeframe}&limit=200&asset_class=${assetClass}`,
        );

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();

        if (active) {
          setBars(data.data || []);
        }
      } catch (err) {
        if (active) {
          setError(
            err.message || 'Failed to load initial chart data',
          );
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    };

    fetchInitialBars();

    const wsUrl =
      `${WS_BASE_URL}/api/v1/trading/live/chart/stream/` +
      `${safeTicker}?asset_class=${assetClass}`;

    const ws = new WebSocket(wsUrl);

    wsRef.current = ws;

    ws.onopen = () => {
      if (active) {
        setConnected(true);
        setError('');
      }
    };

    ws.onmessage = (event) => {
      if (!active) {
        return;
      }

      try {
        const messages = JSON.parse(event.data);

        messages.forEach((msg) => {
          if (msg.T !== 'b') {
            return;
          }

          const newBar = {
            timestamp: msg.t,
            open: parseFloat(msg.o),
            high: parseFloat(msg.h),
            low: parseFloat(msg.l),
            close: parseFloat(msg.c),
            volume: parseFloat(msg.v),
          };

          setBars((previousBars) => {
            const lastBar =
              previousBars[previousBars.length - 1];

            const newTime = new Date(
              newBar.timestamp,
            ).getTime();

            const lastTime = lastBar
              ? new Date(lastBar.timestamp).getTime()
              : 0;

            if (newTime === lastTime) {
              const updatedBars = [
                ...previousBars,
              ];

              updatedBars[
                updatedBars.length - 1
              ] = newBar;

              return updatedBars;
            }

            if (newTime > lastTime) {
              return [
                ...previousBars,
                newBar,
              ];
            }

            return previousBars;
          });
        });
      } catch (err) {
        console.error('Bad WS message', err);
      }
    };

    ws.onerror = () => {
      if (active) {
        setConnected(false);
        setError('Live chart WebSocket error');
      }
    };

    ws.onclose = () => {
      if (active) {
        setConnected(false);
      }
    };

    return () => {
      active = false;

      if (
        wsRef.current &&
        (
          wsRef.current.readyState === WebSocket.OPEN ||
          wsRef.current.readyState === WebSocket.CONNECTING
        )
      ) {
        wsRef.current.close();
      }

      wsRef.current = null;
    };
  }, [ticker, timeframe, assetClass]);

  return {
    bars,
    connected,
    loading,
    error,
  };
}