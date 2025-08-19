# Quant - Stock Data Processing Sidecar

Python batch processing engine for fetching stock data and generating trading signals.

## Setup

1. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment:
```bash
cp .env.example .env
# Edit .env with your Supabase credentials
```

4. Create database tables:
```sql
-- Run schema.sql in Supabase SQL editor
```

## Usage

Run daily batch:
```bash
python engine.py
```

## Architecture

- `engine.py` - Main orchestrator
- `data_sources/` - Stock data fetchers (Yahoo Finance)
- `features/` - Signal generation (RSI, SMA crossovers)
- `io/` - Database operations (Supabase)

## Signals Generated

- **RSI_OVERSOLD**: RSI < 30 (potential buy)
- **RSI_OVERBOUGHT**: RSI > 70 (potential sell)
- **GOLDEN_CROSS**: 20-day SMA crosses above 50-day SMA (bullish)