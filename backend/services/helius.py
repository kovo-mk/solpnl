"""Helius API service for fetching Solana transaction history."""
import asyncio
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
import aiohttp
from loguru import logger

from config import settings


# Known wrapped SOL mint
WSOL_MINT = "So11111111111111111111111111111111111111112"

# Known DEX program IDs for swap detection
DEX_PROGRAMS = {
    "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4": "jupiter",
    "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8": "raydium",
    "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc": "orca",
    "SSwpkEEcbUqx4vtoEByFjSkhKdCT862DNVb52nZg1UZ": "saber",
}


class HeliusService:
    """Service for interacting with Helius API."""

    def __init__(self):
        self.api_key = settings.helius_api_key
        self.base_url = "https://api.helius.xyz"
        self.rpc_url = f"https://mainnet.helius-rpc.com/?api-key={self.api_key}"

    async def get_wallet_transactions(
        self,
        wallet_address: str,
        limit: int = 100,
        before_signature: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch enhanced transactions for a wallet from Helius.

        Args:
            wallet_address: Solana wallet address
            limit: Max transactions to fetch (max 100 per request)
            before_signature: Pagination cursor

        Returns:
            List of enhanced transaction data
        """
        if not self.api_key:
            logger.error("No Helius API key configured")
            return []

        try:
            url = f"{self.base_url}/v0/addresses/{wallet_address}/transactions"
            params = {
                "api-key": self.api_key,
                "limit": min(limit, 100)
            }
            if before_signature:
                params["before"] = before_signature

            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        text = await response.text()
                        logger.error(f"Helius API error: {response.status} - {text}")
                        return []

                    data = await response.json()
                    return data

        except Exception as e:
            logger.error(f"Error fetching wallet transactions: {e}")
            return []

    def parse_transaction(
        self,
        tx: Dict[str, Any],
        wallet_address: str
    ) -> Optional[Dict[str, Any]]:
        """
        Parse a Helius enhanced transaction to extract token movement data.
        Handles: swaps, transfers, airdrops, staking rewards, burns, etc.

        Args:
            tx: Enhanced transaction from Helius
            wallet_address: The wallet we're tracking

        Returns:
            Parsed transaction data or None if not relevant
        """
        try:
            signature = tx.get("signature")
            timestamp = tx.get("timestamp")
            tx_type = tx.get("type", "")
            source = tx.get("source", "unknown")

            # Categorize transaction types
            # SWAP types - trading tokens
            is_swap = (
                tx_type in ["SWAP", "INIT_SWAP", "BUY", "SELL"] or
                "SWAP" in tx_type.upper() or
                source.upper() in ["JUPITER", "RAYDIUM", "ORCA", "METEORA", "PUMP_FUN", "PUMPFUN", "MOONSHOT"]
            )

            # TRANSFER types - moving tokens between wallets
            is_transfer = tx_type in ["TRANSFER"]

            # AIRDROP/MINT types - receiving free tokens
            is_airdrop = tx_type in ["TOKEN_MINT", "COMPRESSED_NFT_MINT", "NFT_MINT"]

            # STAKING types - staking rewards and operations
            is_staking = tx_type in ["STAKE_TOKEN", "UNSTAKE_TOKEN", "STAKE_SOL", "UNSTAKE_SOL", "CLAIM_REWARDS"]

            # LIQUIDITY types - LP operations
            is_liquidity = tx_type in ["ADD_LIQUIDITY", "REMOVE_FROM_POOL", "CREATE_POOL"]

            # BURN types - burning tokens
            is_burn = tx_type in ["BURN", "BURN_NFT"]

            token_transfers = tx.get("tokenTransfers", [])
            native_transfers = tx.get("nativeTransfers", [])

            # For swaps, check if there are both token and native transfers (classic swap pattern)
            if not is_swap and token_transfers and native_transfers:
                wallet_in_tokens = any(
                    t.get("fromUserAccount") == wallet_address or t.get("toUserAccount") == wallet_address
                    for t in token_transfers
                )
                wallet_in_native = any(
                    t.get("fromUserAccount") == wallet_address or t.get("toUserAccount") == wallet_address
                    for t in native_transfers
                )
                if wallet_in_tokens and wallet_in_native:
                    is_swap = True
                    logger.debug(f"Detected swap by transfer pattern: {signature[:8]}...")

            # Skip if not a relevant transaction type
            is_relevant = is_swap or is_transfer or is_airdrop or is_staking or is_liquidity or is_burn
            if not is_relevant:
                return None

            # Determine category for this transaction
            if is_swap:
                category = "swap"
            elif is_transfer:
                category = "transfer"
            elif is_airdrop:
                category = "airdrop"
            elif is_staking:
                category = "staking"
            elif is_liquidity:
                category = "liquidity"
            elif is_burn:
                category = "burn"
            else:
                category = "other"

            # Track changes per token (excluding SOL/WSOL)
            token_changes: Dict[str, float] = {}  # mint -> amount change
            sol_change = 0.0
            transfer_destination = None  # Track where tokens were sent (for transfers)

            # Process token transfers
            for transfer in token_transfers:
                mint = transfer.get("mint", "")
                from_addr = transfer.get("fromUserAccount", "")
                to_addr = transfer.get("toUserAccount", "")
                amount = float(transfer.get("tokenAmount", 0) or 0)

                if amount <= 0:
                    continue

                # Track WSOL separately as SOL
                if mint == WSOL_MINT:
                    if to_addr == wallet_address:
                        sol_change += amount
                    elif from_addr == wallet_address:
                        sol_change -= amount
                        if category == "transfer" and not transfer_destination:
                            transfer_destination = to_addr
                else:
                    # Regular token
                    if mint not in token_changes:
                        token_changes[mint] = 0
                    if to_addr == wallet_address:
                        token_changes[mint] += amount
                    elif from_addr == wallet_address:
                        token_changes[mint] -= amount
                        # Track transfer destination for outgoing transfers
                        if category == "transfer" and not transfer_destination:
                            transfer_destination = to_addr

            # Process native SOL transfers
            for transfer in native_transfers:
                from_addr = transfer.get("fromUserAccount", "")
                to_addr = transfer.get("toUserAccount", "")
                amount = float(transfer.get("amount", 0) or 0) / 1e9  # lamports to SOL

                if amount < 0.0001:  # Skip dust
                    continue

                if to_addr == wallet_address:
                    sol_change += amount
                elif from_addr == wallet_address:
                    sol_change -= amount

            # Find the token with the largest change (the token being traded)
            if not token_changes:
                return None

            # Get the token with the biggest absolute change
            traded_token = max(token_changes.items(), key=lambda x: abs(x[1]))
            token_mint = traded_token[0]
            token_change = traded_token[1]

            if abs(token_change) < 0.0001:
                return None

            # Detect token-to-token swaps (when there are 2+ token changes)
            # One token goes out (negative), another comes in (positive)
            other_token_mint = None
            other_token_amount = 0.0

            if category == "swap" and len(token_changes) >= 2:
                # Find the "other side" of the swap
                for mint, change in token_changes.items():
                    if mint != token_mint:
                        # This is the other token in the swap
                        other_token_mint = mint
                        other_token_amount = abs(change)
                        logger.debug(f"Detected token-to-token swap: {token_mint[:8]} <-> {other_token_mint[:8]}")
                        break

            # Determine transaction subtype based on token flow and category
            if category == "swap":
                # For swaps, use buy/sell logic
                if token_change > 0:
                    # Gained tokens = BUY
                    swap_type = "buy"
                    amount_token = token_change
                    amount_sol = abs(sol_change) if sol_change < 0 else 0

                    # If no direct SOL change, estimate from other flows
                    if amount_sol == 0:
                        for transfer in native_transfers:
                            if transfer.get("fromUserAccount") == wallet_address:
                                amount_sol = max(amount_sol, float(transfer.get("amount", 0) or 0) / 1e9)
                else:
                    # Lost tokens = SELL
                    swap_type = "sell"
                    amount_token = abs(token_change)
                    amount_sol = sol_change if sol_change > 0 else 0

                    # If no direct SOL change, estimate from other flows
                    if amount_sol == 0:
                        for transfer in native_transfers:
                            if transfer.get("toUserAccount") == wallet_address:
                                amount_sol = max(amount_sol, float(transfer.get("amount", 0) or 0) / 1e9)

            elif category == "transfer":
                # For transfers, track as transfer_out or transfer_in
                if token_change > 0:
                    swap_type = "transfer_in"
                    amount_token = token_change
                    amount_sol = 0  # Transfers don't involve SOL exchange
                else:
                    swap_type = "transfer_out"
                    amount_token = abs(token_change)
                    amount_sol = 0

            elif category == "airdrop":
                # Airdrops are always incoming with $0 cost basis
                swap_type = "airdrop"
                amount_token = abs(token_change)
                amount_sol = 0

            elif category == "staking":
                # Staking rewards are incoming, staking is outgoing
                if token_change > 0:
                    swap_type = "staking_reward"
                    amount_token = token_change
                    amount_sol = 0
                else:
                    swap_type = "stake"
                    amount_token = abs(token_change)
                    amount_sol = 0

            elif category == "liquidity":
                # LP operations
                if token_change > 0:
                    swap_type = "liquidity_remove"
                    amount_token = token_change
                    amount_sol = abs(sol_change) if sol_change < 0 else 0
                else:
                    swap_type = "liquidity_add"
                    amount_token = abs(token_change)
                    amount_sol = sol_change if sol_change > 0 else 0

            elif category == "burn":
                swap_type = "burn"
                amount_token = abs(token_change)
                amount_sol = 0

            else:
                # Other types - treat as transfer
                if token_change > 0:
                    swap_type = "other_in"
                    amount_token = token_change
                    amount_sol = 0
                else:
                    swap_type = "other_out"
                    amount_token = abs(token_change)
                    amount_sol = 0

            # Calculate price per token
            price_per_token = amount_sol / amount_token if amount_token > 0 else 0

            # Determine DEX name
            dex_name = source.lower() if source else "unknown"
            for program_id, dex in DEX_PROGRAMS.items():
                if program_id in str(tx.get("accountData", [])):
                    dex_name = dex
                    break

            return {
                "signature": signature,
                "wallet_address": wallet_address,
                "token_mint": token_mint,
                "tx_type": swap_type,  # buy, sell, transfer_in, transfer_out, airdrop, staking_reward, etc.
                "category": category,  # swap, transfer, airdrop, staking, liquidity, burn, other
                "amount_token": amount_token,
                "amount_sol": amount_sol,
                "price_per_token": price_per_token,
                "dex_name": dex_name,
                "transfer_destination": transfer_destination,  # For transfers, where tokens went
                "block_time": datetime.fromtimestamp(timestamp, tz=timezone.utc) if timestamp else None,
                "helius_type": tx_type,  # Original Helius transaction type
                # Token-to-token swap fields
                "other_token_mint": other_token_mint,  # The other token in a token-to-token swap
                "other_token_amount": other_token_amount  # Amount of the other token
            }

        except Exception as e:
            logger.warning(f"Error parsing transaction {tx.get('signature', 'unknown')[:8]}...: {e}")
            return None

    async def fetch_all_transactions(
        self,
        wallet_address: str,
        max_transactions: int = 10000,
        progress_callback=None
    ) -> List[Dict[str, Any]]:
        """
        Fetch all relevant transactions for a wallet.
        Includes: swaps, transfers, airdrops, staking, liquidity ops, burns, etc.

        Args:
            wallet_address: Wallet to fetch transactions for
            max_transactions: Maximum transactions to fetch
            progress_callback: Optional callback(fetched, parsed)

        Returns:
            List of parsed transactions
        """
        parsed_txs = []
        before_sig = None
        total_fetched = 0

        while total_fetched < max_transactions:
            batch_size = min(100, max_transactions - total_fetched)
            transactions = await self.get_wallet_transactions(
                wallet_address,
                limit=batch_size,
                before_signature=before_sig
            )

            if not transactions:
                break

            total_fetched += len(transactions)

            # Log transaction types for debugging
            tx_types = {}
            for tx in transactions:
                t = tx.get("type", "UNKNOWN")
                tx_types[t] = tx_types.get(t, 0) + 1
            logger.info(f"Transaction types in batch: {tx_types}")

            # Parse each transaction
            for tx in transactions:
                parsed = self.parse_transaction(tx, wallet_address)
                if parsed:
                    parsed_txs.append(parsed)

            # Update pagination
            if transactions:
                before_sig = transactions[-1].get("signature")

            if progress_callback:
                await progress_callback(total_fetched, len(parsed_txs))

            # Rate limiting
            await asyncio.sleep(0.3)

            logger.info(f"Fetched {total_fetched} transactions, found {len(parsed_txs)} relevant transactions")

        return parsed_txs

    # Keep backward compatibility - alias old method name
    async def fetch_all_swaps(
        self,
        wallet_address: str,
        max_transactions: int = 10000,
        progress_callback=None
    ) -> List[Dict[str, Any]]:
        """Deprecated: Use fetch_all_transactions instead."""
        return await self.fetch_all_transactions(wallet_address, max_transactions, progress_callback)

    async def get_token_metadata(self, token_mint: str) -> Optional[Dict[str, Any]]:
        """
        Fetch token metadata from Helius DAS API.

        Args:
            token_mint: Token mint address

        Returns:
            Token metadata or None
        """
        if not self.api_key:
            return None

        try:
            url = self.rpc_url
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getAsset",
                "params": {"id": token_mint}
            }

            timeout = aiohttp.ClientTimeout(total=15)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=payload) as response:
                    if response.status != 200:
                        return None

                    data = await response.json()
                    result = data.get("result", {})

                    if not result:
                        return None

                    content = result.get("content", {})
                    metadata = content.get("metadata", {})
                    links = content.get("links", {})

                    return {
                        "address": token_mint,
                        "symbol": metadata.get("symbol", "???"),
                        "name": metadata.get("name", "Unknown"),
                        "decimals": result.get("token_info", {}).get("decimals", 9),
                        "logo_url": links.get("image") or content.get("json_uri")
                    }

        except Exception as e:
            logger.warning(f"Error fetching token metadata for {token_mint[:8]}...: {e}")
            return None



    async def get_wallet_balances(self, wallet_address: str) -> Dict[str, Any]:
        """
        Fetch current token balances for a wallet using Helius RPC.

        Returns:
            Dict with 'sol_balance' and 'tokens' list
        """
        if not self.api_key:
            return {"sol_balance": 0, "tokens": []}

        try:
            url = self.rpc_url

            # Get SOL balance
            sol_payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getBalance",
                "params": [wallet_address]
            }

            # Get token accounts - SPL Token (original)
            spl_tokens_payload = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "getTokenAccountsByOwner",
                "params": [
                    wallet_address,
                    {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
                    {"encoding": "jsonParsed"}
                ]
            }

            # Get token accounts - Token-2022 (newer standard)
            token2022_payload = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "getTokenAccountsByOwner",
                "params": [
                    wallet_address,
                    {"programId": "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"},
                    {"encoding": "jsonParsed"}
                ]
            }

            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # Fetch SOL balance
                sol_balance = 0
                async with session.post(url, json=sol_payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        sol_balance = (data.get("result", {}).get("value", 0) or 0) / 1e9

                # Fetch SPL token accounts
                tokens = []
                seen_mints = set()

                async with session.post(url, json=spl_tokens_payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        accounts = data.get("result", {}).get("value", [])

                        for account in accounts:
                            parsed = account.get("account", {}).get("data", {}).get("parsed", {})
                            info = parsed.get("info", {})
                            token_amount = info.get("tokenAmount", {})
                            mint = info.get("mint")

                            amount = float(token_amount.get("uiAmount") or 0)
                            if amount > 0 and mint:  # Only include non-zero balances
                                tokens.append({
                                    "mint": mint,
                                    "balance": amount,
                                    "decimals": token_amount.get("decimals", 9)
                                })
                                seen_mints.add(mint)

                # Fetch Token-2022 accounts
                async with session.post(url, json=token2022_payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        accounts = data.get("result", {}).get("value", [])

                        for account in accounts:
                            parsed = account.get("account", {}).get("data", {}).get("parsed", {})
                            info = parsed.get("info", {})
                            token_amount = info.get("tokenAmount", {})
                            mint = info.get("mint")

                            amount = float(token_amount.get("uiAmount") or 0)
                            if amount > 0 and mint and mint not in seen_mints:
                                tokens.append({
                                    "mint": mint,
                                    "balance": amount,
                                    "decimals": token_amount.get("decimals", 9)
                                })

                logger.info(f"Fetched balances for {wallet_address[:8]}...: {sol_balance:.4f} SOL, {len(tokens)} tokens")
                return {
                    "sol_balance": sol_balance,
                    "tokens": tokens
                }

        except Exception as e:
            logger.error(f"Error fetching wallet balances: {e}")
            return {"sol_balance": 0, "tokens": []}


# Singleton instance
helius_service = HeliusService()
