import { useEffect, useState } from 'react';
import { encodeTicker } from '../utils/ticker';

const WS_BASE_URL = import.meta.env.VITE_WS_BASE_URL || 'ws://localhost:8000';

export function useLiveTradingPrediction(ticker, assetClass = 'stocks') {
  const [prediction, setPrediction] = useState(null);
  const [bars, setBars] = useState([]);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!ticker) {
      setPrediction(null); setBars([]); setConnected(false); setError('');
      return undefined;
    }

    let active = true;
    let websocket = null;
    setPrediction(null); setBars([]); setConnected(false); setError('');

    const safeTicker = encodeTicker(ticker);

    websocket = new WebSocket(
      `${WS_BASE_URL}/api/v1/trading/live/stream/${safeTicker}`
    );

    websocket.onopen = () => { if (active) { setConnected(true); setError(''); } };
    websocket.onmessage = (event) => {
      if (!active) return;
      try {
        const payload = JSON.parse(event.data);
        if (payload?.status === 'success') {
          const liveData = payload.prediction ?? null;
          setBars(liveData?.bars ?? []);
          setPrediction(liveData?.prediction ?? null);
          setConnected(true); setError('');
          return;
        }
        if (payload?.status === 'error') {
          setConnected(false);
          setError(payload.error || 'Live prediction failed.');
        }
      } catch {
        setError('Invalid live prediction response.');
      }
    };
    websocket.onerror = () => { if (active) { setConnected(false); setError('Live prediction connection failed.'); } };
    websocket.onclose = () => { if (active) setConnected(false); };

    return () => {
      active = false;
      if (websocket && (websocket.readyState === WebSocket.OPEN || websocket.readyState === WebSocket.CONNECTING)) {
        websocket.close();
      }
    };
  }, [ticker, assetClass]);

  return { prediction, bars, connected, error };
}