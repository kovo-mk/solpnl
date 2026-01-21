"""Helius API service for fetching Solana transaction history and DexScreener liquidity data."""
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
        self.api_key = settings.HELIUS_API_KEY
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

            # Also detect token-to-token swaps (2+ token transfers, wallet involved, minimal native transfers)
            # Only classify as swap if there are NO significant native SOL transfers (< 0.01 SOL)
            if not is_swap and len(token_transfers) >= 2:
                wallet_involved = any(
                    t.get("fromUserAccount") == wallet_address or t.get("toUserAccount") == wallet_address
                    for t in token_transfers
                )
                # Check if there are significant native transfers
                total_native_transfer = sum(
                    float(t.get("amount", 0) or 0) / 1e9
                    for t in native_transfers
                    if t.get("fromUserAccount") == wallet_address or t.get("toUserAccount") == wallet_address
                )
                # Only treat as token-to-token swap if native transfers are minimal (< 0.01 SOL, accounting for fees)
                if wallet_involved and total_native_transfer < 0.01:
                    is_swap = True
                    logger.debug(f"Detected token-to-token swap by multiple token transfers: {signature[:8]}...")

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
            # This works for any transaction type, not just category="swap"
            other_token_mint = None
            other_token_amount = 0.0

            if len(token_changes) >= 2:
                # Find the "other side" of the swap
                for mint, change in token_changes.items():
                    if mint != token_mint:
                        # This is the other token in the swap
                        other_token_mint = mint
                        other_token_amount = abs(change)
                        logger.debug(f"Detected token-to-token swap: {token_mint[:8]} <-> {other_token_mint[:8]} (category={category})")
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

    async def get_token_holders(self, token_mint: str, limit: int = 1000) -> List[Dict[str, Any]]:
        """
        Fetch token holder data for a specific token mint using Solana RPC.

        Args:
            token_mint: Token mint address
            limit: Max holders to fetch (default 1000, for top holders)

        Returns:
            List of {address, balance, percentage} dicts sorted by balance descending
        """
        try:
            timeout = aiohttp.ClientTimeout(total=60)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # Step 1: Get token supply from mint account
                supply_payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getTokenSupply",
                    "params": [token_mint]
                }

                async with session.post(self.rpc_url, json=supply_payload) as response:
                    if response.status != 200:
                        logger.error(f"Failed to fetch token supply: {response.status}")
                        return []

                    supply_data = await response.json()
                    if "error" in supply_data:
                        logger.error(f"RPC error fetching supply: {supply_data['error']}")
                        return []

                    supply_result = supply_data.get("result", {}).get("value", {})
                    total_supply = float(supply_result.get("amount", 0))
                    decimals = supply_result.get("decimals", 9)

                    if total_supply == 0:
                        logger.warning(f"Token {token_mint} has zero supply")
                        return []

                # Step 2: Get largest token accounts
                accounts_payload = {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "getTokenLargestAccounts",
                    "params": [token_mint]
                }

                async with session.post(self.rpc_url, json=accounts_payload) as response:
                    if response.status != 200:
                        logger.error(f"Failed to fetch largest accounts: {response.status}")
                        return []

                    accounts_data = await response.json()
                    if "error" in accounts_data:
                        logger.error(f"RPC error fetching accounts: {accounts_data['error']}")
                        return []

                    accounts = accounts_data.get("result", {}).get("value", [])

                    holders = []
                    # Step 3: Get owner for each token account
                    for account in accounts[:min(limit, 100)]:  # Fetch top 100 holders
                        amount = account.get("amount")
                        address = account.get("address")

                        if amount and address:
                            # Get owner of this token account
                            owner_payload = {
                                "jsonrpc": "2.0",
                                "id": 3,
                                "method": "getAccountInfo",
                                "params": [address, {"encoding": "jsonParsed"}]
                            }

                            async with session.post(self.rpc_url, json=owner_payload) as owner_response:
                                if owner_response.status == 200:
                                    owner_data = await owner_response.json()
                                    if "error" not in owner_data:
                                        owner_info = owner_data.get("result", {}).get("value", {}).get("data", {})
                                        parsed = owner_info.get("parsed", {})
                                        owner_address = parsed.get("info", {}).get("owner", address)

                                        balance = float(amount) / (10 ** decimals)
                                        percentage = (balance / (total_supply / (10 ** decimals))) * 100

                                        holders.append({
                                            "address": owner_address,
                                            "token_account": address,
                                            "balance": balance,
                                            "percentage": percentage,
                                        })

                    # Sort by balance descending
                    holders.sort(key=lambda x: x["balance"], reverse=True)

                    logger.info(f"Fetched {len(holders)} holders for token {token_mint[:8]}...")
                    return holders

        except Exception as e:
            logger.error(f"Error fetching token holders: {e}")
            return []

    async def get_token_creator(self, token_mint: str) -> str:
        """
        Get the creator by finding the wallet that created the mint account.

        This looks at the token's transaction history to find who initialized it.

        Args:
            token_mint: Token mint address

        Returns:
            Creator address or None if not found
        """
        try:
            # Get signature list for the mint address (oldest first to find creation tx)
            url = f"{self.rpc_url}"

            # Get the oldest transactions (where the mint was created)
            payload = {
                "jsonrpc": "2.0",
                "id": "get-signatures",
                "method": "getSignaturesForAddress",
                "params": [
                    token_mint,
                    {
                        "limit": 1000  # Get up to 1000 oldest transactions
                    }
                ]
            }

            timeout = aiohttp.ClientTimeout(total=15)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=payload) as response:
                    if response.status != 200:
                        logger.warning(f"Failed to fetch signatures: {response.status}")
                        return None

                    data = await response.json()

                    if "error" in data:
                        logger.warning(f"RPC error fetching signatures: {data.get('error')}")
                        return None

                    signatures = data.get("result", [])

                    if not signatures:
                        logger.warning(f"No transaction signatures found for {token_mint}")
                        return None

                    # The last signature in the list is the oldest (creation transaction)
                    oldest_signature = signatures[-1].get("signature")

                    if not oldest_signature:
                        return None

                    # Get the full transaction to find who created the mint
                    tx_payload = {
                        "jsonrpc": "2.0",
                        "id": "get-transaction",
                        "method": "getTransaction",
                        "params": [
                            oldest_signature,
                            {
                                "encoding": "jsonParsed",
                                "maxSupportedTransactionVersion": 0
                            }
                        ]
                    }

                    async with session.post(url, json=tx_payload) as tx_response:
                        if tx_response.status != 200:
                            logger.warning(f"Failed to fetch transaction: {tx_response.status}")
                            return None

                        tx_data = await tx_response.json()

                        if "error" in tx_data:
                            logger.warning(f"RPC error fetching transaction: {tx_data.get('error')}")
                            return None

                        result = tx_data.get("result", {})
                        transaction = result.get("transaction", {})
                        message = transaction.get("message", {})
                        account_keys = message.get("accountKeys", [])

                        # The fee payer (first account) is usually the creator
                        if account_keys and len(account_keys) > 0:
                            fee_payer = account_keys[0]
                            if isinstance(fee_payer, dict):
                                creator = fee_payer.get("pubkey")
                            else:
                                creator = fee_payer

                            logger.info(f"Found creator for {token_mint[:8]}: {creator[:8] if creator else 'None'}")
                            return creator

                        logger.warning(f"No account keys found in creation transaction")
                        return None

        except Exception as e:
            logger.error(f"Error fetching token creator: {e}")
            return None

    async def get_token_mint_info(self, token_mint: str) -> Dict[str, Any]:
        """
        Fetch token mint information including freeze and mint authorities.

        Args:
            token_mint: Token mint address

        Returns:
            Dict with mint_authority, freeze_authority, decimals, supply
        """
        try:
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getAccountInfo",
                    "params": [
                        token_mint,
                        {
                            "encoding": "jsonParsed"
                        }
                    ]
                }

                async with session.post(self.rpc_url, json=payload) as response:
                    if response.status != 200:
                        logger.error(f"Failed to fetch mint info: {response.status}")
                        return {}

                    data = await response.json()
                    if "error" in data:
                        logger.error(f"RPC error fetching mint info: {data['error']}")
                        return {}

                    result = data.get("result", {}).get("value", {})
                    parsed = result.get("data", {}).get("parsed", {}).get("info", {})

                    return {
                        "mint_authority": parsed.get("mintAuthority"),
                        "freeze_authority": parsed.get("freezeAuthority"),
                        "decimals": parsed.get("decimals", 9),
                        "supply": parsed.get("supply", "0"),
                        "is_initialized": parsed.get("isInitialized", False),
                    }

        except Exception as e:
            logger.error(f"Error fetching mint info: {e}")
            return {}

    async def get_dexscreener_data(self, token_address: str) -> Dict[str, Any]:
        """
        Fetch token data from DexScreener API (free, no API key needed).

        Args:
            token_address: Token mint address

        Returns:
            Dict with price, volume, liquidity, social links
        """
        try:
            url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
            timeout = aiohttp.ClientTimeout(total=10)

            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        logger.warning(f"DexScreener returned {response.status} for {token_address}")
                        return {}

                    data = await response.json()
                    pairs = data.get("pairs", [])

                    if not pairs:
                        logger.info(f"No DexScreener data found for {token_address}")
                        return {}

                    # Get the most liquid pair (usually the main trading pair)
                    main_pair = max(pairs, key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0))

                    # Extract social links
                    info = main_pair.get("info", {})
                    websites = info.get("websites", [])
                    socials = info.get("socials", [])

                    website = websites[0].get("url") if websites else None
                    twitter = None
                    telegram = None

                    for social in socials:
                        social_type = social.get("type", "").lower()
                        if social_type == "twitter":
                            twitter = social.get("url")
                        elif social_type == "telegram":
                            telegram = social.get("url")

                    # Extract transaction counts (includes unique addresses/holders)
                    txns = main_pair.get("txns", {})
                    total_txns_24h = (txns.get("h24", {}).get("buys", 0) or 0) + (txns.get("h24", {}).get("sells", 0) or 0)

                    return {
                        "price_usd": float(main_pair.get("priceUsd", 0) or 0),
                        "price_native": float(main_pair.get("priceNative", 0) or 0),
                        "volume_24h": float(main_pair.get("volume", {}).get("h24", 0) or 0),
                        "liquidity_usd": float(main_pair.get("liquidity", {}).get("usd", 0) or 0),
                        "market_cap": float(main_pair.get("marketCap", 0) or 0),
                        "fdv": float(main_pair.get("fdv", 0) or 0),
                        "dex": main_pair.get("dexId", "unknown"),
                        "pair_address": main_pair.get("pairAddress"),
                        "price_change_24h": float(main_pair.get("priceChange", {}).get("h24", 0) or 0),
                        "total_txns_24h": total_txns_24h,
                        "website": website,
                        "twitter": twitter,
                        "telegram": telegram,
                        "pair_created_at": main_pair.get("pairCreatedAt"),
                    }

        except Exception as e:
            logger.error(f"Error fetching DexScreener data: {e}")
            return {}

    async def get_dexscreener_pools(self, token_address: str) -> List[Dict]:
        """
        Fetch all liquidity pools for a token from DexScreener.

        Returns list of pools similar to Solscan format:
        [{
            "dex": "Raydium",
            "pool_address": "...",
            "liquidity_usd": 123456.78,
            "volume_24h": 50000.0,
            "created_at": "2024-01-01T00:00:00Z"
        }]
        """
        try:
            url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
            timeout = aiohttp.ClientTimeout(total=10)

            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        logger.error(f"DexScreener pools returned {response.status} for {token_address[:8]}")
                        return []

                    data = await response.json()
                    logger.debug(f"DexScreener response for {token_address[:8]}: {str(data)[:200]}")

                    pairs = data.get("pairs", [])
                    logger.info(f"DexScreener returned {len(pairs)} total pairs for {token_address[:8]}")

                    if not pairs:
                        logger.warning(f"No pairs found in DexScreener response for {token_address[:8]}")
                        return []

                    # Format all pairs as liquidity pools
                    formatted_pools = []
                    for pair in pairs:
                        liquidity = float(pair.get("liquidity", {}).get("usd", 0) or 0)

                        # Only include pools with meaningful liquidity (> $100)
                        if liquidity < 100:
                            logger.debug(f"Skipping pool {pair.get('dexId')} with liquidity ${liquidity:.2f}")
                            continue

                        formatted_pools.append({
                            "dex": pair.get("dexId", "Unknown"),
                            "pool_address": pair.get("pairAddress"),
                            "liquidity_usd": liquidity,
                            "volume_24h": float(pair.get("volume", {}).get("h24", 0) or 0),
                            "volume_6h": float(pair.get("volume", {}).get("h6", 0) or 0),
                            "volume_1h": float(pair.get("volume", {}).get("h1", 0) or 0),
                            "price_change_24h": float(pair.get("priceChange", {}).get("h24", 0) or 0),
                            "price_change_6h": float(pair.get("priceChange", {}).get("h6", 0) or 0),
                            "price_change_1h": float(pair.get("priceChange", {}).get("h1", 0) or 0),
                            "txns_24h_buys": pair.get("txns", {}).get("h24", {}).get("buys", 0),
                            "txns_24h_sells": pair.get("txns", {}).get("h24", {}).get("sells", 0),
                            "created_at": pair.get("pairCreatedAt"),
                            "price_usd": float(pair.get("priceUsd", 0) or 0),
                        })

                    logger.info(f"✅ Formatted {len(formatted_pools)} DexScreener pools (>{100}) for {token_address[:8]}")
                    return formatted_pools

        except Exception as e:
            logger.error(f"Error fetching DexScreener pools: {e}")
            return []

    async def get_birdeye_token_data(self, token_address: str) -> Dict[str, Any]:
        """
        Fetch comprehensive token data from Birdeye API (free tier).
        Includes volume, trades, liquidity, and more.

        Args:
            token_address: Token mint address

        Returns:
            Dict with volume_24h, txns_24h, liquidity, price_change, etc.
        """
        try:
            # Birdeye public API (no key required for basic data)
            url = f"https://public-api.birdeye.so/defi/token_overview"
            params = {"address": token_address}

            headers = {
                "User-Agent": "Mozilla/5.0",
                "X-Chain": "solana"
            }

            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, params=params, headers=headers) as response:
                    if response.status != 200:
                        logger.warning(f"Birdeye API returned {response.status}")
                        return {}

                    data = await response.json()

                    if not data.get("success"):
                        return {}

                    token_data = data.get("data", {})

                    result = {
                        "volume_24h": token_data.get("v24hUSD", 0),
                        "volume_change_24h": token_data.get("v24hChangePercent", 0),
                        "liquidity_usd": token_data.get("liquidity", 0),
                        "price_usd": token_data.get("price", 0),
                        "price_change_24h": token_data.get("priceChange24hPercent", 0),
                        "market_cap": token_data.get("mc", 0),
                        "txns_24h": {
                            "buys": token_data.get("trade24h", {}).get("buys", 0),
                            "sells": token_data.get("trade24h", {}).get("sells", 0),
                        },
                        "unique_wallets_24h": token_data.get("uniqueWallet24h", 0),
                        "holder_count": token_data.get("holder", 0),
                    }

                    logger.info(f"Birdeye data: volume=${result['volume_24h']}, txns={result['txns_24h']}")
                    return result

        except Exception as e:
            logger.error(f"Error fetching Birdeye data: {e}")
            return {}

    async def get_dexscreener_data(self, token_address: str) -> Dict[str, Any]:
        """
        Scrape data from DexScreener website including holder count and social links.

        Args:
            token_address: Token mint address

        Returns:
            Dict with holder_count, twitter_handle, telegram_url, website
        """
        try:
            url = f"https://dexscreener.com/solana/{token_address}"
            timeout = aiohttp.ClientTimeout(total=15)

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }

            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        logger.warning(f"DexScreener website returned {response.status}")
                        return {}

                    html = await response.text()
                    import re
                    result = {}

                    # Scrape holder count
                    # Pattern: {"count":602,"totalSupply":"...","holders":[...]}
                    holder_match = re.search(r'\{"count":(\d+),"totalSupply".*?"holders":\[', html)
                    if holder_match:
                        result["holder_count"] = int(holder_match.group(1))
                        logger.info(f"Scraped holder count: {result['holder_count']}")

                    # Scrape Twitter handle
                    # Pattern: {"type":"twitter","label":undefined,"url":"https://x.com/handle"}
                    twitter_match = re.search(r'https://(?:twitter|x)\.com/(\w+)', html)
                    if twitter_match:
                        handle = twitter_match.group(1)
                        # Filter out common non-token accounts
                        if handle.lower() not in ['dexscreener', 'solana', 'twitter', 'x']:
                            result["twitter_handle"] = handle
                            logger.info(f"Scraped Twitter handle: @{handle}")

                    # Scrape Telegram channel
                    # Pattern: {"type":"telegram","label":undefined,"url":"https://t.me/channel"}
                    telegram_match = re.search(r'https://t\.me/([a-zA-Z0-9_]+)', html)
                    if telegram_match:
                        channel = telegram_match.group(1)
                        result["telegram_url"] = f"https://t.me/{channel}"
                        logger.info(f"Scraped Telegram: {channel}")

                    # Scrape website
                    # Pattern: {"type":undefined,"label":"Website","url":"https://..."}
                    website_match = re.search(r'\{"[^}]*"Website"[^}]*"url":"([^"]+)"', html)
                    if website_match:
                        result["website"] = website_match.group(1).replace(r'\u002F', '/')
                        logger.info(f"Scraped website: {result['website']}")

                    return result

        except Exception as e:
            logger.error(f"Error scraping DexScreener data: {e}")
            return {}

    async def get_dexscreener_holder_count(self, token_address: str) -> Optional[int]:
        """
        Scrape holder count from DexScreener (for backwards compatibility).

        Args:
            token_address: Token mint address

        Returns:
            Holder count or None
        """
        data = await self.get_dexscreener_data(token_address)
        return data.get("holder_count")

    async def get_solscan_token_meta(self, token_address: str) -> Dict[str, Any]:
        """
        Fetch token metadata from Solscan Pro API including holder count.
        Falls back to DexScreener web scraping if Solscan API unavailable.

        Args:
            token_address: Token mint address

        Returns:
            Dict with holder count, price, volume, market cap
        """
        try:
            from config import settings

            # Try Solscan API first if key is configured
            if not settings.SOLSCAN_API_KEY:
                logger.info("Solscan API key not configured, using DexScreener scraper")
                holder_count = await self.get_dexscreener_holder_count(token_address)
                return {"holder_count": holder_count} if holder_count else {}

            url = f"https://pro-api.solscan.io/v2.0/token/meta"
            params = {"address": token_address}
            headers = {
                "token": settings.SOLSCAN_API_KEY,
                "accept": "application/json"
            }
            timeout = aiohttp.ClientTimeout(total=10)

            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, params=params, headers=headers) as response:
                    if response.status != 200:
                        logger.warning(f"Solscan API returned {response.status}, falling back to DexScreener scraper")
                        # Fallback to DexScreener web scraping
                        holder_count = await self.get_dexscreener_holder_count(token_address)
                        return {"holder_count": holder_count} if holder_count else {}

                    data = await response.json()

                    if not data.get("success"):
                        logger.warning(f"Solscan request unsuccessful, falling back to DexScreener scraper")
                        holder_count = await self.get_dexscreener_holder_count(token_address)
                        return {"holder_count": holder_count} if holder_count else {}

                    return {
                        "holder_count": data.get("holder", 0),
                        "price_usd": float(data.get("price", 0) or 0),
                        "volume_24h": float(data.get("volume_24h", 0) or 0),
                        "market_cap": float(data.get("market_cap", 0) or 0),
                        "supply": data.get("supply"),
                        "creator": data.get("creator"),
                        "created_time": data.get("created_time"),
                    }

        except Exception as e:
            logger.error(f"Error fetching Solscan token meta, falling back to DexScreener: {e}")
            # Final fallback to DexScreener
            holder_count = await self.get_dexscreener_holder_count(token_address)
            return {"holder_count": holder_count} if holder_count else {}

    async def get_telegram_info(self, telegram_url: str) -> Dict[str, Any]:
        """
        Scrape Telegram channel/group info (member count, title).

        Args:
            telegram_url: Telegram channel or group URL (e.g., https://t.me/channel_name)

        Returns:
            Dict with member_count, title, description
        """
        try:
            # Extract channel name from URL
            if "t.me/" in telegram_url:
                channel_name = telegram_url.split("t.me/")[-1].split("?")[0].strip("/")
            else:
                return {}

            # Telegram's public preview page (no API key needed)
            preview_url = f"https://t.me/{channel_name}"

            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
                async with session.get(preview_url, headers=headers) as response:
                    if response.status != 200:
                        logger.warning(f"Failed to fetch Telegram preview: {response.status}")
                        return {}

                    html = await response.text()

                    # Parse member count from meta tags or page content
                    member_count = None
                    title = None
                    description = None

                    # Try to find member count in various formats
                    import re

                    # Look for "X subscribers" or "X members"
                    subscriber_match = re.search(r'(\d[\d\s,]*)\s*(subscribers|members)', html, re.IGNORECASE)
                    if subscriber_match:
                        member_str = subscriber_match.group(1).replace(" ", "").replace(",", "")
                        try:
                            member_count = int(member_str)
                        except:
                            pass

                    # Look for title in meta tags
                    title_match = re.search(r'<meta property="og:title" content="([^"]+)"', html)
                    if title_match:
                        title = title_match.group(1)

                    # Look for description
                    desc_match = re.search(r'<meta property="og:description" content="([^"]+)"', html)
                    if desc_match:
                        description = desc_match.group(1)

                    return {
                        "member_count": member_count,
                        "title": title,
                        "description": description,
                        "url": telegram_url,
                    }

        except Exception as e:
            logger.error(f"Error fetching Telegram info: {e}")
            return {}

    async def analyze_wallet_distribution(
        self,
        token_address: str,
        wallet_address: str,
        total_supply: float,
        wallet_label: str = "wallet"
    ) -> Dict[str, Any]:
        """
        Analyze token distribution from a specific wallet (mint authority or creator).

        Uses Helius Developer API with tokenAccounts filter to efficiently fetch token transactions.

        Args:
            token_address: The token mint address
            wallet_address: The wallet address to analyze
            total_supply: Total token supply for percentage calculations
            wallet_label: Label for the wallet type (e.g., "mint_authority", "creator")

        Returns:
            Dict with distribution breakdown:
            {
                "wallet_address": str,
                "wallet_label": str,
                "total_distributed": float,
                "total_distributed_pct": float,
                "sold_via_dex": float,
                "sold_via_dex_pct": float,
                "transferred_to_wallets": float,
                "transferred_to_wallets_pct": float,
                "burned": float,
                "burned_pct": float,
                "current_balance": float,
                "transactions": List[Dict],
            }
        """
        logger.info(f"Analyzing {wallet_label} distribution for {token_address[:8]} from {wallet_address[:8]}")

        try:
            # Use Helius getTransactionsForAddress with tokenAccounts filter
            url = f"{self.rpc_url}"

            payload = {
                "jsonrpc": "2.0",
                "id": "wallet-distribution",
                "method": "getTransactionsForAddress",
                "params": [
                    wallet_address,
                    {
                        "filters": {
                            "tokenAccounts": "balanceChanged"  # Only txns that moved tokens
                        },
                        "sortOrder": "asc",  # Chronological order
                        "limit": 1000  # Fetch up to 1000 transactions
                    }
                ]
            }

            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=payload) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Helius RPC error: {response.status} - {error_text}")
                        return self._empty_distribution_result(wallet_address, wallet_label)

                    data = await response.json()

                    if "error" in data:
                        logger.error(f"RPC error: {data['error']}")
                        return self._empty_distribution_result(wallet_address, wallet_label)

                    transactions = data.get("result", [])
                    logger.info(f"Fetched {len(transactions)} transactions from {wallet_label}")

            # Analyze transactions to categorize distributions
            total_distributed = 0
            sold_via_dex = 0
            transferred_to_wallets = 0
            burned = 0
            distribution_events = []

            # Known DEX programs
            DEX_PROGRAMS = {
                "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8",  # Raydium AMM
                "5quBtoiQqxF9Jv6KYKctB59NT3gtJD2Y65kdnB1Uev3h",  # Raydium V4
                "9W959DqEETiGZocYWCQPaJ6sBmUzgfxXfqGeTEdp3aQP",  # Orca
                "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc",  # Orca Whirlpool
                "HYPERfwdTjyJ2SCaKHmpF2MtrXqWxrsotYDsTrshHWq8",  # Hyperplane
                "PSwapMdSai8tjrEXcxFeQth87xC4rRsa4VA5mhGhXkP",   # Pump.fun
                "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4",  # Jupiter
            }

            # Burn addresses
            BURN_ADDRESSES = {
                "1nc1nerator11111111111111111111111111111111",  # Incinerator
                "11111111111111111111111111111111",  # System program
            }

            for tx in transactions:
                try:
                    # Get token transfers from transaction
                    token_transfers = tx.get("tokenTransfers", [])

                    for transfer in token_transfers:
                        # Only analyze transfers of our specific token
                        if transfer.get("mint") != token_address:
                            continue

                        from_account = transfer.get("fromUserAccount")
                        to_account = transfer.get("toUserAccount")
                        amount = transfer.get("tokenAmount", 0)

                        # Only count outbound transfers from the wallet
                        if from_account != wallet_address:
                            continue

                        # Categorize the transfer
                        if to_account in BURN_ADDRESSES:
                            burned += amount
                            category = "burn"
                        elif to_account in DEX_PROGRAMS:
                            sold_via_dex += amount
                            category = "dex_sale"
                        else:
                            transferred_to_wallets += amount
                            category = "transfer"

                        total_distributed += amount

                        # Record the event
                        distribution_events.append({
                            "signature": tx.get("signature"),
                            "timestamp": tx.get("timestamp"),
                            "to_address": to_account,
                            "amount": amount,
                            "category": category,
                        })

                except Exception as e:
                    logger.warning(f"Error parsing transaction: {e}")
                    continue

            # Calculate percentages
            total_distributed_pct = (total_distributed / total_supply * 100) if total_supply > 0 else 0
            sold_via_dex_pct = (sold_via_dex / total_distributed * 100) if total_distributed > 0 else 0
            transferred_pct = (transferred_to_wallets / total_distributed * 100) if total_distributed > 0 else 0
            burned_pct = (burned / total_distributed * 100) if total_distributed > 0 else 0

            logger.info(f"Distribution analysis: {total_distributed:,.0f} tokens distributed ({total_distributed_pct:.1f}% of supply)")
            logger.info(f"  - Sold via DEX: {sold_via_dex:,.0f} ({sold_via_dex_pct:.1f}%)")
            logger.info(f"  - Transferred: {transferred_to_wallets:,.0f} ({transferred_pct:.1f}%)")
            logger.info(f"  - Burned: {burned:,.0f} ({burned_pct:.1f}%)")

            return {
                "wallet_address": wallet_address,
                "wallet_label": wallet_label,
                "total_distributed": total_distributed,
                "total_distributed_pct": total_distributed_pct,
                "sold_via_dex": sold_via_dex,
                "sold_via_dex_pct": sold_via_dex_pct,
                "transferred_to_wallets": transferred_to_wallets,
                "transferred_to_wallets_pct": transferred_pct,
                "burned": burned,
                "burned_pct": burned_pct,
                "transaction_count": len(distribution_events),
                "transactions": distribution_events[:50],  # Limit to 50 most recent
            }

        except Exception as e:
            logger.error(f"Error analyzing wallet distribution: {e}")
            return self._empty_distribution_result(wallet_address, wallet_label)

    async def analyze_mint_authority_distribution(
        self,
        token_address: str,
        mint_authority: str,
        total_supply: float
    ) -> Dict[str, Any]:
        """
        Analyze token distribution from mint authority wallet.
        Wrapper around analyze_wallet_distribution for backwards compatibility.
        """
        return await self.analyze_wallet_distribution(
            token_address=token_address,
            wallet_address=mint_authority,
            total_supply=total_supply,
            wallet_label="mint_authority"
        )

    async def analyze_creator_distribution(
        self,
        token_address: str,
        creator_address: str,
        total_supply: float
    ) -> Dict[str, Any]:
        """
        Analyze token distribution from the creator/deployer wallet.
        """
        return await self.analyze_wallet_distribution(
            token_address=token_address,
            wallet_address=creator_address,
            total_supply=total_supply,
            wallet_label="creator"
        )

    def _empty_distribution_result(self, wallet_address: str, wallet_label: str = "wallet") -> Dict[str, Any]:
        """Return empty distribution result structure."""
        return {
            "wallet_address": wallet_address,
            "wallet_label": wallet_label,
            "total_distributed": 0,
            "total_distributed_pct": 0,
            "sold_via_dex": 0,
            "sold_via_dex_pct": 0,
            "transferred_to_wallets": 0,
            "transferred_to_wallets_pct": 0,
            "burned": 0,
            "burned_pct": 0,
            "transaction_count": 0,
            "transactions": [],
        }


# Singleton instance
helius_service = HeliusService()
