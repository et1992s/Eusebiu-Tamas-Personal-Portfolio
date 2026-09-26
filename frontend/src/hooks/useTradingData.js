import { useState, useEffect } from 'react';
import { tradingApi } from '../services/api';

export const useTradingData = (ticker = 'AAPL', limit = 100) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      if (!ticker) return;
      
      try {
        setLoading(true);
        setError(null);
        console.log(`Fetching data for ${ticker}...`);
        const response = await tradingApi.getBars(ticker, limit);
        console.log('Data received:', response);
        setData(response);
      } catch (err) {
        console.error('Fetch error:', err);
        setError(err.message || 'Network Error');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [ticker, limit]);

  return { data, loading, error };
};

export const useTickers = () => {
  const [tickers, setTickers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchTickers = async () => {
      try {
        setLoading(true);
        setError(null);
        console.log('Fetching tickers...');
        const response = await tradingApi.getTickers();
        console.log('Tickers received:', response);
        setTickers(response.tickers || []);
      } catch (err) {
        console.error('Tickers error:', err);
        setError(err.message || 'Network Error');
      } finally {
        setLoading(false);
      }
    };

    fetchTickers();
  }, []);

  return { tickers, loading, error };
};