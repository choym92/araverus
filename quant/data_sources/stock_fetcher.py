"""
Stock data fetcher using yfinance as primary source.
Simple implementation - fetches daily OHLCV data.
"""
import logging
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class StockDataFetcher:
    """Fetches stock data from Yahoo Finance."""
    
    def __init__(self):
        self.period = "1mo"  # Start with 1 month of data
        
    def fetch_batch(self, symbols: List[str]) -> Dict[str, pd.DataFrame]:
        """Fetch stock data for multiple symbols."""
        results = {}
        
        for symbol in symbols:
            try:
                data = self.fetch_single(symbol)
                results[symbol] = data
                logger.info(f"Fetched data for {symbol}")
            except Exception as e:
                logger.error(f"Failed to fetch {symbol}: {e}")
                
        return results
    
    def fetch_single(self, symbol: str) -> pd.DataFrame:
        """Fetch data for a single symbol."""
        ticker = yf.Ticker(symbol)
        
        # Get historical data
        hist = ticker.history(period=self.period)
        
        if hist.empty:
            raise ValueError(f"No data returned for {symbol}")
            
        # Add symbol column
        hist['symbol'] = symbol
        
        return hist