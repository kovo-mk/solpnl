# SolPnL - Claude Context File

> This file is automatically read by Claude Code at session start. It contains project context, architecture, and recent changes to help maintain continuity across devices and sessions.

## Project Overview

**SolPnL** is a Solana portfolio profit/loss tracker that allows users to:
- Connect their Solana wallet for authentication
- Track multiple wallet addresses
- View real-time token balances and USD values
- Calculate realized and unrealized P/L from swap transactions
- Mark tokens as verified (counted in portfolio value) or hidden (spam airdrops)

**Live URLs:**
- Frontend: https://solpnl.vercel.app (Vercel)
- Backend: https://solpnl-production.up.railway.app (Railway)
- Repository: https://github.com/kovo-mk/solpnl

---

## Tech Stack

### Frontend (`/frontend`)
- **Framework:** Next.js 14 (App Router)
- **Styling:** Tailwind CSS with `dark:` class-based theme switching
- **Wallet:** @solana/wallet-adapter-react (Phantom, Solflare, etc.)
- **State:** React Context (ThemeContext, WalletContext)

### Backend (`/backend`)
- **Framework:** FastAPI (Python)
- **Database:** PostgreSQL (Railway) / SQLite (local dev)
- **ORM:** SQLAlchemy
- **Auth:** Ed25519 signature verification with session tokens
- **External APIs:** Helius (Solana RPC), Jupiter (prices), DexScreener

---

## Project Structure

```
solpnl/
├── frontend/
│   ├── app/
│   │   ├── page.tsx          # Main portfolio page
│   │   ├── pnl/page.tsx      # P/L breakdown page
│   │   ├── globals.css       # Theme variables, scrollbars
│   │   └── layout.tsx        # Root layout with providers
│   ├── components/
│   │   ├── TokenHoldingsList.tsx   # Token list with verify/hide
│   │   ├── PortfolioSummary.tsx    # Wallet stats card
│   │   ├── TokenPnLCard.tsx        # Individual token P/L
│   │   ├── AddWalletModal.tsx      # Add wallet form
│   │   └── WalletConnectButton.tsx # Solana wallet connect
│   ├── contexts/
│   │   └── ThemeContext.tsx  # Light/dark mode state
│   └── lib/
│       ├── api.ts            # Backend API client
│       └── utils.ts          # Formatting helpers
│
├── backend/
│   ├── api/
│   │   └── routes.py         # All API endpoints
│   ├── database/
│   │   ├── models.py         # SQLAlchemy models
│   │   └── connection.py     # DB setup + migrations
│   ├── services/
│   │   ├── helius.py         # Solana RPC calls
│   │   ├── jupiter.py        # Price fetching
│   │   └── pnl.py            # P/L calculations
│   ├── config.py             # Environment settings
│   └── main.py               # FastAPI app entry
│
└── CLAUDE.md                 # This file
```

---

## Key Database Models

### User
- `pubkey` - Solana wallet public key (unique identifier)
- `auth_nonce` - One-time nonce for signature verification
- `auth_message` - Exact message that was signed (stored for verification)
- `session_token` - Current session token
- `session_expires_at` - Session expiration

### TrackedWallet
- `address` - Solana wallet address being tracked
- `user_id` - Owner (for user isolation)
- `label` - User-friendly name

### Token
- `mint` - Token mint address
- `is_verified` - Counts toward portfolio value
- `is_hidden` - Hidden from view (spam airdrops)

### Transaction
- Stores swap transactions (buys/sells) for P/L calculation

---

## Authentication Flow

1. Frontend calls `POST /api/auth/nonce` with wallet pubkey
2. Backend generates nonce, creates message, stores in `user.auth_message`
3. Frontend prompts wallet to sign the exact message
4. Frontend calls `POST /api/auth/verify` with pubkey, nonce, signature
5. Backend retrieves stored `auth_message`, verifies signature with Ed25519
6. Backend generates session token, returns to frontend
7. Frontend stores session in localStorage, sends in `Authorization` header

**Critical:** The exact message must be stored in DB because timestamps would change between nonce request and verification.

---

## Theme System

- **Dark mode:** Purple/green Solana brand colors (`sol-purple`, `sol-green`)
- **Light mode:** Clean white/black/blue professional theme
- Toggle stored in localStorage, respects system preference as fallback
- ThemeContext provides SSR-safe default to prevent hydration errors

**Light mode pattern:**
```tsx
className="bg-white dark:bg-gray-800 text-gray-900 dark:text-white border-gray-200 dark:border-gray-700"
```

**Accent colors:**
- Light: `bg-blue-600`, `text-blue-600`
- Dark: `bg-sol-purple`, `text-sol-purple`

---

## Recent Changes (January 2026)

### Session: January 14, 2026 - Token-to-Token Swap P/L Investigation (ONGOING)

**Problem:** VXM (Volt) token shows incorrect P/L compared to Jupiter:
- Jupiter: +$4,444.76 realized P/L
- Our system: -$0.29 (or varies wildly with each attempt)
- User wallet: `56YahmTzWix9nAYaeRKDMHZhyHZe6diU1tcgkBXA5iVt`
- VXM mint: `FRsV3m924aGpLMuEekoo3JkkMt1oopaM4JY9ki5YLXrp`

**Root Cause:** VXM swaps are token-to-token (e.g., XVM ↔ USDC), not XVM ↔ SOL. Our parser only tracked SOL swaps initially.

**Work Completed:**
1. ✅ Enhanced Helius parser to detect token-to-token swaps by checking for 2+ token transfers
2. ✅ Added `other_token_mint` and `other_token_amount` fields to track the "other side" of swaps
3. ✅ Calculate USD value from other token's current price (e.g., USDC at $1.00)
4. ✅ Generate synthetic `price_sol` by dividing USD price by current SOL price
5. ✅ Fixed timezone-aware datetime bug (changed `datetime.utcfromtimestamp` to `datetime.fromtimestamp(tz=timezone.utc)`)
6. ✅ Refined swap detection to only trigger when native SOL transfers < 0.01 SOL

**Files Modified:**
- `backend/services/helius.py` - Enhanced transaction parser
- `backend/api/routes.py` - Added USD price calculation for token-to-token swaps
- `backend/services/pnl.py` - Extract other_token fields

**Commits:**
- `8b8869f` - Only detect token-to-token swaps when native transfers are minimal
- `f4ef666` - Detect token-to-token swaps by checking for 2+ token transfers
- `5b702df` - Detect token-to-token swaps for all transaction categories
- `a7eafee` - Fix timezone-aware datetime comparison in sync
- `419739d` - Re-enable database cleanup for full resyncs

**Current Blocker:**
Database sync failing with "duplicate key value violates unique constraint". The database cleanup (delete old transactions before re-insert) isn't working correctly, causing insert failures mid-sync.

**Key Technical Insight - Historical USD Values:**
We investigated whether historical USD values are available from various APIs:

1. **Solana RPC:** Does NOT provide prices - only token amounts and transaction data
2. **Helius Enhanced API:** Provides transaction data (token transfers, amounts, timestamps) but NO USD/price values
3. **Current approach:** Using current token prices as approximations (likely same as Jupiter)

**For token-to-token swaps (e.g., XVM → USDC):**
- ✅ We CAN get accurate USD value: If sold for 980 USDC, that's exactly $980 (USDC ≈ $1)
- ❌ We CANNOT get accurate SOL-denominated cost basis without historical SOL prices
- Using current SOL price ($144) to calculate synthetic price_sol creates inaccuracies when historical SOL was $200+

**Paid API Options Considered:**
- **Birdeye Pro:** ~$49-199/month, has historical OHLCV price data, good for liquid tokens
- **Solscan Pro:** Unknown pricing (need to contact), unclear if API returns historical USD values
- **Helius Premium:** Need to check what additional data they provide

**Next Steps (for Desktop session):**
1. Fix database sync duplicate key error
2. Decide on P/L calculation approach:
   - Option A: Accept current prices for approximation (like Jupiter likely does)
   - Option B: USD-only P/L (no SOL conversion) - more accurate
   - Option C: Pay for Birdeye historical price data
3. Test if VXM P/L matches Jupiter after fixes

**Questions to Answer:**
- How exactly does Jupiter calculate their P/L? (Assumption: current prices, but unconfirmed)
- Should we prioritize USD P/L over SOL P/L?
- Is $200/month API cost acceptable for historical price accuracy?

### Session: January 14, 2026 (Laptop Setup)

**1. Fixed Light Mode Button Readability**
- Problem: Wallet connect button and Add Wallet modal were unreadable in light mode (dark backgrounds on light theme)
- Fix: Updated both components with proper light/dark mode styling
- Files: `frontend/components/WalletConnectButton.tsx`, `frontend/components/AddWalletModal.tsx`
- Changes:
  - WalletConnectButton: gray-100 bg with gray-900 text + border in light mode
  - AddWalletModal: white bg with blue accents, gray-50 input fields, proper contrast
  - All states (loading, signing in, connected, dropdown) now readable in both modes

**2. Verified Cloud Deployment Configuration**
- Confirmed `NEXT_PUBLIC_API_URL` environment variable is set in Vercel
- Points to Railway backend: `https://solpnl-production.up.railway.app/api`
- No local setup required - everything runs 100% in the cloud

### Session: January 13, 2026

**1. Fixed Wallet Authentication (400 Bad Request)**
- Problem: Login stuck on "Signing in..." - signature verification was failing
- Root cause: Message timestamp changed between nonce and verify calls; signature was never actually verified
- Fix: Store exact message in `user.auth_message`, call `verify_key.verify()` properly
- Files: `backend/api/routes.py`, `backend/database/models.py`, `backend/database/connection.py`

**2. Fixed ThemeContext SSR Error**
- Problem: Vercel build failed with "useTheme must be used within ThemeProvider"
- Fix: Provide default context value instead of undefined
- File: `frontend/contexts/ThemeContext.tsx`

**3. Redesigned Light Mode**
- Problem: Gray light mode was hard to read
- Fix: Complete redesign with white backgrounds, blue accents, proper contrast
- Files: `frontend/app/globals.css`, `frontend/app/page.tsx`, `frontend/components/TokenHoldingsList.tsx`, `frontend/components/PortfolioSummary.tsx`, `frontend/components/TokenPnLCard.tsx`

---

## Known Issues / TODO

- [ ] P/L page (`/pnl`) may need light mode styling updates (header/nav duplicated from page.tsx)
- [ ] Consider adding loading skeletons for better UX

---

## Development

### Local Setup
```bash
# Frontend
cd frontend
npm install
npm run dev  # http://localhost:3000

# Backend
cd backend
pip install -r requirements.txt
python main.py  # http://localhost:8000
```

### Environment Variables

**Frontend** (`.env.local`):
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

**Backend** (`.env`):
```
DATABASE_URL=sqlite:///./solpnl.db  # or postgres://...
HELIUS_API_KEY=your_key
JWT_SECRET=your_secret
```

---

## Git Workflow

Recent commits:
```
b6e9f2d Update TokenPnLCard for light mode styling
e67a57f Add CLAUDE.md for cross-device session continuity
7ea9b28 Update PortfolioSummary and TokenHoldingsList for light mode
da605e5 Redesign light mode with clean white/black/blue theme
ea1e819 Add database migration for auth_message column
```

---

## Notes for Claude

- User prefers automated git commits/pushes - working one-handed
- Light mode uses blue accents, dark mode uses purple/green Solana colors
- Always use `dark:` prefix for dark mode styles, light mode is default
- Database migrations run automatically via `init_db()` -> `run_migrations()`
- Frontend auto-deploys to Vercel on push, backend on Railway

---

*Last updated: January 14, 2026*
