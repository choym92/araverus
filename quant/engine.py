#!/usr/bin/env python3
"""
Main orchestration engine for stock data processing and signal generation.
Runs daily batch job to update stock data and generate trading signals.
"""
import os
import logging
from datetime import datetime
from dotenv import load_dotenv

from data_sources.stock_fetcher import StockDataFetcher
from features.signal_generator import SignalGenerator
from database.database import DatabaseManager

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class QuantEngine:
    """Main engine for processing stock data and generating signals."""
    
    def __init__(self):
        self.db = DatabaseManager()
        self.fetcher = StockDataFetcher()
        self.signal_gen = SignalGenerator()
        
    def run_daily_batch(self):
        """Main daily batch processing."""
        logger.info(f"Starting daily batch at {datetime.now()}")
        
        try:
            # 1. Fetch latest stock data
            symbols = self._get_watchlist()
            stock_data = self.fetcher.fetch_batch(symbols)
            
            # 2. Generate signals
            signals = self.signal_gen.generate_signals(stock_data)
            
            # 3. Store results
            self.db.save_signals(signals)
            self.db.save_stock_data(stock_data)
            
            logger.info(f"Batch completed successfully. Processed {len(symbols)} symbols")
            
        except Exception as e:
            logger.error(f"Batch failed: {e}")
            raise
    
    def _get_watchlist(self):
        """Get list of stocks to monitor."""
        # For now, start with a few key stocks
        return ['AAPL', 'MSFT', 'GOOGL', 'TSLA', 'NVDA']


if __name__ == "__main__":
    engine = QuantEngine()
    engine.run_daily_batch()