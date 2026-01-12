"""Pydantic schemas for API request/response models."""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


# Wallet schemas
class WalletCreate(BaseModel):
    """Request to add a wallet to track."""
    address: str = Field(..., min_length=32, max_length=44)
    label: Optional[str] = Field(None, max_length=255)


class WalletUpdate(BaseModel):
    """Request to update wallet."""
    label: Optional[str] = Field(None, max_length=255)
    is_active: Optional[bool] = None


class WalletResponse(BaseModel):
    """Wallet response."""
    id: int
    address: str
    label: Optional[str]
    is_active: bool
    last_synced: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


# Token schemas
class TokenResponse(BaseModel):
    """Token response."""
    address: str
    symbol: Optional[str]
    name: Optional[str]
    decimals: int
    logo_url: Optional[str]
    current_price_usd: Optional[float]

    class Config:
        from_attributes = True


# Transaction schemas
class TransactionResponse(BaseModel):
    """Transaction response."""
    id: int
    signature: str
    tx_type: str
    amount_token: float
    amount_sol: float
    price_per_token: Optional[float]
    price_usd: Optional[float]
    realized_pnl_sol: Optional[float]
    realized_pnl_usd: Optional[float]
    dex_name: Optional[str]
    block_time: Optional[datetime]
    token: Optional[TokenResponse]

    class Config:
        from_attributes = True


# P/L schemas
class TokenPnLResponse(BaseModel):
    """P/L for a single token."""
    token_address: str
    token_symbol: str
    token_name: str
    token_logo: Optional[str]

    # Holdings
    current_balance: float
    avg_buy_price_sol: float
    total_cost_sol: float

    # Current value
    current_price_usd: Optional[float]
    current_value_usd: Optional[float]

    # Unrealized P/L
    unrealized_pnl_sol: float
    unrealized_pnl_usd: Optional[float]
    unrealized_pnl_percent: Optional[float]

    # Realized P/L
    realized_pnl_sol: float
    realized_pnl_usd: float

    # Stats
    total_bought: float
    total_sold: float
    total_buy_sol: float
    total_sell_sol: float
    trade_count: int

    # Times
    first_trade: Optional[datetime]
    last_trade: Optional[datetime]


class PortfolioResponse(BaseModel):
    """Complete portfolio P/L response."""
    wallet_address: str
    wallet_label: Optional[str]
    total_value_usd: float
    total_cost_sol: float
    total_unrealized_pnl_usd: float
    total_realized_pnl_sol: float
    total_realized_pnl_usd: float
    token_count: int
    tokens: List[TokenPnLResponse]
    last_synced: Optional[datetime]


# Sync schemas
class SyncStatus(BaseModel):
    """Wallet sync status."""
    wallet_address: str
    status: str  # "pending", "syncing", "completed", "error"
    transactions_fetched: int = 0
    swaps_found: int = 0
    message: Optional[str] = None


# Multi-wallet portfolio
class MultiWalletPortfolioResponse(BaseModel):
    """Portfolio across multiple wallets."""
    total_value_usd: float
    total_unrealized_pnl_usd: float
    total_realized_pnl_usd: float
    wallet_count: int
    token_count: int
    wallets: List[PortfolioResponse]
