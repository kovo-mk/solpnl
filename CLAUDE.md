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

*Last updated: January 13, 2026*
