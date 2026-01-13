"""P/L (Profit/Loss) calculation engine using FIFO cost basis."""
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from loguru import logger

from sqlalchemy.orm import Session
from database.models import TrackedWallet, Token, Transaction, WalletTokenHolding


@dataclass
class CostBasisLot:
    """Represents a single purchase lot for FIFO tracking."""
    amount: float
    price_sol: float
    price_usd: float
    timestamp: datetime


@dataclass
class TokenPnL:
    """P/L summary for a single token."""
    token_address: str
    token_symbol: str
    token_name: str
    token_logo: Optional[str]

    # Current holdings
    current_balance: float
    avg_buy_price_sol: float
    total_cost_sol: float

    # Current value
    current_price_usd: Optional[float]
    current_value_usd: Optional[float]

    # Unrealized P/L (on current holdings)
    unrealized_pnl_sol: float
    unrealized_pnl_usd: Optional[float]
    unrealized_pnl_percent: Optional[float]

    # Realized P/L (from sells)
    realized_pnl_sol: float
    realized_pnl_usd: float

    # Trade stats
    total_bought: float
    total_sold: float
    total_buy_sol: float
    total_sell_sol: float
    trade_count: int

    # Timestamps
    first_trade: Optional[datetime]
    last_trade: Optional[datetime]


@dataclass
class PortfolioSummary:
    """Overall portfolio P/L summary."""
    total_value_usd: float
    total_cost_sol: float
    total_unrealized_pnl_usd: float
    total_realized_pnl_sol: float
    total_realized_pnl_usd: float
    token_count: int
    tokens: List[TokenPnL]


class PnLCalculator:
    """
    Calculates P/L using FIFO (First In, First Out) cost basis method.

    FIFO means when you sell, you're selling the tokens you bought first.
    This is standard for tax purposes in most jurisdictions.
    """

    def __init__(self, db: Session):
        self.db = db

    def calculate_realized_pnl(
        self,
        sell_amount: float,
        sell_price_sol: float,
        cost_basis_lots: List[CostBasisLot],
        sol_price_usd: float
    ) -> Tuple[float, float, List[CostBasisLot]]:
        """
        Calculate realized P/L for a sell using FIFO.

        Args:
            sell_amount: Amount of tokens being sold
            sell_price_sol: Price per token in SOL at time of sale
            cost_basis_lots: List of purchase lots (FIFO order)
            sol_price_usd: SOL price in USD at time of sale

        Returns:
            Tuple of (realized_pnl_sol, realized_pnl_usd, remaining_lots)
        """
        remaining_to_sell = sell_amount
        total_cost_sol = 0.0
        remaining_lots = []

        for lot in cost_basis_lots:
            if remaining_to_sell <= 0:
                remaining_lots.append(lot)
                continue

            if lot.amount <= remaining_to_sell:
                # Use entire lot
                total_cost_sol += lot.amount * lot.price_sol
                remaining_to_sell -= lot.amount
            else:
                # Partial lot usage
                total_cost_sol += remaining_to_sell * lot.price_sol
                # Add remaining portion back
                remaining_lots.append(CostBasisLot(
                    amount=lot.amount - remaining_to_sell,
                    price_sol=lot.price_sol,
                    price_usd=lot.price_usd,
                    timestamp=lot.timestamp
                ))
                remaining_to_sell = 0

        # Calculate P/L
        sell_value_sol = sell_amount * sell_price_sol
        realized_pnl_sol = sell_value_sol - total_cost_sol
        realized_pnl_usd = realized_pnl_sol * sol_price_usd

        return realized_pnl_sol, realized_pnl_usd, remaining_lots

    def process_transactions(
        self,
        transactions: List[Dict],
        sol_prices: Dict[str, float]  # signature -> sol_price_usd at that time
    ) -> Dict[str, WalletTokenHolding]:
        """
        Process transactions and calculate P/L for each token.

        Args:
            transactions: List of parsed swap transactions (sorted by time)
            sol_prices: Map of signature -> SOL price at that time

        Returns:
            Dict mapping token_mint -> holding with P/L data
        """
        # Track cost basis lots per token (FIFO)
        token_lots: Dict[str, List[CostBasisLot]] = {}
        token_holdings: Dict[str, Dict] = {}

        for tx in sorted(transactions, key=lambda x: x.get("block_time") or datetime.min):
            token_mint = tx.get("token_mint")
            tx_type = tx.get("tx_type")
            amount = tx.get("amount_token", 0)
            price_sol = tx.get("price_per_token", 0)
            block_time = tx.get("block_time")
            signature = tx.get("signature")

            sol_price_usd = sol_prices.get(signature, 200.0)  # Default SOL price

            if token_mint not in token_lots:
                token_lots[token_mint] = []
                token_holdings[token_mint] = {
                    "current_balance": 0,
                    "total_cost_sol": 0,
                    "total_bought": 0,
                    "total_sold": 0,
                    "total_buy_sol": 0,
                    "total_sell_sol": 0,
                    "realized_pnl_sol": 0,
                    "realized_pnl_usd": 0,
                    "first_trade": block_time,
                    "last_trade": block_time,
                    "trade_count": 0
                }

            holding = token_holdings[token_mint]
            holding["last_trade"] = block_time
            holding["trade_count"] += 1

            if tx_type == "buy":
                # Add to cost basis lots
                token_lots[token_mint].append(CostBasisLot(
                    amount=amount,
                    price_sol=price_sol,
                    price_usd=price_sol * sol_price_usd,
                    timestamp=block_time
                ))

                holding["current_balance"] += amount
                holding["total_cost_sol"] += amount * price_sol
                holding["total_bought"] += amount
                holding["total_buy_sol"] += amount * price_sol

            elif tx_type == "sell":
                # Calculate realized P/L using FIFO
                pnl_sol, pnl_usd, remaining = self.calculate_realized_pnl(
                    sell_amount=amount,
                    sell_price_sol=price_sol,
                    cost_basis_lots=token_lots[token_mint],
                    sol_price_usd=sol_price_usd
                )

                token_lots[token_mint] = remaining
                holding["current_balance"] -= amount
                holding["realized_pnl_sol"] += pnl_sol
                holding["realized_pnl_usd"] += pnl_usd
                holding["total_sold"] += amount
                holding["total_sell_sol"] += amount * price_sol

                # Recalculate total cost from remaining lots
                holding["total_cost_sol"] = sum(
                    lot.amount * lot.price_sol for lot in remaining
                )

        # Calculate average buy price for remaining holdings
        for token_mint, lots in token_lots.items():
            holding = token_holdings[token_mint]
            if holding["current_balance"] > 0 and lots:
                total_cost = sum(lot.amount * lot.price_sol for lot in lots)
                holding["avg_buy_price_sol"] = total_cost / holding["current_balance"]
            else:
                holding["avg_buy_price_sol"] = 0

        return token_holdings

    async def get_portfolio_pnl(
        self,
        wallet_id: int,
        current_prices: Dict[str, float],  # token_mint -> price_usd
        sol_price_usd: float,
        actual_balances: Optional[Dict[str, float]] = None  # token_mint -> actual on-chain balance
    ) -> PortfolioSummary:
        """
        Get complete P/L summary for a wallet.

        Args:
            wallet_id: Wallet database ID
            current_prices: Current token prices in USD
            sol_price_usd: Current SOL price in USD
            actual_balances: Optional dict of actual on-chain balances (token_mint -> amount).
                           If provided, uses these instead of transaction-calculated balances.

        Returns:
            PortfolioSummary with all token P/L data
        """
        # Get all holdings for wallet
        holdings = self.db.query(WalletTokenHolding).filter(
            WalletTokenHolding.wallet_id == wallet_id
        ).all()

        token_pnls = []
        total_value = 0.0
        total_cost = 0.0
        total_unrealized = 0.0
        total_realized_sol = 0.0
        total_realized_usd = 0.0

        for holding in holdings:
            token = self.db.query(Token).filter(Token.id == holding.token_id).first()
            if not token:
                continue

            current_price = current_prices.get(token.address)

            # Use actual on-chain balance if provided, otherwise use transaction-calculated balance
            if actual_balances is not None and token.address in actual_balances:
                current_balance = actual_balances[token.address]
            else:
                current_balance = holding.current_balance

            # Calculate unrealized P/L
            current_value = None
            unrealized_pnl_sol = 0.0
            unrealized_pnl_usd = None
            unrealized_pnl_percent = None

            if current_price and current_balance > 0:
                current_value = current_balance * current_price
                total_value += current_value

                # Unrealized = current value - cost basis
                cost_basis_usd = holding.total_cost_sol * sol_price_usd
                unrealized_pnl_usd = current_value - cost_basis_usd
                total_unrealized += unrealized_pnl_usd

                # Calculate in SOL terms
                current_price_sol = current_price / sol_price_usd if sol_price_usd > 0 else 0
                unrealized_pnl_sol = (current_balance * current_price_sol) - holding.total_cost_sol

                # Percent change
                if cost_basis_usd > 0:
                    unrealized_pnl_percent = (unrealized_pnl_usd / cost_basis_usd) * 100

            total_cost += holding.total_cost_sol
            total_realized_sol += holding.realized_pnl_sol
            total_realized_usd += holding.realized_pnl_usd

            token_pnls.append(TokenPnL(
                token_address=token.address,
                token_symbol=token.symbol or "???",
                token_name=token.name or "Unknown",
                token_logo=token.logo_url,
                current_balance=current_balance,  # Use actual balance
                avg_buy_price_sol=holding.avg_buy_price,
                total_cost_sol=holding.total_cost_sol,
                current_price_usd=current_price,
                current_value_usd=current_value,
                unrealized_pnl_sol=unrealized_pnl_sol,
                unrealized_pnl_usd=unrealized_pnl_usd,
                unrealized_pnl_percent=unrealized_pnl_percent,
                realized_pnl_sol=holding.realized_pnl_sol,
                realized_pnl_usd=holding.realized_pnl_usd,
                total_bought=holding.total_bought,
                total_sold=holding.total_sold,
                total_buy_sol=holding.total_buy_sol,
                total_sell_sol=holding.total_sell_sol,
                trade_count=0,  # Would need to count from transactions
                first_trade=holding.first_buy_at,
                last_trade=holding.last_trade_at
            ))

        # Sort by current value (highest first), then by realized P/L
        token_pnls.sort(
            key=lambda x: (x.current_value_usd or 0, x.realized_pnl_usd),
            reverse=True
        )

        return PortfolioSummary(
            total_value_usd=total_value,
            total_cost_sol=total_cost,
            total_unrealized_pnl_usd=total_unrealized,
            total_realized_pnl_sol=total_realized_sol,
            total_realized_pnl_usd=total_realized_usd,
            token_count=len([t for t in token_pnls if t.current_balance > 0 or t.realized_pnl_sol != 0]),
            tokens=token_pnls
        )
