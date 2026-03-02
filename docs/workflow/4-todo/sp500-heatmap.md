<!-- Created: 2026-03-02 -->
# S&P 500 Heatmap — Finviz-style Treemap for chopaul.com

## Concept

Build a Finviz-style stock market heatmap (treemap visualization) showing S&P 500 stocks grouped by sector, sized by market cap, colored by daily % change (green = up, red = down).

Reference: [Finviz S&P 500 Map](https://finviz.com/map.ashx)

---

## Legal Considerations

### Allowed
- Treemap layout itself is a generic data visualization technique — not copyrightable
- Building your own with independently sourced data is fully legal
- Using open-source libraries (D3.js, Recharts) for rendering

### Not Allowed
- Scraping Finviz directly (ToS violation)
- Copying their code, images, or branding
- Implying affiliation ("Powered by Finviz", etc.)

### Gray Area
- Commercial use of free-tier API data — check each provider's ToS
- Real-time exchange data requires exchange licenses for redistribution (not needed for delayed/EOD)

---

## Data Source Decision: Finnhub (Winner)

### Why Finnhub

| Criteria | Finnhub (Free) | FMP (Free) | Alpha Vantage (Free) | yfinance |
|----------|---------------|------------|---------------------|----------|
| **Rate limit** | 60 calls/min | 250 calls/day | 25 calls/day | ~6/min (unofficial) |
| **Daily cap** | No explicit cap | 250/day hard | 25/day hard | No cap but blocks |
| **Data freshness** | Real-time (US) | EOD only | 15min delay | ~15min delay |
| **WebSocket** | Yes (free) | No | No | No |
| **Bulk endpoint** | No | $99/mo only | No | Batch but unstable |
| **Stability** | Official API + key | Official API + key | Official API + key | Unofficial scraper |
| **Cost** | $0 | $0 | $0 | $0 |

### Finnhub Free Tier Details
- **60 API calls/minute** (REST endpoints)
- **30 calls/second** hard ceiling on top of plan limit
- **WebSocket**: Real-time trade data, subscribe to multiple symbols — does NOT count against REST call limit
- **No explicit daily cap** — only per-minute rate limiting
- **Includes**: US stock quotes, company profiles, market news, basic fundamentals
- **429 error** if rate exceeded (temporary, retry after cooldown)

### FMP Free Tier Details (from pricing page screenshot)
- **250 calls/day** — too low for 500 stocks
- **EOD (End of Day)** data only — no intraday
- **500MB bandwidth / 30 days**
- **150+ endpoints** accessible
- **Profile and Reference Data** included
- **Bulk/Batch Delivery** only on Ultimate plan ($99/mo)
- Starter ($19/mo): 300/min, 5yr history, US coverage
- Premium ($49/mo): 750/min, 30yr history, intraday charts
- Ultimate ($99/mo): 3,000/min, bulk & batch delivery

### Rejected Alternatives
- **Alpha Vantage**: 25 calls/day — impossible for 500 stocks
- **Polygon.io**: 5 calls/min — 100 minutes to fetch 500 stocks
- **yfinance**: Unofficial scraper, Yahoo tightened limits in 2024-2025, frequent 429 errors, unreliable for production

---

## WebSocket Explained

**REST API** (traditional): Client asks → Server responds → Connection closes. Repeat for each stock.
```
Client: "AAPL price?" → Server: "$185.50" → done
Client: "MSFT price?" → Server: "$420.30" → done
... 500 times = 500 API calls
```

**WebSocket**: Persistent two-way connection. Subscribe once, receive updates automatically.
```
Client: "Subscribe to AAPL, MSFT, ... 500 symbols"
Server: pushes price updates whenever they change
No repeated API calls — data flows continuously
```

Key benefit: **WebSocket connections don't count against the 60 calls/min REST limit.**

---

## Architecture

```
┌─────────────────────────────────────────┐
│  Mac Mini (Python, always-on)           │
│                                         │
│  finnhub_ws_collector.py                │
│  ├─ WebSocket connect to Finnhub        │
│  ├─ Subscribe to ~500 S&P 500 symbols   │
│  ├─ On price update → batch upsert      │
│  │   to Supabase (sp500_quotes table)   │
│  ├─ Market hours: WebSocket active      │
│  └─ After hours: disconnect, sleep      │
│                                         │
│  Cron: refresh S&P 500 list quarterly   │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│  Supabase                               │
│                                         │
│  sp500_constituents                     │
│  ├─ symbol, company_name, sector        │
│  ├─ sub_industry, market_cap            │
│  └─ updated_at                          │
│                                         │
│  sp500_quotes                           │
│  ├─ symbol, price, change_pct           │
│  ├─ volume, previous_close              │
│  └─ updated_at                          │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│  Next.js (chopaul.com)                  │
│                                         │
│  /markets (or /finance/heatmap)         │
│  ├─ Server Component: fetch from        │
│  │   Supabase sp500_quotes + sectors    │
│  ├─ Client Component: D3.js treemap    │
│  │   - Size: market cap                 │
│  │   - Color: daily % change            │
│  │   - Sectors: grouped rectangles      │
│  │   - Hover: tooltip with details      │
│  └─ ISR/revalidate: 60s (or on-demand) │
└─────────────────────────────────────────┘
```

---

## S&P 500 Constituent List

### Source Options (Free)
1. **Wikipedia** — [S&P 500 companies table](https://en.wikipedia.org/wiki/List_of_S%26P_500_companies) — scrape or manual CSV
2. **GitHub datasets** — multiple repos maintain updated CSVs
3. **Finnhub API** — `GET /api/v1/index/constituents?symbol=^GSPC` (if available on free tier)

### Storage
- Supabase `sp500_constituents` table
- Refresh quarterly (composition changes ~20-30 stocks/year)
- Fields: symbol, company_name, sector, sub_industry, market_cap_weight

---

## Rendering Library Options

| Library | Pros | Cons |
|---------|------|------|
| **D3.js treemap** | Full control, exact Finviz-style possible | More code, steeper learning curve |
| **Recharts Treemap** | Simple React API, quick setup | Less customizable |
| **Nivo Treemap** | Beautiful defaults, React-native | Heavier bundle |
| **Lightweight Charts (TradingView)** | Professional look | No treemap — charts only |

**Recommendation**: D3.js for full Finviz-style control (sector grouping, nested rectangles, color gradients).

---

## Cost Estimate

| Component | Cost |
|-----------|------|
| Finnhub API | $0 (free tier) |
| Supabase | $0 (existing free/pro plan) |
| Mac Mini (existing) | $0 (already running pipeline) |
| Vercel (existing) | $0 (already deployed) |
| D3.js | $0 (open source) |
| **Total** | **$0/month** |

---

## Implementation Phases

### Phase 1: Data Pipeline (Python, Mac Mini)
- [ ] Create `sp500_constituents` table in Supabase
- [ ] Script to fetch/store S&P 500 list (Wikipedia or Finnhub)
- [ ] Create `sp500_quotes` table in Supabase
- [ ] `finnhub_ws_collector.py` — WebSocket collector script
- [ ] Cron job: start on market open, stop after close
- [ ] Batch upsert logic (don't write every tick — aggregate 30s/1min)

### Phase 2: Frontend (Next.js)
- [ ] Route: `/markets` or `/finance/heatmap`
- [ ] Server Component: fetch latest quotes + constituents from Supabase
- [ ] Client Component: D3.js treemap renderer
- [ ] Color scale: red (-3%+) → white (0%) → green (+3%+)
- [ ] Sector grouping with labels
- [ ] Hover tooltips (symbol, name, price, % change, volume)
- [ ] Responsive: desktop full treemap, mobile simplified or list view

### Phase 3: Polish
- [ ] Click-through to stock detail (link to Yahoo/Google Finance or internal page)
- [ ] Time selector: 1D, 1W, 1M, YTD
- [ ] Market status indicator (open/closed/pre-market)
- [ ] Loading skeleton while data fetches
- [ ] SEO metadata

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Finnhub changes free tier | Data stops flowing | Fallback to FMP EOD or yfinance batch |
| WebSocket disconnects | Stale prices | Auto-reconnect logic with exponential backoff |
| 500 symbols too many for WS | Partial data | Split into 2 connections or use REST polling for overflow |
| Exchange data redistribution | Legal issue | Display delayed data, add "Data provided by Finnhub" attribution |
| Mac Mini downtime | No updates | Data stays stale until restart; add health check alert |

---

## Open Questions

1. **URL path**: `/markets`, `/finance`, or `/stocks`?
2. **Scope**: S&P 500 only, or expand to NASDAQ 100 / sectors later?
3. **Update frequency**: Real-time via WebSocket or periodic (every 1-5 min)?
4. **Mobile UX**: Treemap doesn't work well on small screens — table/list alternative?
5. **Attribution**: Finnhub requires "Data provided by Finnhub" — where to place?
