"""API routes for SolPnL."""
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Header
from sqlalchemy.orm import Session
from loguru import logger
import base58
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError

from database import get_db, TrackedWallet, Token, Transaction, WalletTokenHolding, User
from services.helius import helius_service
from services.price import price_service
from services.pnl import PnLCalculator
from .schemas import (
    WalletCreate, WalletUpdate, WalletResponse,
    TokenResponse, TransactionResponse,
    TokenPnLResponse, PortfolioResponse, MultiWalletPortfolioResponse,
    SyncStatus
)

router = APIRouter()

# Track sync status in memory (would use Redis in production)
sync_status: dict = {}


# ============ Auth Helper ============

def get_current_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Get current user from session token (optional auth)."""
    if not authorization:
        return None

    # Expect "Bearer <token>" format
    if not authorization.startswith("Bearer "):
        return None

    token = authorization[7:]  # Remove "Bearer " prefix

    user = db.query(User).filter(User.session_token == token).first()
    if user and user.is_session_valid():
        return user
    return None


def require_auth(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> User:
    """Require authentication - raises 401 if not authenticated."""
    user = get_current_user(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


# ============ Auth Endpoints ============

@router.post("/auth/nonce")
async def get_auth_nonce(pubkey: str, db: Session = Depends(get_db)):
    """Get a nonce for signing to authenticate."""
    # Validate pubkey format
    try:
        base58.b58decode(pubkey)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid public key format")

    # Get or create user
    user = db.query(User).filter(User.pubkey == pubkey).first()
    if not user:
        user = User(pubkey=pubkey)
        db.add(user)

    # Generate nonce
    nonce = user.generate_nonce()

    # Create message to sign and store it
    message = f"Sign this message to authenticate with SolPnL.\n\nNonce: {nonce}"
    user.auth_message = message
    db.commit()

    return {
        "nonce": nonce,
        "message": message,
        "pubkey": pubkey
    }


@router.post("/auth/verify")
async def verify_signature(
    pubkey: str,
    signature: str,
    nonce: str,
    db: Session = Depends(get_db)
):
    """Verify wallet signature and create session."""
    # Get user
    user = db.query(User).filter(User.pubkey == pubkey).first()
    if not user:
        raise HTTPException(status_code=400, detail="User not found. Request a nonce first.")

    # Check nonce
    if user.auth_nonce != nonce:
        raise HTTPException(status_code=400, detail="Invalid nonce")

    if user.nonce_expires_at and datetime.now(timezone.utc) > user.nonce_expires_at:
        raise HTTPException(status_code=400, detail="Nonce expired")

    # Check that we have the stored message
    if not user.auth_message:
        raise HTTPException(status_code=400, detail="No auth message found. Request a new nonce.")

    # Verify signature
    try:
        # Decode pubkey and signature
        pubkey_bytes = base58.b58decode(pubkey)
        signature_bytes = base58.b58decode(signature)

        # Get the exact message that was signed
        message_bytes = user.auth_message.encode('utf-8')

        # Verify the signature using ed25519
        verify_key = VerifyKey(pubkey_bytes)
        verify_key.verify(message_bytes, signature_bytes)

        logger.info(f"Signature verified for {pubkey}")

    except BadSignatureError:
        logger.warning(f"Invalid signature for {pubkey}")
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        logger.warning(f"Signature verification error for {pubkey}: {e}")
        raise HTTPException(status_code=400, detail=f"Signature verification failed: {str(e)}")

    # Generate session
    session_token = user.generate_session()
    db.commit()

    # Auto-add the login wallet to tracked wallets if not already tracked
    existing_wallet = db.query(TrackedWallet).filter(
        TrackedWallet.user_id == user.id,
        TrackedWallet.address == pubkey
    ).first()

    if not existing_wallet:
        new_wallet = TrackedWallet(
            address=pubkey,
            label="My Wallet",
            user_id=user.id,
            is_active=True
        )
        db.add(new_wallet)
        db.commit()
        logger.info(f"Auto-added login wallet {pubkey} for user {user.id}")

    return {
        "session_token": session_token,
        "pubkey": pubkey,
        "expires_at": user.session_expires_at.isoformat() if user.session_expires_at else None
    }


@router.post("/auth/verify-session")
async def verify_session(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """Verify if current session is valid."""
    user = get_current_user(authorization, db)
    return {"valid": user is not None, "pubkey": user.pubkey if user else None}


@router.post("/auth/logout")
async def logout(user: User = Depends(require_auth), db: Session = Depends(get_db)):
    """Logout and invalidate session."""
    user.session_token = None
    user.session_expires_at = None
    db.commit()
    return {"message": "Logged out successfully"}


# ============ Wallet Endpoints ============

@router.post("/wallets", response_model=WalletResponse)
async def add_wallet(
    wallet: WalletCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """Add a wallet to track."""
    # Check if already exists for this user
    query = db.query(TrackedWallet).filter(TrackedWallet.address == wallet.address)
    if current_user:
        query = query.filter(TrackedWallet.user_id == current_user.id)
    else:
        query = query.filter(TrackedWallet.user_id == None)

    existing = query.first()
    if existing:
        raise HTTPException(status_code=400, detail="Wallet already being tracked")

    # Create wallet
    db_wallet = TrackedWallet(
        address=wallet.address,
        label=wallet.label,
        user_id=current_user.id if current_user else None
    )
    db.add(db_wallet)
    db.commit()
    db.refresh(db_wallet)

    # Start background sync
    background_tasks.add_task(sync_wallet_transactions, wallet.address, db_wallet.id)

    return db_wallet


@router.get("/wallets", response_model=List[WalletResponse])
async def list_wallets(
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """List tracked wallets for current user."""
    if not current_user:
        # No auth - return empty list (user must log in to see wallets)
        return []

    # Show only wallets belonging to this user
    query = db.query(TrackedWallet).filter(
        TrackedWallet.is_active == True,
        TrackedWallet.user_id == current_user.id
    )

    wallets = query.all()
    return wallets


@router.get("/wallets/{address}", response_model=WalletResponse)
async def get_wallet(
    address: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """Get a specific wallet."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")

    wallet = db.query(TrackedWallet).filter(
        TrackedWallet.address == address,
        TrackedWallet.user_id == current_user.id
    ).first()

    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    return wallet


@router.patch("/wallets/{address}", response_model=WalletResponse)
async def update_wallet(
    address: str,
    updates: WalletUpdate,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """Update wallet label or status."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")

    wallet = db.query(TrackedWallet).filter(
        TrackedWallet.address == address,
        TrackedWallet.user_id == current_user.id
    ).first()

    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")

    if updates.label is not None:
        wallet.label = updates.label
    if updates.is_active is not None:
        wallet.is_active = updates.is_active

    db.commit()
    db.refresh(wallet)
    return wallet


@router.delete("/wallets/{address}")
async def delete_wallet(
    address: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """Remove a wallet from tracking."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")

    wallet = db.query(TrackedWallet).filter(
        TrackedWallet.address == address,
        TrackedWallet.user_id == current_user.id
    ).first()

    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")

    db.delete(wallet)
    db.commit()
    return {"message": "Wallet deleted"}


# ============ Sync Endpoints ============

@router.post("/wallets/{address}/sync")
async def sync_wallet(
    address: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Trigger a sync for a wallet."""
    wallet = db.query(TrackedWallet).filter(TrackedWallet.address == address).first()
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")

    # Start background sync
    background_tasks.add_task(sync_wallet_transactions, address, wallet.id)

    return {"message": "Sync started", "wallet": address}


@router.get("/wallets/{address}/sync/status", response_model=SyncStatus)
async def get_sync_status(address: str):
    """Get sync status for a wallet."""
    status = sync_status.get(address, {
        "wallet_address": address,
        "status": "unknown",
        "transactions_fetched": 0,
        "swaps_found": 0
    })
    return SyncStatus(**status)


async def sync_wallet_transactions(wallet_address: str, wallet_id: int):
    """Background task to sync wallet transactions."""
    from database.connection import SessionLocal

    sync_status[wallet_address] = {
        "wallet_address": wallet_address,
        "status": "syncing",
        "transactions_fetched": 0,
        "swaps_found": 0,
        "message": "Fetching transactions..."
    }

    db = SessionLocal()

    try:
        # Fetch swaps from Helius
        async def progress_callback(fetched, swaps):
            sync_status[wallet_address]["transactions_fetched"] = fetched
            sync_status[wallet_address]["swaps_found"] = swaps

        swaps = await helius_service.fetch_all_swaps(
            wallet_address,
            max_transactions=1000,
            progress_callback=progress_callback
        )

        sync_status[wallet_address]["message"] = "Processing transactions..."

        # Get SOL price for USD calculations
        sol_price = await price_service.get_sol_price()

        # Get unique tokens and fetch metadata
        token_mints = set(swap["token_mint"] for swap in swaps)
        token_ids = {}

        for mint in token_mints:
            token = db.query(Token).filter(Token.address == mint).first()
            if not token:
                # Fetch metadata
                metadata = await helius_service.get_token_metadata(mint)
                token = Token(
                    address=mint,
                    symbol=metadata.get("symbol", "???") if metadata else "???",
                    name=metadata.get("name", "Unknown") if metadata else "Unknown",
                    decimals=metadata.get("decimals", 9) if metadata else 9,
                    logo_url=metadata.get("logo_url") if metadata else None
                )
                db.add(token)
                db.commit()
                db.refresh(token)

            token_ids[mint] = token.id

        # Get current prices for all tokens
        prices = await price_service.get_multiple_token_prices(list(token_mints))

        # Update token prices
        for mint, price in prices.items():
            if price:
                token = db.query(Token).filter(Token.address == mint).first()
                if token:
                    token.current_price_usd = price
                    token.price_updated_at = datetime.utcnow()
        db.commit()

        # Process transactions and calculate P/L
        calculator = PnLCalculator(db)

        # Build sol_prices map (using current price as approximation)
        sol_prices = {swap["signature"]: sol_price for swap in swaps}

        # Process all transactions
        holdings_data = calculator.process_transactions(swaps, sol_prices)

        # Save transactions and update holdings
        for swap in swaps:
            # Check if transaction already exists
            existing = db.query(Transaction).filter(
                Transaction.signature == swap["signature"]
            ).first()

            if not existing:
                tx = Transaction(
                    signature=swap["signature"],
                    wallet_id=wallet_id,
                    token_id=token_ids.get(swap["token_mint"]),
                    tx_type=swap["tx_type"],
                    amount_token=swap["amount_token"],
                    amount_sol=swap["amount_sol"],
                    price_per_token=swap["price_per_token"],
                    price_usd=swap["price_per_token"] * sol_price if swap["price_per_token"] else None,
                    dex_name=swap["dex_name"],
                    block_time=swap["block_time"]
                )
                db.add(tx)

        db.commit()

        # Update holdings
        for token_mint, data in holdings_data.items():
            token_id = token_ids.get(token_mint)
            if not token_id:
                continue

            holding = db.query(WalletTokenHolding).filter(
                WalletTokenHolding.wallet_id == wallet_id,
                WalletTokenHolding.token_id == token_id
            ).first()

            if not holding:
                holding = WalletTokenHolding(
                    wallet_id=wallet_id,
                    token_id=token_id
                )
                db.add(holding)

            holding.current_balance = data["current_balance"]
            holding.total_cost_sol = data["total_cost_sol"]
            holding.avg_buy_price = data.get("avg_buy_price_sol", 0)
            holding.total_bought = data["total_bought"]
            holding.total_sold = data["total_sold"]
            holding.total_buy_sol = data["total_buy_sol"]
            holding.total_sell_sol = data["total_sell_sol"]
            holding.realized_pnl_sol = data["realized_pnl_sol"]
            holding.realized_pnl_usd = data["realized_pnl_usd"]
            holding.first_buy_at = data["first_trade"]
            holding.last_trade_at = data["last_trade"]

        # Update wallet sync time
        wallet = db.query(TrackedWallet).filter(TrackedWallet.id == wallet_id).first()
        if wallet:
            wallet.last_synced = datetime.utcnow()

        db.commit()

        sync_status[wallet_address] = {
            "wallet_address": wallet_address,
            "status": "completed",
            "transactions_fetched": sync_status[wallet_address]["transactions_fetched"],
            "swaps_found": len(swaps),
            "message": f"Synced {len(swaps)} swaps across {len(token_mints)} tokens"
        }

    except Exception as e:
        logger.error(f"Error syncing wallet {wallet_address}: {e}")
        sync_status[wallet_address] = {
            "wallet_address": wallet_address,
            "status": "error",
            "transactions_fetched": 0,
            "swaps_found": 0,
            "message": str(e)
        }
    finally:
        db.close()


# ============ Portfolio Endpoints ============

@router.get("/wallets/{address}/portfolio", response_model=PortfolioResponse)
async def get_wallet_portfolio(address: str, db: Session = Depends(get_db)):
    """Get P/L portfolio for a single wallet."""
    wallet = db.query(TrackedWallet).filter(TrackedWallet.address == address).first()
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")

    # Get all holdings from transaction history
    holdings = db.query(WalletTokenHolding).filter(
        WalletTokenHolding.wallet_id == wallet.id
    ).all()

    # Get current prices for tracked tokens
    token_mints = []
    for holding in holdings:
        token = db.query(Token).filter(Token.id == holding.token_id).first()
        if token:
            token_mints.append(token.address)

    # Fetch actual on-chain balances (source of truth for current holdings)
    actual_balances = {}
    try:
        balance_data = await helius_service.get_wallet_balances(address)
        for token_balance in balance_data.get("tokens", []):
            mint = token_balance.get("mint")
            amount = token_balance.get("amount", 0)
            if mint and amount > 0:
                actual_balances[mint] = amount
                # Also add to token_mints if not already tracked
                if mint not in token_mints:
                    token_mints.append(mint)
    except Exception as e:
        logger.warning(f"Failed to fetch on-chain balances for {address}: {e}")
        # Fall back to transaction-calculated balances

    prices = await price_service.get_multiple_token_prices(token_mints)
    sol_price = await price_service.get_sol_price()

    # Calculate P/L using the calculator with actual balances
    calculator = PnLCalculator(db)
    portfolio = await calculator.get_portfolio_pnl(
        wallet.id, prices, sol_price, actual_balances=actual_balances
    )

    return PortfolioResponse(
        wallet_address=wallet.address,
        wallet_label=wallet.label,
        total_value_usd=portfolio.total_value_usd,
        total_cost_sol=portfolio.total_cost_sol,
        total_unrealized_pnl_usd=portfolio.total_unrealized_pnl_usd,
        total_realized_pnl_sol=portfolio.total_realized_pnl_sol,
        total_realized_pnl_usd=portfolio.total_realized_pnl_usd,
        token_count=portfolio.token_count,
        tokens=[TokenPnLResponse(
            token_address=t.token_address,
            token_symbol=t.token_symbol,
            token_name=t.token_name,
            token_logo=t.token_logo,
            current_balance=t.current_balance,
            avg_buy_price_sol=t.avg_buy_price_sol,
            total_cost_sol=t.total_cost_sol,
            current_price_usd=t.current_price_usd,
            current_value_usd=t.current_value_usd,
            unrealized_pnl_sol=t.unrealized_pnl_sol,
            unrealized_pnl_usd=t.unrealized_pnl_usd,
            unrealized_pnl_percent=t.unrealized_pnl_percent,
            realized_pnl_sol=t.realized_pnl_sol,
            realized_pnl_usd=t.realized_pnl_usd,
            total_bought=t.total_bought,
            total_sold=t.total_sold,
            total_buy_sol=t.total_buy_sol,
            total_sell_sol=t.total_sell_sol,
            trade_count=t.trade_count,
            first_trade=t.first_trade,
            last_trade=t.last_trade
        ) for t in portfolio.tokens],
        last_synced=wallet.last_synced
    )


@router.get("/portfolio", response_model=MultiWalletPortfolioResponse)
async def get_all_portfolios(db: Session = Depends(get_db)):
    """Get combined P/L across all tracked wallets."""
    wallets = db.query(TrackedWallet).filter(TrackedWallet.is_active == True).all()

    all_portfolios = []
    total_value = 0.0
    total_unrealized = 0.0
    total_realized = 0.0
    all_tokens = set()

    for wallet in wallets:
        try:
            portfolio = await get_wallet_portfolio(wallet.address, db)
            all_portfolios.append(portfolio)
            total_value += portfolio.total_value_usd
            total_unrealized += portfolio.total_unrealized_pnl_usd
            total_realized += portfolio.total_realized_pnl_usd
            all_tokens.update(t.token_address for t in portfolio.tokens)
        except Exception as e:
            logger.error(f"Error getting portfolio for {wallet.address}: {e}")

    return MultiWalletPortfolioResponse(
        total_value_usd=total_value,
        total_unrealized_pnl_usd=total_unrealized,
        total_realized_pnl_usd=total_realized,
        wallet_count=len(wallets),
        token_count=len(all_tokens),
        wallets=all_portfolios
    )


# ============ Transaction Endpoints ============

@router.get("/wallets/{address}/transactions", response_model=List[TransactionResponse])
async def get_wallet_transactions(
    address: str,
    token: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """Get transactions for a wallet, optionally filtered by token."""
    wallet = db.query(TrackedWallet).filter(TrackedWallet.address == address).first()
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")

    query = db.query(Transaction).filter(Transaction.wallet_id == wallet.id)

    if token:
        token_obj = db.query(Token).filter(Token.address == token).first()
        if token_obj:
            query = query.filter(Transaction.token_id == token_obj.id)

    transactions = query.order_by(
        Transaction.block_time.desc()
    ).offset(offset).limit(limit).all()

    # Add token info to each transaction
    result = []
    for tx in transactions:
        token_obj = db.query(Token).filter(Token.id == tx.token_id).first()
        tx_dict = {
            "id": tx.id,
            "signature": tx.signature,
            "tx_type": tx.tx_type,
            "amount_token": tx.amount_token,
            "amount_sol": tx.amount_sol,
            "price_per_token": tx.price_per_token,
            "price_usd": tx.price_usd,
            "realized_pnl_sol": tx.realized_pnl_sol,
            "realized_pnl_usd": tx.realized_pnl_usd,
            "dex_name": tx.dex_name,
            "block_time": tx.block_time,
            "token": TokenResponse(
                address=token_obj.address,
                symbol=token_obj.symbol,
                name=token_obj.name,
                decimals=token_obj.decimals,
                logo_url=token_obj.logo_url,
                current_price_usd=token_obj.current_price_usd
            ) if token_obj else None
        }
        result.append(tx_dict)

    return result


# ============ Balance Endpoints ============

@router.get("/wallets/{address}/balances")
async def get_wallet_balances(address: str, db: Session = Depends(get_db)):
    """Get actual on-chain balances for a wallet (like Phantom shows).

    This endpoint works for any Solana wallet address - the wallet doesn't
    need to be tracked. Useful for read-only share links.
    """
    # Note: We don't require the wallet to be tracked anymore
    # This allows read-only viewing of any wallet

    # Fetch actual balances from chain
    balances = await helius_service.get_wallet_balances(address)
    sol_price = await price_service.get_sol_price()

    # Get prices for all tokens
    token_mints = [t["mint"] for t in balances.get("tokens", [])]
    prices = await price_service.get_multiple_token_prices(token_mints) if token_mints else {}

    # Calculate SOL value
    sol_balance = balances.get("sol_balance", 0)
    sol_value_usd = sol_balance * sol_price

    # Filter out dust tokens (worth less than $0.01)
    MIN_TOKEN_VALUE_USD = 0.01

    tokens_with_value = []
    total_token_value_usd = 0.0
    verified_token_value_usd = 0.0

    # Add SOL as the first token in the list (always verified)
    sol_token = {
        "mint": "So11111111111111111111111111111111111111112",  # Wrapped SOL mint
        "symbol": "SOL",
        "name": "Solana",
        "logo_url": "https://raw.githubusercontent.com/solana-labs/token-list/main/assets/mainnet/So11111111111111111111111111111111111111112/logo.png",
        "balance": sol_balance,
        "price_usd": sol_price,
        "value_usd": sol_value_usd,
        "is_verified": True,  # SOL is always verified
        "is_hidden": False  # SOL is never hidden
    }
    tokens_with_value.append(sol_token)
    verified_token_value_usd += sol_value_usd

    for token_data in balances.get("tokens", []):
        mint = token_data["mint"]
        balance = token_data["balance"]

        # Get token metadata from DB or fetch
        token = db.query(Token).filter(Token.address == mint).first()
        if not token:
            # Fetch metadata
            metadata = await helius_service.get_token_metadata(mint)
            token_symbol = metadata.get("symbol", "???") if metadata else "???"
            token_name = metadata.get("name", "Unknown") if metadata else "Unknown"
            token_logo = metadata.get("logo_url") if metadata else None
            is_verified = False
            is_hidden = False

            # Create token in DB so user can verify it later
            token = Token(
                address=mint,
                symbol=token_symbol,
                name=token_name,
                logo_url=token_logo,
                is_verified=False,
                is_hidden=False
            )
            db.add(token)
            db.commit()
            db.refresh(token)
        else:
            token_symbol = token.symbol or "???"
            token_name = token.name or "Unknown"
            token_logo = token.logo_url
            is_verified = token.is_verified or False
            is_hidden = token.is_hidden or False

        # Check for known stablecoins (auto-verify)
        STABLECOIN_MINTS = {
            "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": "USDC",
            "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB": "USDT",
        }
        if mint in STABLECOIN_MINTS:
            is_verified = True
            # Also update DB if not already verified
            if not token.is_verified:
                token.is_verified = True
                db.commit()

        price_usd = prices.get(mint)
        value_usd = balance * price_usd if price_usd else None

        # Auto-verify tokens that have a valid price (real tradeable tokens)
        # Only unverified/non-hidden tokens get auto-verified
        if price_usd is not None and price_usd > 0 and not is_hidden and not is_verified:
            is_verified = True
            # Update DB so it persists
            if token and not token.is_verified:
                token.is_verified = True
                db.commit()

        # Filter out dust tokens (worth less than $0.01)
        if value_usd is not None and value_usd < MIN_TOKEN_VALUE_USD:
            continue

        # Track values for totals
        if value_usd is not None:
            total_token_value_usd += value_usd
            if is_verified:
                verified_token_value_usd += value_usd

        tokens_with_value.append({
            "mint": mint,
            "symbol": token_symbol,
            "name": token_name,
            "logo_url": token_logo,
            "balance": balance,
            "price_usd": price_usd,
            "value_usd": value_usd,
            "is_verified": is_verified,
            "is_hidden": is_hidden
        })

    # Sort by value (highest first), but keep SOL at the top
    sol_entry = tokens_with_value[0]
    other_tokens = tokens_with_value[1:]
    other_tokens.sort(key=lambda x: x.get("value_usd") or 0, reverse=True)
    tokens_with_value = [sol_entry] + other_tokens

    return {
        "wallet_address": address,
        "sol_balance": sol_balance,
        "sol_price_usd": sol_price,
        "sol_value_usd": sol_value_usd,
        "tokens": tokens_with_value,
        "total_token_value_usd": total_token_value_usd,
        "verified_token_value_usd": verified_token_value_usd,
        "total_portfolio_value_usd": verified_token_value_usd  # Only verified tokens count
    }


@router.patch("/tokens/{mint}/verify")
async def toggle_token_verification(mint: str, db: Session = Depends(get_db)):
    """Toggle verification status of a token."""
    token = db.query(Token).filter(Token.address == mint).first()
    if not token:
        raise HTTPException(status_code=404, detail="Token not found")

    # Toggle verification
    token.is_verified = not token.is_verified
    db.commit()
    db.refresh(token)

    return {
        "mint": token.address,
        "symbol": token.symbol,
        "is_verified": token.is_verified
    }


@router.patch("/tokens/{mint}/hide")
async def toggle_token_hidden(mint: str, db: Session = Depends(get_db)):
    """Toggle hidden status of a token (for scam airdrops)."""
    token = db.query(Token).filter(Token.address == mint).first()
    if not token:
        raise HTTPException(status_code=404, detail="Token not found")

    # Toggle hidden
    token.is_hidden = not token.is_hidden
    # If hiding, also unverify
    if token.is_hidden:
        token.is_verified = False
    db.commit()
    db.refresh(token)

    return {
        "mint": token.address,
        "symbol": token.symbol,
        "is_hidden": token.is_hidden,
        "is_verified": token.is_verified
    }


# ============ Health Check ============

@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}
