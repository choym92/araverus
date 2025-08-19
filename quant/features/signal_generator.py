"""
Signal generator for stock trading signals.
Simple implementation using basic technical indicators.
"""
import logging
import pandas as pd
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


class SignalGenerator:
    """Generates trading signals from stock data."""
    
    def __init__(self):
        self.rsi_oversold = 30
        self.rsi_overbought = 70
        self.sma_short = 20
        self.sma_long = 50
        
    def generate_signals(self, stock_data: Dict[str, pd.DataFrame]) -> List[Dict[str, Any]]:
        """Generate signals for all stocks."""
        all_signals = []
        
        for symbol, df in stock_data.items():
            try:
                signals = self._analyze_stock(symbol, df)
                all_signals.extend(signals)
            except Exception as e:
                logger.error(f"Failed to generate signals for {symbol}: {e}")
                
        return all_signals
    
    def _analyze_stock(self, symbol: str, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Analyze a single stock and generate signals."""
        signals = []
        
        # Calculate indicators
        df['SMA_20'] = df['Close'].rolling(window=20).mean()
        df['SMA_50'] = df['Close'].rolling(window=50).mean()
        df['RSI'] = self._calculate_rsi(df['Close'])
        
        # Get latest values
        latest = df.iloc[-1]
        
        # Check for signals
        if pd.notna(latest['RSI']):
            if latest['RSI'] < self.rsi_oversold:
                signals.append({
                    'symbol': symbol,
                    'signal_type': 'BUY',
                    'indicator': 'RSI_OVERSOLD',
                    'value': latest['RSI'],
                    'price': latest['Close'],
                    'timestamp': latest.name
                })
            elif latest['RSI'] > self.rsi_overbought:
                signals.append({
                    'symbol': symbol,
                    'signal_type': 'SELL',
                    'indicator': 'RSI_OVERBOUGHT',
                    'value': latest['RSI'],
                    'price': latest['Close'],
                    'timestamp': latest.name
                })
        
        # Moving average crossover
        if pd.notna(latest['SMA_20']) and pd.notna(latest['SMA_50']):
            if latest['SMA_20'] > latest['SMA_50']:
                signals.append({
                    'symbol': symbol,
                    'signal_type': 'BULLISH',
                    'indicator': 'GOLDEN_CROSS',
                    'value': latest['SMA_20'] / latest['SMA_50'],
                    'price': latest['Close'],
                    'timestamp': latest.name
                })
                
        return signals
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI indicator."""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi