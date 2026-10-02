import { useEffect, useState } from 'react';
import { tradingApi } from '../services/api';

const DEFAULT_LIMIT = 500;

export function useTradingPrediction(
  ticker,
  limit = DEFAULT_LIMIT,
) {
  const [prediction, setPrediction] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!ticker) {
      setPrediction(null);
      setLoading(false);
      setError('');
      return undefined;
    }

    let cancelled = false;

    setLoading(true);
    setError('');
    setPrediction(null);

    tradingApi
      .predict(ticker, limit)
      .then((payload) => {
        if (cancelled) return;

        const result = payload?.prediction ?? null;

        setPrediction(result);
      })
      .catch((err) => {
        if (cancelled) return;

        setPrediction(null);
        setError(
          err?.response?.data?.detail ||
          err?.message ||
          'Failed to load ML prediction',
        );
      })
      .finally(() => {
        if (cancelled) return;

        setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [ticker, limit]);

  return {
    prediction,
    loading,
    error,
  };
}