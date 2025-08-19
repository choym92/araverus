"""
Database manager for storing stock data and signals in Supabase.
"""
import os
import logging
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any
from supabase import create_client, Client

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages database operations with Supabase."""
    
    def __init__(self):
        url = os.getenv('SUPABASE_URL')
        key = os.getenv('SUPABASE_SERVICE_KEY')
        
        if not url or not key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
            
        self.client: Client = create_client(url, key)
        
    def save_stock_data(self, stock_data: Dict[str, pd.DataFrame]):
        """Save stock price data to database."""
        records = []
        
        for symbol, df in stock_data.items():
            for index, row in df.iterrows():
                records.append({
                    'symbol': symbol,
                    'date': index.isoformat(),
                    'open': float(row['Open']),
                    'high': float(row['High']),
                    'low': float(row['Low']),
                    'close': float(row['Close']),
                    'volume': int(row['Volume']),
                    'created_at': datetime.now().isoformat()
                })
        
        if records:
            try:
                # Upsert to handle duplicates
                response = self.client.table('stock_prices').upsert(
                    records,
                    on_conflict='symbol,date'
                ).execute()
                logger.info(f"Saved {len(records)} stock price records")
            except Exception as e:
                logger.error(f"Failed to save stock data: {e}")
                raise
    
    def save_signals(self, signals: List[Dict[str, Any]]):
        """Save trading signals to database."""
        if not signals:
            logger.info("No signals to save")
            return
            
        # Add created_at timestamp
        for signal in signals:
            signal['created_at'] = datetime.now().isoformat()
            signal['timestamp'] = signal['timestamp'].isoformat()
        
        try:
            response = self.client.table('trading_signals').insert(signals).execute()
            logger.info(f"Saved {len(signals)} trading signals")
        except Exception as e:
            logger.error(f"Failed to save signals: {e}")
            raise
    
    def get_watchlist(self) -> List[str]:
        """Get watchlist from database (future enhancement)."""
        # For now, return empty list - will be implemented when we have user watchlists
        return []