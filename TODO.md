# SolPNL TODO & Progress Tracker

## 🚀 Current Sprint: Tab Navigation + New Tokens Feed

### In Progress
- [ ] **Frontend: Tab-Based Navigation** (NEXT UP)
  - [ ] Create reusable TabNavigation component
  - [ ] Split research page into 4 tabs: Overview, Network, Liquidity, Whales
  - [ ] Implement lazy loading (fetch data on tab click)
  - [ ] Add mobile swipe gestures
  - [ ] Test on mobile devices

### Ready to Start
- [ ] **Frontend: Liquidity Tab Content**
  - [ ] Parse `liquidity_pools` JSON from report
  - [ ] Display DEX pool cards (Raydium, Orca, etc.)
  - [ ] Show liquidity USD amounts
  - [ ] Add Solscan pool links
  - [ ] Handle empty state (no pools found)

- [ ] **Frontend: Whale Tracking Tab Content**
  - [ ] Parse `whale_movements` JSON from report
  - [ ] Display whale transfer table/cards
  - [ ] Show from/to wallets with Solscan links
  - [ ] Display USD amounts prominently
  - [ ] Add timestamp formatting
  - [ ] Sort by amount (largest first)

- [ ] **Frontend: New Tokens Feed Page** (`/research/new-tokens`)
  - [ ] Create new page route
  - [ ] Build token feed table/cards layout
  - [ ] Add platform filter buttons (All, Pump.fun, Raydium, etc.)
  - [ ] Implement pagination or infinite scroll
  - [ ] Add "Analyze" button per token
  - [ ] Show time since launch
  - [ ] Display initial liquidity

- [ ] **Backend: New Tokens Background Job**
  - [ ] Create `fetch_and_store_new_tokens.py` script
  - [ ] Call Solscan `fetch_latest_tokens()` API
  - [ ] Save/update `new_token_feed` table
  - [ ] Handle duplicates (upsert)
  - [ ] Set up Railway cron job (every 5 minutes)

- [ ] **Backend: New Tokens API Endpoint**
  - [ ] `GET /api/research/new-tokens` with pagination
  - [ ] Filter by platform parameter
  - [ ] Filter by time range (last 1h, 24h, 7d)
  - [ ] Sort by created_at DESC
  - [ ] Return has_been_analyzed flag

---

## ✅ Recently Completed (Last 24 Hours)

### 2026-01-18
- [x] Added `liquidity_pools` and `whale_movements` columns to reports
- [x] Created `new_token_feed` table with indexes
- [x] Implemented Solscan API methods:
  - [x] `fetch_token_markets()` for DEX pools
  - [x] `fetch_whale_movements()` for large transfers
  - [x] `fetch_latest_tokens()` for new token discovery
- [x] Integrated liquidity/whale fetching into analysis flow
- [x] Created migration script `add_liquidity_whale_columns.py`
- [x] Updated `railway.json` to run new migration
- [x] Deployed backend changes to Railway
- [x] Created comprehensive DEVELOPMENT.md documentation

### Earlier (Priority 5)
- [x] Cross-token wash trading network detection
- [x] `suspicious_wallet_tokens` table with junction pattern
- [x] Related tokens API endpoint
- [x] Shared wallets API endpoint
- [x] Frontend modal for viewing shared suspicious wallets

---

## 📋 Backlog (Future Enhancements)

### Performance Improvements
- [ ] Implement Redis caching for frequent queries
- [ ] Add database connection pooling optimization
- [ ] Profile frontend bundle size and code-split
- [ ] Implement service worker for offline support

### Features
- [ ] **Wallet Watchlist**: Monitor specific wallets across all tokens
- [ ] **Alert System**: Notify when new tokens match suspicious patterns
- [ ] **Portfolio Integration**: Track user's token holdings with risk scores
- [ ] **Comparison View**: Side-by-side comparison of 2-3 tokens
- [ ] **Historical Tracking**: Chart risk score changes over time
- [ ] **Export Reports**: PDF/CSV export of analysis reports
- [ ] **API Rate Limit Dashboard**: Show Solscan API usage

### UX Improvements
- [ ] Dark mode toggle (already has theme support)
- [ ] Keyboard shortcuts for power users
- [ ] Bulk analysis (upload list of token addresses)
- [ ] Search history / recent analyses
- [ ] Bookmark/favorite tokens
- [ ] Share report via link

### Mobile App (Future)
- [ ] React Native wrapper
- [ ] Push notifications for alerts
- [ ] Offline mode with cached reports

---

## 🐛 Known Issues

### Critical
- None currently

### Minor
- [ ] Long token names overflow on mobile in related tokens cards
- [ ] Transaction modal doesn't show token decimals correctly in some cases
- [ ] Occasional Helius API rate limit (handled with retry, but slow)

---

## 🧪 Testing Checklist (Before Each Deploy)

### Backend
- [ ] Run all migrations locally against test DB
- [ ] Test new API endpoints with curl/Postman
- [ ] Check Railway logs for errors after deploy
- [ ] Verify environment variables are set

### Frontend
- [ ] Build succeeds without TypeScript errors
- [ ] Test on mobile (Chrome DevTools + real device)
- [ ] Verify dark mode works
- [ ] Check all modals open/close correctly
- [ ] Test with real token address (not just mock data)

---

## 📊 Metrics to Track

### Usage
- [ ] Number of tokens analyzed per day
- [ ] API response times (P50, P95, P99)
- [ ] Error rate by endpoint
- [ ] User retention (returning users)

### Costs
- [ ] Solscan API C.U usage (current vs. budget)
- [ ] Railway compute hours
- [ ] Database storage growth rate

---

## 🎯 Goals

### Short-term (This Week)
- Complete tab-based navigation
- Deploy new tokens feed page
- Set up background job for token monitoring

### Medium-term (This Month)
- Reach 100 analyzed tokens in database
- Optimize mobile UX based on user feedback
- Add wallet watchlist feature

### Long-term (This Quarter)
- Build API for third-party integrations
- Launch alert/notification system
- Implement portfolio tracking

---

**Last Updated**: 2026-01-18
