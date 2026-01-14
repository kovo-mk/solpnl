"""
Debug script to analyze USDC transaction history and cost basis.
Usage: python debug_usdc.py <wallet_address>
"""
import sys
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.models import TrackedWallet, Token, Transaction, WalletTokenHolding
from datetime import datetime

# Get database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./solpnl.db")

# Create engine and session
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
db = Session()

def debug_usdc(wallet_address: str):
    """Analyze USDC transactions for a wallet."""

    # Find wallet
    wallet = db.query(TrackedWallet).filter(TrackedWallet.address == wallet_address).first()
    if not wallet:
        print(f"❌ Wallet not found: {wallet_address}")
        return

    print(f"\n📊 Analyzing USDC for wallet: {wallet.label or wallet_address}")
    print("=" * 80)

    # Find USDC token
    usdc = db.query(Token).filter(Token.symbol == "USDC").first()
    if not usdc:
        print("❌ USDC token not found in database")
        return

    print(f"\n💰 Token Info:")
    print(f"   Symbol: {usdc.symbol}")
    print(f"   Name: {usdc.name}")
    print(f"   Address: {usdc.address}")
    print(f"   Current Price: ${usdc.current_price_usd or 0:.4f}")

    # Get holding summary
    holding = db.query(WalletTokenHolding).filter(
        WalletTokenHolding.wallet_id == wallet.id,
        WalletTokenHolding.token_id == usdc.id
    ).first()

    if holding:
        print(f"\n📈 Holding Summary:")
        print(f"   Current Balance: {holding.current_balance:.2f} USDC")
        print(f"   Avg Buy Price: {holding.avg_buy_price:.6f} SOL")
        if holding.avg_buy_price == 0:
            print(f"   ⚠️  WARNING: Zero cost basis = 100% profit!")
        print(f"   Total Cost: {holding.total_cost_sol:.4f} SOL")
        print(f"   Total Bought: {holding.total_bought:.2f}")
        print(f"   Total Sold: {holding.total_sold:.2f}")
        print(f"   Realized P/L: ${holding.realized_pnl_usd:.2f}")
    else:
        print("\n❌ No holding data found for USDC")

    # Get all transactions
    transactions = db.query(Transaction).filter(
        Transaction.wallet_id == wallet.id,
        Transaction.token_id == usdc.id
    ).order_by(Transaction.block_time.asc()).all()

    print(f"\n📜 Transactions ({len(transactions)} total):")
    print("-" * 80)

    if not transactions:
        print("   No transactions found")
        return

    # Print header
    print(f"{'Date':<12} {'Type':<15} {'Category':<12} {'Amount':<12} {'SOL':<10} {'Price/Token':<12}")
    print("-" * 80)

    for tx in transactions:
        date_str = tx.block_time.strftime("%Y-%m-%d") if tx.block_time else "N/A"
        amount_str = f"{tx.amount_token:.2f}"
        sol_str = f"{tx.amount_sol:.4f}"
        price_str = f"{tx.price_per_token:.6f}" if tx.price_per_token else "0.000000"

        # Highlight zero-cost transactions
        warning = " ⚠️ " if tx.price_per_token == 0 and tx.tx_type in ["buy", "transfer_in"] else ""

        print(f"{date_str:<12} {tx.tx_type:<15} {tx.category or 'N/A':<12} {amount_str:<12} {sol_str:<10} {price_str:<12}{warning}")

    # Analysis
    print("\n" + "=" * 80)
    print("🔍 Analysis:")
    print("-" * 80)

    # Check for zero-cost acquisitions
    zero_cost_txs = [tx for tx in transactions if tx.price_per_token == 0 and tx.tx_type in ["buy", "transfer_in", "airdrop"]]
    if zero_cost_txs:
        print(f"\n⚠️  Found {len(zero_cost_txs)} zero-cost acquisition(s):")
        for tx in zero_cost_txs:
            print(f"   - {tx.tx_type}: {tx.amount_token:.2f} USDC on {tx.block_time.strftime('%Y-%m-%d') if tx.block_time else 'N/A'}")
            if tx.tx_type == "transfer_in":
                print(f"     → This was a TRANSFER from another wallet (gets $0 cost basis)")
            elif tx.tx_type == "airdrop":
                print(f"     → This was an AIRDROP (gets $0 cost basis)")
            elif tx.tx_type == "buy":
                print(f"     → This was a BUY but price = $0 (parser may have missed it)")

    # Check for buys with proper cost basis
    real_buys = [tx for tx in transactions if tx.price_per_token and tx.price_per_token > 0 and tx.tx_type == "buy"]
    if real_buys:
        print(f"\n✅ Found {len(real_buys)} purchase(s) with valid cost basis:")
        for tx in real_buys:
            print(f"   - Bought {tx.amount_token:.2f} USDC at {tx.price_per_token:.6f} SOL/token")

    # Check for sells
    sells = [tx for tx in transactions if tx.tx_type == "sell"]
    if sells:
        print(f"\n💸 Found {len(sells)} sale(s):")
        for tx in sells:
            pnl_str = f"${tx.realized_pnl_usd:.2f}" if tx.realized_pnl_usd else "N/A"
            print(f"   - Sold {tx.amount_token:.2f} USDC, P/L: {pnl_str}")

    print("\n" + "=" * 80)
    print("💡 Explanation:")
    print("-" * 80)
    if holding and holding.avg_buy_price == 0:
        print("""
Your USDC shows a $0 cost basis (avg_buy_price = 0.0000 SOL). This happens when:

  1. You TRANSFERRED USDC into this wallet from another wallet/exchange
     → The receiving wallet doesn't know what you paid originally
     → So it gets $0 cost basis (conservative accounting)
     → Result: Current value shows as 100% profit

  2. You received USDC as an AIRDROP or payment
     → Free tokens get $0 cost basis
     → Result: Any sale is 100% profit

This is EXPECTED BEHAVIOR for stablecoins that were transferred in. The P/L is
technically correct (you didn't pay SOL for it in THIS wallet), but it may be
misleading since USDC is always $1.

Possible solutions:
  - Track the sending wallet separately (it would show the loss)
  - Special handling for stablecoins to suppress unrealized P/L
  - Manual cost basis adjustment (would require additional feature)
""")
    else:
        print("\n✅ USDC has a valid cost basis - P/L calculations should be accurate")

    print("=" * 80)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python debug_usdc.py <wallet_address>")
        sys.exit(1)

    wallet_address = sys.argv[1]
    try:
        debug_usdc(wallet_address)
    finally:
        db.close()
