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
    """Individual transactions for P/L tracking (swaps, transfers, airdrops, etc.)."""
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    signature = Column(String(255), unique=True, nullable=False, index=True)

    # References
    wallet_id = Column(Integer, ForeignKey("tracked_wallets.id", ondelete="CASCADE"), nullable=False)
    token_id = Column(Integer, ForeignKey("tokens.id", ondelete="SET NULL"), nullable=True)

    # Transaction details
    tx_type = Column(String(20), nullable=False)  # buy, sell, transfer_in, transfer_out, airdrop, staking_reward, etc.
    category = Column(String(20), nullable=True)  # swap, transfer, airdrop, staking, liquidity, burn, other

    # Amounts
    amount_token = Column(Float, nullable=False)  # Token amount
    amount_sol = Column(Float, nullable=False)    # SOL amount (0 for transfers/airdrops)
    price_per_token = Column(Float, nullable=True)  # Price at time of trade (in SOL)
    price_usd = Column(Float, nullable=True)       # USD price at time of trade

    # For P/L calculation on sells
    realized_pnl_sol = Column(Float, nullable=True)  # Realized P/L in SOL
    realized_pnl_usd = Column(Float, nullable=True)  # Realized P/L in USD
    cost_basis_sol = Column(Float, nullable=True)    # Cost basis used for this sell

    # Metadata
    dex_name = Column(String(50), nullable=True)  # jupiter, raydium, etc.
    transfer_destination = Column(String(255), nullable=True)  # For transfers, where tokens went
    helius_type = Column(String(50), nullable=True)  # Original Helius transaction type
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


# ============================================================================
# Token Research / Fraud Detection Models
# ============================================================================

class TokenAnalysisRequest(Base):
    """User requests to analyze a token for fraud/risk."""
    __tablename__ = "token_analysis_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    token_address = Column(String(255), nullable=False, index=True)

    # Request metadata
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(String(20), default="pending")  # pending, processing, completed, failed

    # Analysis results reference
    report_id = Column(Integer, ForeignKey("token_analysis_reports.id", ondelete="SET NULL"), nullable=True)

    # Error tracking
    error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User")
    report = relationship("TokenAnalysisReport", back_populates="requests", foreign_keys=[report_id])

    __table_args__ = (
        Index('ix_analysis_requests_status_created', 'status', 'created_at'),
    )


class TokenAnalysisReport(Base):
    """Comprehensive fraud analysis report for a token."""
    __tablename__ = "token_analysis_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    token_address = Column(String(255), nullable=False, index=True)

    # Risk scoring (0-100, higher = more risky)
    risk_score = Column(Integer, nullable=False)
    risk_level = Column(String(20), nullable=False)  # low, medium, high, critical

    # Analysis results (JSON stored as text)
    holder_concentration = Column(Text, nullable=True)  # JSON: top holder percentages
    suspicious_patterns = Column(Text, nullable=True)   # JSON: array of detected patterns
    red_flags = Column(Text, nullable=True)              # JSON: array of red flag objects

    # Holder stats
    total_holders = Column(Integer, nullable=True)  # Number of holders analyzed (usually 20)
    total_holder_count = Column(Integer, nullable=True)  # Total holder count from Solscan
    top_10_holder_percentage = Column(Float, nullable=True)
    whale_count = Column(Integer, nullable=True)  # Holders with >5%

    # Contract analysis
    is_pump_fun = Column(Boolean, default=False)
    contract_verified = Column(Boolean, default=False)
    has_freeze_authority = Column(Boolean, nullable=True)
    has_mint_authority = Column(Boolean, nullable=True)

    # Social/external data
    github_repo_url = Column(String(500), nullable=True)
    twitter_handle = Column(String(100), nullable=True)
    telegram_group = Column(String(500), nullable=True)

    # GitHub analysis
    github_commit_count = Column(Integer, nullable=True)
    github_developer_count = Column(Integer, nullable=True)
    github_created_at = Column(DateTime(timezone=True), nullable=True)
    github_first_commit_at = Column(DateTime(timezone=True), nullable=True)

    # Social metrics
    twitter_followers = Column(Integer, nullable=True)
    telegram_members = Column(Integer, nullable=True)

    # Wash trading analysis
    wash_trading_score = Column(Integer, nullable=True)  # 0-100, higher = more suspicious
    wash_trading_likelihood = Column(String(20), nullable=True)  # low, medium, high, critical
    unique_traders_24h = Column(Integer, nullable=True)
    volume_24h_usd = Column(Float, nullable=True)
    txns_24h_total = Column(Integer, nullable=True)
    airdrop_likelihood = Column(String(20), nullable=True)  # low, medium, high, critical
    suspicious_wallets = Column(Text, nullable=True)  # JSON list of suspicious wallet details

    # Additional market data
    liquidity_usd = Column(Float, nullable=True)
    price_change_24h = Column(Float, nullable=True)
    market_cap_usd = Column(Float, nullable=True)
    current_price_usd = Column(Float, nullable=True)

    # Transaction analysis (stored as JSON)
    transaction_breakdown = Column(Text, nullable=True)  # JSON: transaction type counts
    pattern_transactions = Column(Text, nullable=True)  # JSON: pattern_name -> [signatures]
    time_periods = Column(Text, nullable=True)  # JSON: 24h, 7d, 30d breakdown

    # Liquidity and whale tracking (stored as JSON)
    liquidity_pools = Column(Text, nullable=True)  # JSON: [{dex, pool_address, liquidity_usd, created_at}]
    whale_movements = Column(Text, nullable=True)  # JSON: [{from, to, amount, amount_usd, timestamp, tx_signature}]

    # Token metadata
    token_name = Column(String(500), nullable=True)
    token_symbol = Column(String(50), nullable=True)
    token_logo_url = Column(Text, nullable=True)
    pair_created_at = Column(DateTime(timezone=True), nullable=True)  # When the trading pair was created

    # AI analysis summary
    claude_summary = Column(Text, nullable=True)  # Claude's natural language analysis
    claude_verdict = Column(String(50), nullable=True)  # safe, suspicious, likely_scam, confirmed_scam

    # Cache control
    is_stale = Column(Boolean, default=False)  # Mark for re-analysis
    cached_until = Column(DateTime(timezone=True), nullable=True)  # Cache expiry

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    requests = relationship("TokenAnalysisRequest", back_populates="report", foreign_keys="TokenAnalysisRequest.report_id")
    wallet_reputations = relationship("WalletReputation", back_populates="token_report")

    __table_args__ = (
        Index('ix_reports_token_created', 'token_address', 'created_at'),
        Index('ix_reports_risk_score', 'risk_score'),
    )


class WalletReputation(Base):
    """Reputation tracking for individual wallets (for Sybil/wash trading detection)."""
    __tablename__ = "wallet_reputations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    wallet_address = Column(String(255), nullable=False, unique=True, index=True)

    # Reputation metrics
    reputation_score = Column(Integer, default=50)  # 0-100, 50=neutral, <30=suspicious

    # Activity patterns
    first_seen_at = Column(DateTime(timezone=True), nullable=True)
    total_tokens_held = Column(Integer, default=0)
    total_transactions = Column(Integer, default=0)

    # Suspicious behavior flags
    is_sybil_cluster = Column(Boolean, default=False)  # Part of coordinated wallet group
    wash_trading_score = Column(Float, default=0.0)    # 0-1, higher = more suspicious
    rapid_dump_count = Column(Integer, default=0)      # Number of tokens dumped <24h after buy

    # Clustering info
    cluster_id = Column(String(100), nullable=True)  # Group ID for related wallets
    cluster_confidence = Column(Float, nullable=True)  # 0-1, how confident about clustering

    # Analysis metadata
    analyzed_in_report_id = Column(Integer, ForeignKey("token_analysis_reports.id", ondelete="SET NULL"), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    token_report = relationship("TokenAnalysisReport", back_populates="wallet_reputations")

    __table_args__ = (
        Index('ix_wallet_reputation_score', 'reputation_score'),
        Index('ix_wallet_sybil_cluster', 'is_sybil_cluster', 'cluster_id'),
    )


class SuspiciousWalletToken(Base):
    """Tracks which suspicious wallets are associated with which tokens for network detection."""
    __tablename__ = "suspicious_wallet_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    wallet_address = Column(String(255), nullable=False, index=True)
    token_address = Column(String(255), nullable=False, index=True)
    report_id = Column(Integer, ForeignKey("token_analysis_reports.id", ondelete="CASCADE"), nullable=False)

    # Pattern info
    pattern_type = Column(String(50), nullable=True)  # repeated_pairs, bot_activity, isolated_trader
    trade_count = Column(Integer, nullable=True)  # How many times this wallet traded the token

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint('wallet_address', 'token_address', 'report_id', name='unique_wallet_token_report'),
        Index('ix_suspicious_wallet_address', 'wallet_address'),
        Index('ix_suspicious_token_address', 'token_address'),
    )


class SolscanTransferCache(Base):
    """Cache for Solscan Pro API token transfer data to reduce API costs."""
    __tablename__ = "solscan_transfer_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    token_address = Column(String(255), nullable=False, index=True)

    # Transfer data (stored as JSON string)
    transfers_json = Column(Text, nullable=False)  # Raw Solscan transfer data

    # Cache metadata
    transfer_count = Column(Integer, nullable=False)  # Number of transfers cached
    earliest_timestamp = Column(Integer, nullable=False)  # Unix timestamp of oldest transfer
    latest_timestamp = Column(Integer, nullable=False)  # Unix timestamp of newest transfer
    days_back = Column(Integer, default=30)  # How many days of data this cache covers

    # Cache validity
    cached_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)  # When to invalidate cache
    is_complete = Column(Boolean, default=False)  # True if we fetched all available transfers

    __table_args__ = (
        Index('ix_solscan_cache_token_cached', 'token_address', 'cached_at'),
        Index('ix_solscan_cache_expires', 'expires_at'),
    )


class WalletTransactionCache(Base):
    """Cache for complete wallet transaction history from Helius API.

    Transactions are immutable blockchain data, so we cache permanently.
    Use continue_fetch parameter to fetch additional older transactions.
    """
    __tablename__ = "wallet_transaction_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    wallet_address = Column(String(255), nullable=False, unique=True, index=True)

    # Transaction data (stored as JSON string)
    transactions_json = Column(Text, nullable=False)  # Enhanced Helius transaction data

    # Cache metadata
    transaction_count = Column(Integer, nullable=False)  # Number of transactions cached
    earliest_timestamp = Column(Integer, nullable=True)  # Unix timestamp of oldest transaction
    latest_timestamp = Column(Integer, nullable=True)  # Unix timestamp of newest transaction

    # Cache validity
    cached_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    is_complete = Column(Boolean, default=False)  # True if we fetched all available transactions

    __table_args__ = (
        Index('ix_wallet_tx_cache_wallet_cached', 'wallet_address', 'cached_at'),
    )


class NewTokenFeed(Base):
    """Feed of newly created tokens from Solscan for monitoring."""
    __tablename__ = "new_token_feed"

    id = Column(Integer, primary_key=True, autoincrement=True)
    token_address = Column(String(255), nullable=False, unique=True, index=True)

    # Token metadata
    token_name = Column(String(500), nullable=True)
    token_symbol = Column(String(50), nullable=True)
    token_logo_url = Column(Text, nullable=True)

    # Launch details
    platform = Column(String(50), nullable=True)  # pumpfun, raydium, orca, etc.
    created_at = Column(DateTime(timezone=True), nullable=False, index=True)

    # Quick metrics
    initial_liquidity_usd = Column(Float, nullable=True)
    pool_address = Column(String(255), nullable=True)

    # Tracking
    discovered_at = Column(DateTime(timezone=True), server_default=func.now())
    has_been_analyzed = Column(Boolean, default=False, index=True)

    __table_args__ = (
        Index('ix_new_token_created', 'created_at', 'has_been_analyzed'),
        Index('ix_new_token_platform', 'platform', 'created_at'),
    )


class RateLimit(Base):
    """API rate limiting for analysis requests."""
    __tablename__ = "rate_limits"

    id = Column(Integer, primary_key=True, autoincrement=True)
    identifier = Column(String(255), nullable=False, index=True)  # IP or user_id
    endpoint = Column(String(100), nullable=False)  # /api/analyze, etc.

    request_count = Column(Integer, default=1)
    window_start = Column(DateTime(timezone=True), nullable=False)
    window_end = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint('identifier', 'endpoint', 'window_start', name='unique_rate_limit_window'),
        Index('ix_rate_limit_window', 'identifier', 'endpoint', 'window_end'),
    )
