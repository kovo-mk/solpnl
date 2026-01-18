# SolPNL Development Documentation

## Current Implementation Status (2026-01-18)

### ✅ Completed Features

#### Priority 5: Cross-Token Wash Trading Network Detection
- **Backend**: Tracks suspicious wallets across multiple token analyses
- **Database**: `suspicious_wallet_tokens` table with wallet-token-report relationships
- **API Endpoints**:
  - `GET /api/research/related-tokens/{token_address}` - Find tokens sharing suspicious wallets
  - `GET /api/research/shared-wallets/{token1}/{token2}` - Get detailed wallet overlap
- **Frontend**: Modal showing shared suspicious wallets with Solscan links
- **Location**: [frontend/app/research/page.tsx:992-1079](frontend/app/research/page.tsx#L992-L1079)

#### Liquidity Pool & Whale Tracking (Backend Complete)
- **Database Columns Added**:
  - `liquidity_pools` (JSON) - DEX pools with liquidity amounts
  - `whale_movements` (JSON) - Large transfers ($10k+ threshold)
- **Solscan API Integration**:
  - `fetch_token_markets()` - Gets all DEX pools (Raydium, Orca, etc.)
  - `fetch_whale_movements()` - Tracks large token transfers
  - `fetch_latest_tokens()` - Retrieves newly created tokens
- **Location**: [backend/services/solscan_api.py:21-205](backend/services/solscan_api.py#L21-L205)
- **Analysis Integration**: [backend/api/research.py:631-657](backend/api/research.py#L631-L657)

#### New Token Feed Infrastructure
- **Database**: `new_token_feed` table ready for monitoring newly launched tokens
- **Model**: [backend/database/models.py:391-418](backend/database/models.py#L391-L418)

### 🚧 In Progress

#### Frontend: Tab-Based Navigation (Next Task)
**Goal**: Improve mobile UX and organize analysis data better

**Planned Structure**:
```
┌──────────────────────────────────────┐
│ [Overview] [Network] [Liquidity] [Whales] │  ← Mobile-friendly tabs
└──────────────────────────────────────┘

Tab 1 - Overview:
  • Risk Score & Verdict
  • Token Metadata
  • Wash Trading Summary
  • Red Flags & Quick Stats

Tab 2 - Network Analysis:
  • Related Manipulated Tokens
  • Shared Wallets Modal
  • Suspicious Patterns

Tab 3 - Liquidity:
  • DEX Pool List
  • Pool Sizes & Creation Dates
  • Liquidity Concentration

Tab 4 - Whale Tracking:
  • Recent Large Transfers
  • Entry/Exit Patterns
  • Whale Wallet List
```

**Technical Approach**:
- Horizontal scroll tabs on mobile
- Swipe gestures for navigation
- Lazy-load tab content (fetch on tab click)
- Sticky header

#### New Tokens Feed Page (Planned)
**Route**: `/research/new-tokens`
**Features**:
- Platform filters (Pump.fun, Raydium, All)
- Real-time feed updated every 5 minutes
- Quick "Analyze" button per token
- Mobile-optimized table/card view

**Background Job**:
- Cron job or Railway scheduled task
- Runs every 5 minutes
- Calls `fetch_latest_tokens()` API
- Saves to `new_token_feed` table
- **API Cost**: ~864,000 C.U/month (0.58% of Level 2 plan)

---

## Architecture Overview

### Backend Stack
- **Framework**: FastAPI (Python)
- **Database**: PostgreSQL (Railway)
- **ORM**: SQLAlchemy
- **APIs**:
  - Helius (Solana transaction data)
  - Solscan Pro (transfers, markets, new tokens)
  - DexScreener (market data fallback)
  - Birdeye (market data)
- **Deployment**: Railway (auto-deploy from GitHub)

### Frontend Stack
- **Framework**: Next.js 14 (App Router)
- **Language**: TypeScript
- **Styling**: TailwindCSS
- **State**: React useState/useEffect
- **Deployment**: Vercel (auto-deploy from GitHub)

### Database Schema (Key Tables)

#### `token_analysis_reports`
Primary analysis storage with recent additions:
- `liquidity_pools` (TEXT/JSON) - DEX pool data
- `whale_movements` (TEXT/JSON) - Large transfer tracking
- `transaction_breakdown` (TEXT/JSON) - Transaction type counts
- `time_periods` (TEXT/JSON) - 24h/7d/30d analysis breakdowns
- `suspicious_wallets` (TEXT/JSON) - Wash trading wallet pairs

#### `suspicious_wallet_tokens`
Junction table for cross-token network analysis:
- `wallet_address` + `token_address` + `report_id` (unique constraint)
- `pattern_type` (repeated_pairs, bot_activity, isolated_trader)
- `trade_count` - Frequency of suspicious trades

#### `new_token_feed`
Monitors newly launched tokens:
- `platform` (pumpfun, raydium, orca)
- `created_at` - Token launch timestamp
- `initial_liquidity_usd` - Launch liquidity
- `has_been_analyzed` - Tracking flag

#### `solscan_transfer_cache`
Caches token transfer data to reduce API costs:
- Permanent storage (10-year expiry)
- Incremental updates (fetches only new transfers)
- Tracks timestamp ranges for efficient queries

---

## API Endpoints

### Research & Analysis
- `POST /api/research/analyze` - Submit token for analysis
- `GET /api/research/status/{request_id}` - Poll analysis status
- `GET /api/research/report/{report_id}` - Get full analysis report
- `GET /api/research/related-tokens/{token_address}` - Find related manipulated tokens
- `GET /api/research/shared-wallets/{token1}/{token2}` - Get shared suspicious wallets

### Future Endpoints (Planned)
- `GET /api/research/new-tokens` - Get new token feed (with pagination)
- `POST /api/research/new-tokens/refresh` - Manually trigger token discovery

---

## Migration System

All database migrations run automatically on Railway deployment via `railway.json`:

```bash
python add_logo_column.py && \
python add_solscan_cache_table.py && \
python add_transaction_analysis_columns.py && \
python add_suspicious_wallet_tokens_table.py && \
python add_liquidity_whale_columns.py && \
uvicorn main:app --host 0.0.0.0 --port $PORT
```

**Migration Pattern**:
1. Check if column/table exists
2. Skip if already present (idempotent)
3. Create if missing
4. Log success/failure

---

## Performance Optimizations

### Current Implementations
1. **Solscan Transfer Cache**: Permanent storage with incremental updates
2. **24-hour Report Cache**: Reuse recent analysis results
3. **Parallel API Calls**: Use `asyncio.gather()` where possible

### Planned Improvements
1. **Tab-Based Lazy Loading**: Only fetch data for active tab
2. **Background Jobs**: Move new token discovery off main analysis flow
3. **Database Indexing**: Optimized for common queries (already implemented)

---

## Mobile Optimization Strategy

### Current
- Responsive TailwindCSS layouts
- Mobile-friendly modals
- Touch-friendly buttons (min 44px tap targets)

### Planned
- **Horizontal scrolling tabs** with overflow indicators
- **Swipe gestures** for tab navigation (react-swipeable)
- **Bottom sheet modals** instead of centered (better mobile UX)
- **Collapsible sections** to reduce scroll depth
- **Infinite scroll** for new tokens feed

---

## API Rate Limits & Costs

### Solscan Pro API (Level 2 Plan: $199/month)
- **Monthly Allowance**: 150M C.U
- **Rate Limit**: 1,000 requests/60 seconds
- **Cost per Request**: 100 C.U (standard endpoints)

**Current Usage Estimate**:
- Token analysis: ~400 C.U per token (4 API calls)
- New token monitoring (every 5 min): ~864K C.U/month (0.58%)
- Plenty of headroom for scaling

### Helius API
- Used for transaction history analysis
- Rate limits managed via exponential backoff

---

## Git Workflow

### Branch Strategy
- `main` - Production (auto-deploys to Railway + Vercel)
- Feature branches merged directly to main (small team)

### Commit Message Format
```
<action>: <brief description>

- Bullet points of changes
- Include file locations
- Note breaking changes

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>
```

---

## Environment Variables

### Backend (Railway)
```bash
DATABASE_URL=<railway_postgres_url>
HELIUS_API_KEY=<helius_key>
SOLSCAN_API_KEY=<solscan_pro_key>
BIRDEYE_API_KEY=<birdeye_key>
```

### Frontend (Vercel)
```bash
NEXT_PUBLIC_API_URL=<backend_url>
```

---

## Common Debugging Tips

### Backend Not Fetching Liquidity/Whales
1. Check `settings.SOLSCAN_API_KEY` is set in Railway
2. Verify API key in logs: `logger.info(f"SOLSCAN_API_KEY loaded: {bool(settings.SOLSCAN_API_KEY)}")`
3. Check API response in Railway logs

### Frontend Not Showing New Data
1. Hard refresh browser (Ctrl+Shift+R)
2. Check Network tab for API call responses
3. Verify backend deployment completed on Railway

### Migration Not Running
1. Check Railway logs for migration output
2. Manually run: `railway run python add_<migration_name>.py`
3. Verify `railway.json` includes migration in startCommand

---

## Next Steps (Priority Order)

1. ✅ **Backend: Liquidity + Whale Tracking** (DONE)
2. 🚧 **Frontend: Tab Navigation** (NEXT)
   - Create TabNavigation component
   - Split research page into tab sections
   - Add lazy loading for Liquidity/Whale tabs
3. **Frontend: New Tokens Feed Page**
   - Create `/research/new-tokens` route
   - Build token feed table/cards
   - Add platform filters
4. **Backend: Background Job**
   - Set up Railway cron job or FastAPI scheduler
   - Call `fetch_latest_tokens()` every 5 minutes
   - Save to `new_token_feed` table
5. **Testing & Optimization**
   - Mobile testing on real devices
   - Performance profiling
   - API cost monitoring

---

## File Structure Reference

### Backend
```
backend/
├── api/
│   └── research.py          # Main analysis endpoints
├── services/
│   ├── helius.py            # Helius API integration
│   ├── solscan_api.py       # Solscan Pro API client
│   ├── fraud_analyzer.py    # Risk scoring logic
│   └── wash_trading_analyzer.py  # Wash trading detection
├── database/
│   └── models.py            # SQLAlchemy models
├── add_*.py                 # Migration scripts
└── railway.json             # Deployment config
```

### Frontend
```
frontend/
└── app/
    └── research/
        ├── page.tsx         # Main analysis page (needs tab refactor)
        └── new-tokens/      # (To be created)
            └── page.tsx     # New tokens feed
```

---

## Contact & Resources

- **Repository**: https://github.com/kovo-mk/solpnl
- **Backend**: Railway (auto-deploy)
- **Frontend**: Vercel (auto-deploy)
- **Solscan Docs**: https://docs.solscan.io
- **Helius Docs**: https://docs.helius.dev

---

**Last Updated**: 2026-01-18
**Current Sprint**: Tab Navigation + New Tokens Feed
