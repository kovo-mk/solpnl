"""Database models for SolPnL portfolio tracker."""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey,
    Boolean, Text, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class TrackedWallet(Base):
    """Wallets being tracked for P/L calculation."""
    __tablename__ = "tracked_wallets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    address = Column(String(255), unique=True, nullable=False, index=True)
    label = Column(String(255), nullable=True)  # User-friendly name

    # Tracking status
    is_active = Column(Boolean, default=True)
    last_synced = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    transactions = relationship("Transaction", back_populates="wallet", cascade="all, delete-orphan")
    holdings = relationship("WalletTokenHolding", back_populates="wallet", cascade="all, delete-orphan")


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
