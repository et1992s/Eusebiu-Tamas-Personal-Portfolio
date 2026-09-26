"""
engine.py - Pre-processed Pickle Version (FIXED)
"""

import pandas as pd
import datetime
import pickle
from pathlib import Path
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class TradingEngine:
    def __init__(self, data_path: str = 'data/algoseek_preprocessed.pkl'):
        self.data_path = Path(data_path)
        self.ticker_data: Dict[str, pd.DataFrame] = {}
        self.tickers: List[str] = []
        self._loaded = False
        
    def load_data(self):
        """Load pre-processed data - INSTANT"""
        if self._loaded:
            return
        
        if not self.data_path.exists():
            logger.error(f"File not found: {self.data_path}")
            return
        
        logger.info(f"Loading pre-processed data: {self.data_path}...")
        start = pd.Timestamp.now()
        
        with open(self.data_path, 'rb') as f:
            data = pickle.load(f)
        
        self.ticker_data = data['data']
        self.tickers = data['tickers']
        self._loaded = True
        
        elapsed = (pd.Timestamp.now() - start).total_seconds()
        logger.info(f"✅ Loaded {len(self.tickers)} tickers in {elapsed:.1f}s")
    
    def get_tickers(self) -> List[str]:
        if not self._loaded:
            self.load_data()
        return self.tickers
    
    def get_bars(self, ticker: str, limit: int = 100) -> Optional[List[Dict[str, Any]]]:
        """Get OHLCV bars - INSTANT"""
        if not self._loaded:
            self.load_data()
        
        if ticker not in self.ticker_data:
            logger.warning(f"Ticker '{ticker}' not found")
            return None
        
        ticker_df = self.ticker_data[ticker]
        
        # Get the last N rows directly (no year filter for now)
        if len(ticker_df) > limit:
            bars_df = ticker_df.iloc[-limit:]
        else:
            bars_df = ticker_df
        
        result = []
        for idx, row in bars_df.iterrows():
            # Convert timestamp to string
            if isinstance(idx, pd.Timestamp):
                timestamp_str = idx.strftime('%Y-%m-%dT%H:%M:%SZ')
            else:
                timestamp_str = str(idx)
            
            result.append({
                'timestamp': timestamp_str,
                'open': float(row['first']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['last']),
                'volume': int(row['volume'])
            })
        
        return result
    
    def get_bars_2015(self, ticker: str, limit: int = 100) -> List[Dict[str, Any]]:
        if not self._loaded:
            self.load_data()

        if ticker not in self.ticker_data:
            return []

        ticker_df = self.ticker_data[ticker]

        try:
            # Access timestamps only through their raw int64 representation.
            raw_index = ticker_df.index.asi8 # type: ignore

            start_ns = 1420070400000000000  # 2015-01-01
            end_ns = 1451606400000000000    # 2016-01-01

            mask = (raw_index >= start_ns) & (raw_index < end_ns)
            positions = mask.nonzero()[0]

            if len(positions) == 0:
                return []

            positions = positions[-limit:]

            # Select the rows, but NEVER ask Pandas to expose the DatetimeIndex.
            bars_df = ticker_df.iloc[positions]

            # index=False is critical here.
            rows = bars_df.itertuples(index=False, name=None)

            result = []

            for position, row in zip(positions, rows):
                timestamp_ns = int(raw_index[position])

                timestamp = datetime.datetime.fromtimestamp(
                    timestamp_ns / 1_000_000_000,
                    datetime.timezone.utc
                ).strftime('%Y-%m-%dT%H:%M:%SZ')

                result.append({
                    'timestamp': timestamp,
                    'open': float(row[0]),
                    'high': float(row[1]),
                    'low': float(row[2]),
                    'close': float(row[3]),
                    'volume': int(row[4])
                })

            return result

        except Exception as e:
            logger.error(f"Error processing 2015 bars for {ticker}: {e}")
            return []