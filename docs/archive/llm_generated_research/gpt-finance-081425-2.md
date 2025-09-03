Milestones (DoR/DoD = Definition of Ready/Done)
M0 — Monorepo & Ops Skeleton

Outcome: Python lives alongside your Next.js app without touching the Vercel build.

Create /quant/ with requirements.txt, engine.py, /data_sources, /features, /io, /backtest, /notebooks.

Add .env pattern and secrets doc (Supabase URL/key, email SMTP).

DoD: python quant/engine.py runs locally; prints hello & can write to /public/data/.

M1 — Data Ingestion (Prices)

Outcome: Clean OHLCV for AAPL; daily resample → weekly; persisted.

Source: yfinance (AAPL, 10y, 1d).

Tables (Supabase) or local DuckDB: price_bars(ticker, dt, ohlcv, adj_close, interval).

DoD: price_bars populated; parquet cache saved; /public/data/raw/aapl_last.json exists.

M2 — Indicators & Signal Engine v1 (Technicals only)

Outcome: Daily/weekly RSI/MACD/SMAs + state machine → signal label.

features/indicators.py (RSI, MACD, SMAs).

features/signals.py (rules):

Early Buy: RSI<30 or cross↑30 (+ optional near 50SMA-)

Confirmed Buy: MACD cross↑ and close>20/50SMA and weekly momentum not bearish

Early/Confirmed Sell: symmetric (RSI>70; MACD cross↓; close<50SMA)

DoD: /public/data/signals/aapl.json with {ticker, asOf, signal, explanation, technicals}; renders in a simple Next.js page.

M3 — Fundamentals v1 + DCF v1 (Cheap & Simple)

Outcome: Snapshot quality & valuation to gate signals and annotate risk.

Source: FMP/Yahoo-style ratios (PE, PS, EV/EBITDA, ROIC/ROE, FCF margin, Net-Debt/EBITDA, SBC% rev if available).

features/fundamentals_score.py → Quality (0–25) + Valuation (0–25) + Class (A/B/C).

features/dcf.py → 5-yr FCF CAGR (bounded), terminal 1.5–2.0%, CAPM discount → fair, low, high.

Combine: position intent = f(Technical Signal, Fundamental Class, DCF discount).

DoD: /public/data/signals/aapl.json expanded with {fundamentals:{class, scores, pe, ps, ev_ebitda, roic, dcf:{fair,low,high,discount}}} and the UI shows a fair-value band.

M4 — Backtesting & Guardrails

Outcome: Honest stats; no look-ahead; param sanity.

Use Backtesting.py or vectorized pandas; trade next open after close signal.

Baselines: Buy&Hold, 200SMA trend-follow.

Metrics: CAGR, Sharpe/Sortino, MaxDD, hit-rate, expectancy, turnover.

Walk-forward: tune on window A, test on B; keep params conservative.

DoD: Markdown report in /quant/backtest/reports/aapl.md with charts + table vs baselines.

M5 — Automation & Alerts

Outcome: It runs itself after market close; only pings you for confirmed state changes.

GitHub Actions nightly (weekday 6–7pm ET) → run engine → write /public/data/....

Email (or Telegram) only on state transition to Confirmed Buy/Sell (throttled; 1/day/ticker max).

Logging + error capture to a simple file (or Supabase table).

DoD: You receive an email when label changes; site updates JSON nightly.

M6 — SEC / XBRL Module (Foundation for KPIs like RPO)

Outcome: You can extract special KPIs & MD&A snippets when needed.

data_sources/sec_xbrl.py: data.sec.gov companyfacts + submissions (proper User-Agent).

Parser helpers to extract: SBC expense, deferred revenue, guidance phrases; RPO for SaaS later.

DoD: For AAPL, demonstrate SBC + deferred revenue mapping (even if not core KPI here); store in fundamentals_kpis.

M7 — Scale Out & Portfolio Layer

Outcome: From AAPL → watchlist (10–50 tickers) + portfolio signals.

Rate-limit aware batching; caching; retries.

Add signals_latest materialized view (per ticker latest row).

Portfolio intent: sum of weights, sector buckets, cash level; simple vol targeting (optional).

DoD: /public/data/signals/index.json list view; dashboard grid renders multiple tickers.

M8 — Risk & Execution Playbook (Optional)

Outcome: Practical sizing & exit hygiene.

Position sizing: vol/ATR target or fixed risk per trade.

Exits: ATR/trailing stop; earnings blackout window; partial profit-taking.

DoD: Signal JSON adds {risk:{atr, stop, target}}; backtest includes risk rules variant.

Front-End Contract (keep it stable)

/public/data/signals/aapl.json

{
  "ticker":"AAPL",
  "asOf":"YYYY-MM-DD",
  "signal":"EarlyBuy|ConfirmedBuy|EarlySell|ConfirmedSell|Hold",
  "explanation":"human-readable reason",
  "technicals":{
    "rsi14_d": 48.3, "rsi14_w": 55.2,
    "macd_d": {"line": -0.12, "signal": -0.18, "cross":"up|down|none"},
    "sma20": 0, "sma50": 0, "sma200": 0
  },
  "fundamentals":{
    "class":"A|B|C",
    "qualityScore": 22, "valuationScore": 14,
    "pe_ttm": 0, "ps_ttm": 0, "ev_ebitda": 0,
    "roic": 0, "netDebtEbitda": 0,
    "dcf":{"fair":0,"low":0,"high":0,"discount":-12.3}
  }
}

Data & Storage Choices

Truth store: Supabase Postgres (price_bars, indicators_daily, signals_daily, optional fundamentals_kpis).

UI feed: tiny JSON in /public/data/ (fast, cacheable; easy with Vercel).

EDA/Backtests: parquet/DuckDB in /quant/.data_local/ (git-ignored).

Success Criteria

M2: Signal JSON updates nightly and matches rule examples on historical dates.

M3: Fundamental class changes only on new filings/ratios; DCF band visible; signals gated sensibly.

M4: Strategy beats Buy&Hold risk-adjusted or draws down less than baseline; params not overfit.

M5: Zero-touch nightly run; alert noise < 2/month unless markets are extreme.

M7: 10–50 tickers stable within API limits.

Risks & Mitigations

Data quirks / survivorship bias: lock calendars, adjust splits/dividends; cache vendor responses.

Overfitting: keep few parameters; walk-forward; report out-of-sample only.

Alert spam: throttle + “confirmed only”; group daily digest option.

Vendor limits: batch + backoff; local mirror for historical; consider FMP paid if scaling.

First 12 Tasks (in order)

Add /quant/ skeleton + requirements.

Write prices.py (AAPL daily 10y) → parquet + Supabase price_bars.

Build indicators.py (RSI/MACD/SMAs) + unit tests on known values.

Implement signals.py (rules) + golden test cases (crafted dates).

Emit /public/data/signals/aapl.json; add minimal Next.js page to render it.

Add weekly resample + weekly momentum gate.

Pull fundamentals (ratios) → fundamentals_score.py + Class A/B/C.

Implement dcf.py (bounded growth, discount) + serialize band.

Integrate fundamentals gating into final label + explanation.

Backtest v1 (next-open execution, costs, metrics) + report.

GitHub Action nightly run; commit JSON artifact; basic logging.

Email sender on state change to Confirmed Buy/Sell (throttled).

If you want, I can turn this into GitHub issues (one per task with acceptance criteria), but this is the clean roadmap I’d follow.