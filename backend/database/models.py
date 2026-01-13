"""Database models for SolPnL portfolio tracker."""
import secrets
from datetime import datetime, timedelta, timezone
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey,
    Boolean, Text, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class User(Base):
    """User accounts identified by Solana wallet public key."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pubkey = Column(String(255), unique=True, nullable=False, index=True)  # Solana pubkey

    # Auth nonce for signature verification (one-time use)
    auth_nonce = Column(String(255), nullable=True)
    auth_message = Column(Text, nullable=True)  # Store exact message to be signed
    nonce_expires_at = Column(DateTime(timezone=True), nullable=True)

    # Session management
    session_token = Column(String(255), nullable=True, index=True)
    session_expires_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    wallets = relationship("TrackedWallet", back_populates="user", cascade="all, delete-orphan")

    def generate_nonce(self) -> str:
        """Generate a new auth nonce."""
        self.auth_nonce = secrets.token_urlsafe(32)
        self.nonce_expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
        return self.auth_nonce

    def generate_session(self) -> str:
        """Generate a new session token."""
        self.session_token = secrets.token_urlsafe(64)
        self.session_expires_at = datetime.now(timezone.utc) + timedelta(days=30)
        self.last_login_at = datetime.now(timezone.utc)
        # Clear nonce after use
        self.auth_nonce = None
        self.nonce_expires_at = None
        return self.session_token

    def is_session_valid(self) -> bool:
        """Check if current session is valid."""
        if not self.session_token or not self.session_expires_at:
            return False
        return datetime.now(timezone.utc) < self.session_expires_at


class TrackedWallet(Base):
    """Wallets being tracked for P/L calculation."""
    __tablename__ = "tracked_wallets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    address = Column(String(255), nullable=False, index=True)
    label = Column(String(255), nullable=True)  # User-friendly name

    # Owner of this tracked wallet (nullable for backwards compatibility / shared wallets)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)

    # Tracking status
    is_active = Column(Boolean, default=True)
    last_synced = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="wallets")
    transactions = relationship("Transaction", back_populates="wallet", cascade="all, delete-orphan")
    holdings = relationship("WalletTokenHolding", back_populates="wallet", cascade="all, delete-orphan")

    # Unique constraint: same address can only be tracked once per user
    __table_args__ = (
        UniqueConstraint('user_id', 'address', name='unique_user_wallet'),
        Index('ix_tracked_wallets_user_address', 'user_id', 'address'),
    )


class Token(Base):
    """Token metadata cache."""
    __tablename__ = "tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    address = Column(String(255), unique=True, nullable=False, index=True)
    symbol = Column(String(50), nullable=True)
    name = Column(String(255), nullable=True)
    decimals = Column(Integer, default=9)
    logo_url = Column(Text, nullable=True)

    # Current price (cached)
    current_price_usd = Column(Float, nullable=True)
    price_updated_at = Column(DateTime(timezone=True), nullable=True)

    # User-verified token (contributes to wallet value)
    is_verified = Column(Boolean, default=False)

    # Hidden tokens (scam airdrops, etc.)
    is_hidden = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    transactions = relationship("Transaction", back_populates="token")
    holdings = relationship("WalletTokenHolding", back_populates="token")


class Transaction(Base):
    """Individual swap transactions for P/L tracking."""
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    signature = Column(String(255), unique=True, nullable=False, index=True)

    # References
    wallet_id = Column(Integer, ForeignKey("tracked_wallets.id", ondelete="CASCADE"), nullable=False)
    token_id = Column(Integer, ForeignKey("tokens.id", ondelete="SET NULL"), nullable=True)

    # Transaction details
    tx_type = Column(String(10), nullable=False)  # 'buy' or 'sell'

    # Amounts
    amount_token = Column(Float, nullable=False)  # Token amount
    amount_sol = Column(Float, nullable=False)    # SOL amount
    price_per_token = Column(Float, nullable=True)  # Price at time of trade (in SOL)
    price_usd = Column(Float, nullable=True)       # USD price at time of trade

    # For P/L calculation on sells
    realized_pnl_sol = Column(Float, nullable=True)  # Realized P/L in SOL
    realized_pnl_usd = Column(Float, nullable=True)  # Realized P/L in USD
    cost_basis_sol = Column(Float, nullable=True)    # Cost basis used for this sell

    # Metadata
    dex_name = Column(String(50), nullable=True)  # jupiter, raydium, etc.
    block_time = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    wallet = relationship("TrackedWallet", back_populates="transactions")
    token = relationship("Token", back_populates="transactions")

    # Indexes
    __table_args__ = (
        Index('ix_transactions_wallet_token', 'wallet_id', 'token_id'),
        Index('ix_transactions_block_time', 'block_time'),
    )


class WalletTokenHolding(Base):
    """Current holdings and P/L summary per wallet per token."""
    __tablename__ = "wallet_token_holdings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    wallet_id = Column(Integer, ForeignKey("tracked_wallets.id", ondelete="CASCADE"), nullable=False)
    token_id = Column(Integer, ForeignKey("tokens.id", ondelete="CASCADE"), nullable=False)

    # Current holdings
    current_balance = Column(Float, default=0.0)  # Current token balance

    # Cost basis tracking (FIFO)
    total_cost_sol = Column(Float, default=0.0)   # Total SOL spent on current holdings
    avg_buy_price = Column(Float, default=0.0)    # Average buy price in SOL

    # P/L summary
    total_bought = Column(Float, default=0.0)     # Total tokens ever bought
    total_sold = Column(Float, default=0.0)       # Total tokens ever sold
    total_buy_sol = Column(Float, default=0.0)    # Total SOL spent buying
    total_sell_sol = Column(Float, default=0.0)   # Total SOL received selling

    realized_pnl_sol = Column(Float, default=0.0)  # Total realized P/L in SOL
    realized_pnl_usd = Column(Float, default=0.0)  # Total realized P/L in USD (at time of trades)

    # Timestamps
    first_buy_at = Column(DateTime(timezone=True), nullable=True)
    last_trade_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    wallet = relationship("TrackedWallet", back_populates="holdings")
    token = relationship("Token", back_populates="holdings")

    __table_args__ = (
        UniqueConstraint('wallet_id', 'token_id', name='unique_wallet_token'),
    )
