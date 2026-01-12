# SolPnL - Solana Portfolio P/L Tracker

Track your Solana trading P/L per token. Know exactly how much you made or lost on each coin.

## Features

- **Per-Token P/L** - See realized and unrealized P/L for every token you've traded
- **Cost Basis Tracking** - FIFO-based cost basis calculation
- **Trade History** - Every buy/sell with individual P/L
- **Multi-Wallet Support** - Track multiple wallets in one place
- **Clean UI** - Simple, mobile-friendly dashboard

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- Helius API key (free at https://helius.xyz)

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy env file and add your Helius API key
cp .env.example .env
# Edit .env and add HELIUS_API_KEY

# Run the server
python main.py
```

Backend runs at http://localhost:8000

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Copy env file
cp .env.example .env.local

# Run the dev server
npm run dev
```

Frontend runs at http://localhost:3000

## Usage

1. Open http://localhost:3000
2. Click "Add Wallet" and enter your Solana wallet address
3. Wait for transaction sync (may take a minute for wallets with many trades)
4. View your P/L breakdown per token!

## API Endpoints

- `POST /api/wallets` - Add a wallet to track
- `GET /api/wallets` - List tracked wallets
- `GET /api/wallets/{address}/portfolio` - Get P/L for a wallet
- `POST /api/wallets/{address}/sync` - Trigger transaction sync
- `GET /api/portfolio` - Get combined P/L across all wallets

## Tech Stack

**Backend:**
- FastAPI
- SQLAlchemy + SQLite/PostgreSQL
- Helius API for transactions

**Frontend:**
- Next.js 14
- React 18
- Tailwind CSS

## Roadmap

- [ ] Transaction history view per token
- [ ] Export to CSV
- [ ] Tax report generation
- [ ] Multi-chain support (ETH, Base)
- [ ] Mobile app (React Native)

## License

MIT
