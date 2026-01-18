"""Wash trading and market manipulation detection."""
import asyncio
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from loguru import logger
import aiohttp


class WashTradingAnalyzer:
    """Analyzes tokens for wash trading and market manipulation patterns."""

    def __init__(self, helius_api_key: Optional[str] = None):
        """Initialize with optional Helius API key for transaction analysis."""
        self.helius_api_key = helius_api_key

    def analyze_trading_patterns(
        self,
        token_address: str,
        holder_data: List[Dict],
        transaction_history: Optional[List[Dict]] = None,
        dex_data: Optional[Dict] = None,
    ) -> Dict:
        """
        Comprehensive wash trading analysis.

        Args:
            token_address: Token mint address
            holder_data: List of top holders with balances
            transaction_history: Optional transaction data
            dex_data: Optional DEX trading data (volume, trades, etc.)

        Returns:
            {
                wash_trading_score: 0-100,
                wash_trading_likelihood: "low"|"medium"|"high"|"critical",
                unique_traders_ratio: float,
                circular_trading_detected: bool,
                suspicious_patterns: [...],
                metrics: {...}
            }
        """
        logger.info(f"Analyzing wash trading patterns for {token_address[:8]}...")

        patterns = []
        score = 0

        # 1. Analyze holder concentration (already have this data)
        concentration_analysis = self._analyze_concentration(holder_data)
        score += concentration_analysis["score"]
        patterns.extend(concentration_analysis["patterns"])

        # 2. Analyze trading volume vs holders
        if dex_data:
            volume_analysis = self._analyze_volume_patterns(holder_data, dex_data)
            score += volume_analysis["score"]
            patterns.extend(volume_analysis["patterns"])

        # 3. Analyze holder acquisition patterns (for airdrop detection)
        acquisition_analysis = self._analyze_holder_acquisition(holder_data)
        score += acquisition_analysis["score"]
        patterns.extend(acquisition_analysis["patterns"])

        # Determine likelihood
        if score >= 75:
            likelihood = "critical"
        elif score >= 50:
            likelihood = "high"
        elif score >= 25:
            likelihood = "medium"
        else:
            likelihood = "low"

        return {
            "wash_trading_score": min(score, 100),
            "wash_trading_likelihood": likelihood,
            "suspicious_patterns": patterns,
            "concentration_risk": concentration_analysis.get("risk_level", "unknown"),
            "airdrop_likelihood": acquisition_analysis.get("airdrop_probability", "low"),
            "metrics": {
                "holder_count": len(holder_data),
                "concentration_score": concentration_analysis["score"],
                "volume_anomaly_score": volume_analysis.get("score", 0) if dex_data else 0,
                "airdrop_score": acquisition_analysis["score"],
            }
        }

    def _analyze_concentration(self, holder_data: List[Dict]) -> Dict:
        """Analyze holder concentration for manipulation risk."""
        patterns = []
        score = 0

        if not holder_data:
            return {"score": 0, "patterns": [], "risk_level": "unknown"}

        # Sort by balance
        sorted_holders = sorted(holder_data, key=lambda x: x.get("balance", 0), reverse=True)
        total_holders = len(sorted_holders)

        # Calculate concentration metrics
        top_1_pct = sorted_holders[0].get("percentage", 0) if sorted_holders else 0
        top_5_pct = sum(h.get("percentage", 0) for h in sorted_holders[:5])
        top_10_pct = sum(h.get("percentage", 0) for h in sorted_holders[:10])

        # Very high single holder concentration
        if top_1_pct > 30:
            patterns.append("extreme_single_holder_control")
            score += 35
        elif top_1_pct > 20:
            patterns.append("high_single_holder_control")
            score += 20

        # Top 5 concentration
        if top_5_pct > 70:
            patterns.append("extreme_top5_concentration")
            score += 25
        elif top_5_pct > 50:
            patterns.append("high_top5_concentration")
            score += 15

        # Top 10 concentration
        if top_10_pct > 85:
            patterns.append("extreme_top10_concentration")
            score += 20
        elif top_10_pct > 70:
            patterns.append("high_top10_concentration")
            score += 10

        # Determine risk level
        if score >= 50:
            risk_level = "critical"
        elif score >= 30:
            risk_level = "high"
        elif score >= 15:
            risk_level = "medium"
        else:
            risk_level = "low"

        return {
            "score": score,
            "patterns": patterns,
            "risk_level": risk_level,
            "top_1_percentage": top_1_pct,
            "top_5_percentage": top_5_pct,
            "top_10_percentage": top_10_pct,
        }

    def _analyze_volume_patterns(self, holder_data: List[Dict], dex_data: Dict) -> Dict:
        """Analyze volume vs holders for wash trading indicators."""
        patterns = []
        score = 0

        volume_24h = dex_data.get("volume_24h", 0)
        txns_24h = dex_data.get("txns_24h", {})
        buys = txns_24h.get("buys", 0)
        sells = txns_24h.get("sells", 0)
        total_txns = buys + sells

        holder_count = len(holder_data)

        # Calculate traders per volume ratio
        if volume_24h > 0 and total_txns > 0:
            avg_trade_size = volume_24h / total_txns

            # If average trade is very large compared to holder count
            if holder_count > 0:
                ratio = total_txns / holder_count

                # Very few unique traders relative to transaction count
                if ratio < 0.1:  # Less than 10% of holders are trading
                    patterns.append("low_unique_trader_ratio")
                    score += 25
                elif ratio < 0.3:
                    patterns.append("moderate_unique_trader_ratio")
                    score += 15

        # High volume but low holder count
        if volume_24h > 100000 and holder_count < 100:
            patterns.append("high_volume_low_holders")
            score += 20

        # Suspicious buy/sell ratio (perfectly balanced = wash trading)
        if buys > 0 and sells > 0:
            buy_sell_ratio = min(buys, sells) / max(buys, sells)
            if buy_sell_ratio > 0.95:  # 95%+ balanced
                patterns.append("perfectly_balanced_buys_sells")
                score += 30

        # Very high transaction count relative to holders
        if total_txns > holder_count * 10:
            patterns.append("excessive_transaction_frequency")
            score += 20

        return {
            "score": score,
            "patterns": patterns,
            "volume_24h": volume_24h,
            "total_transactions": total_txns,
            "unique_holders": holder_count,
        }

    def _analyze_holder_acquisition(self, holder_data: List[Dict]) -> Dict:
        """Analyze holder acquisition patterns for airdrop schemes."""
        patterns = []
        score = 0

        if not holder_data:
            return {"score": 0, "patterns": [], "airdrop_probability": "unknown"}

        # Check for identical or very similar balances (airdrop indicator)
        balances = [h.get("balance", 0) for h in holder_data]
        balance_counts = defaultdict(int)

        for balance in balances:
            # Round to avoid floating point precision issues
            rounded = round(balance, 2)
            balance_counts[rounded] += 1

        # Find most common balance
        if balance_counts:
            max_identical = max(balance_counts.values())
            total_holders = len(balances)

            # Many holders with identical balances
            if max_identical >= total_holders * 0.5:  # 50%+ have same balance
                patterns.append("massive_identical_balance_clustering")
                score += 40
            elif max_identical >= total_holders * 0.3:  # 30%+ have same balance
                patterns.append("high_identical_balance_clustering")
                score += 25
            elif max_identical >= total_holders * 0.15:  # 15%+ have same balance
                patterns.append("moderate_identical_balance_clustering")
                score += 15

        # Check for round number clustering (common in airdrops)
        round_numbers = 0
        for balance in balances:
            # Check if balance is a round number (1000, 5000, 10000, etc.)
            if balance >= 100 and balance % 100 == 0:
                round_numbers += 1

        if round_numbers >= len(balances) * 0.4:  # 40%+ are round numbers
            patterns.append("round_number_clustering")
            score += 20

        # Determine airdrop probability
        if score >= 50:
            airdrop_prob = "critical"
        elif score >= 30:
            airdrop_prob = "high"
        elif score >= 15:
            airdrop_prob = "medium"
        else:
            airdrop_prob = "low"

        return {
            "score": score,
            "patterns": patterns,
            "airdrop_probability": airdrop_prob,
            "identical_balance_count": max(balance_counts.values()) if balance_counts else 0,
            "round_number_percentage": round_numbers / len(balances) if balances else 0,
        }

    def generate_wash_trading_summary(self, analysis: Dict) -> str:
        """Generate human-readable summary of wash trading analysis."""
        score = analysis["wash_trading_score"]
        likelihood = analysis["wash_trading_likelihood"]
        patterns = analysis["suspicious_patterns"]

        summary = f"Wash Trading Risk: {likelihood.upper()} (Score: {score}/100)\n\n"

        if likelihood in ["high", "critical"]:
            summary += "⚠️ SIGNIFICANT MANIPULATION INDICATORS DETECTED\n\n"

        if "extreme_single_holder_control" in patterns:
            summary += "• Single wallet controls >30% of supply - extreme dump risk\n"
        if "perfectly_balanced_buys_sells" in patterns:
            summary += "• Buy/sell ratio suspiciously balanced - possible wash trading\n"
        if "low_unique_trader_ratio" in patterns:
            summary += "• Very few unique traders relative to volume - artificial activity\n"
        if "massive_identical_balance_clustering" in patterns:
            summary += "• Massive airdrop detected - 50%+ holders have identical balances\n"
        if "high_volume_low_holders" in patterns:
            summary += "• High trading volume but very few holders - manipulation likely\n"

        if analysis.get("airdrop_likelihood") in ["high", "critical"]:
            summary += "\n🎁 AIRDROP SCHEME DETECTED\n"
            summary += "This token shows strong signs of mass airdrop distribution, often used to:\n"
            summary += "• Create artificial holder counts\n"
            summary += "• Generate fake social proof\n"
            summary += "• Dump tokens on unsuspecting buyers\n"

        return summary

    async def fetch_rpc_transactions(
        self,
        token_address: str,
        limit: int = 1000,
        days_back: int = 30
    ) -> List[Dict]:
        """
        Fetch token transactions using Helius RPC (Solana JSON-RPC methods).

        Uses getSignaturesForAddress to get all transaction signatures
        for the token mint address, then fetches details for each.

        Args:
            token_address: Token mint address
            limit: Max transactions to fetch (default 1000)
            days_back: Days to look back (default 30)

        Returns:
            List of transaction dictionaries in Helius-compatible format
        """
        if not self.helius_api_key:
            logger.warning("No Helius API key provided")
            return []

        logger.info(f"Fetching RPC transactions for {token_address[:8]}... (limit: {limit})")

        try:
            time_cutoff = int((datetime.now() - timedelta(days=days_back)).timestamp())
            url = f"https://mainnet.helius-rpc.com/?api-key={self.helius_api_key}"

            transactions = []
            before_signature = None

            async with aiohttp.ClientSession() as session:
                # Fetch signatures in batches of 100
                while len(transactions) < limit:
                    # Get signatures for the token address
                    params = [token_address, {"limit": min(100, limit - len(transactions))}]
                    if before_signature:
                        params[1]["before"] = before_signature

                    payload = {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "getSignaturesForAddress",
                        "params": params
                    }

                    async with session.post(url, json=payload) as response:
                        if response.status != 200:
                            logger.error(f"RPC error: {response.status}")
                            break

                        data = await response.json()
                        signatures = data.get("result", [])

                        if not signatures:
                            logger.info("No more signatures")
                            break

                        # Filter signatures by time first
                        valid_signatures = []
                        for sig_info in signatures:
                            block_time = sig_info.get("blockTime", 0)
                            if block_time < time_cutoff:
                                logger.info(f"Reached time cutoff at {len(transactions)} transactions")
                                return transactions
                            valid_signatures.append(sig_info)

                        # Batch fetch transaction details (10 at a time to avoid overwhelming the RPC)
                        batch_size = 10
                        for i in range(0, len(valid_signatures), batch_size):
                            batch = valid_signatures[i:i + batch_size]

                            # Create batch RPC request
                            batch_payloads = [
                                {
                                    "jsonrpc": "2.0",
                                    "id": idx,
                                    "method": "getParsedTransaction",
                                    "params": [
                                        sig_info["signature"],
                                        {
                                            "encoding": "jsonParsed",
                                            "maxSupportedTransactionVersion": 0
                                        }
                                    ]
                                }
                                for idx, sig_info in enumerate(batch)
                            ]

                            async with session.post(url, json=batch_payloads) as tx_response:
                                if tx_response.status == 200:
                                    batch_results = await tx_response.json()

                                    # Handle both single response and batch response
                                    if not isinstance(batch_results, list):
                                        batch_results = [batch_results]

                                    for result_data, sig_info in zip(batch_results, batch):
                                        tx_result = result_data.get("result")

                                        if tx_result:
                                            # Parse token transfers from transaction
                                            token_transfers = self._parse_token_transfers(
                                                tx_result, token_address
                                            )

                                            if token_transfers:  # Only include if has token transfers
                                                transactions.append({
                                                    "signature": sig_info["signature"],
                                                    "timestamp": sig_info.get("blockTime", 0),
                                                    "type": "TRANSFER",
                                                    "source": "rpc",
                                                    "tokenTransfers": token_transfers,
                                                })

                            # Rate limiting between batches
                            await asyncio.sleep(0.1)

                            if len(transactions) >= limit:
                                break

                        if len(transactions) >= limit:
                            break

                        # Set pagination cursor
                        if len(signatures) == 100:
                            before_signature = signatures[-1]["signature"]
                        else:
                            break  # No more data

            logger.info(f"Fetched {len(transactions)} transactions via RPC")
            return transactions

        except Exception as e:
            logger.error(f"Error fetching RPC transactions: {e}")
            return []

    def _parse_token_transfers(self, tx_result: Dict, token_address: str) -> List[Dict]:
        """Parse token transfers from a parsed transaction."""
        token_transfers = []

        try:
            # Get instructions from transaction
            instructions = tx_result.get("transaction", {}).get("message", {}).get("instructions", [])

            for instruction in instructions:
                if instruction.get("program") == "spl-token" and instruction.get("parsed"):
                    parsed = instruction["parsed"]
                    info = parsed.get("info", {})

                    # Check if it's a transfer of our token
                    if parsed.get("type") == "transfer" and info.get("mint") == token_address:
                        token_transfers.append({
                            "mint": token_address,
                            "fromUserAccount": info.get("source"),
                            "toUserAccount": info.get("destination"),
                            "tokenAmount": int(info.get("amount", 0)),
                        })

        except Exception as e:
            logger.error(f"Error parsing token transfers: {e}")

        return token_transfers

    async def analyze_helius_transactions(
        self,
        token_address: str,
        limit: int = 500,
        days_back: int = 7
    ) -> Dict:
        """
        Analyze actual trading transactions using Solscan API (primary) or Helius (fallback).

        Detects:
        - Wash trading (same wallets trading back and forth)
        - Bot trading patterns (rapid automated trading)
        - Circular trading (A->B->C->A patterns)
        - Coordinated wallet activity (Sybil attacks)
        - Volume manipulation

        Args:
            token_address: Token mint address
            limit: Number of recent transactions to analyze (max 1000)
            days_back: Number of days to look back (default 7)

        Returns:
            {
                wash_trading_score: 0-100,
                unique_traders: int,
                total_transactions: int,
                suspicious_wallet_pairs: [...],
                circular_trading_rings: [...],
                bot_activity_detected: bool,
                rapid_trade_count: int,
                metrics: {...}
            }
        """
        logger.info(f"Fetching up to {limit} transactions for {token_address[:8]} (last {days_back} days)...")

        try:
            # Try RPC method first (uses standard Solana JSON-RPC with Helius)
            transactions = await self.fetch_rpc_transactions(
                token_address=token_address,
                limit=limit,
                days_back=days_back
            )

            # If RPC fails or returns no data, fallback to Helius Enhanced Transactions API
            if not transactions:
                logger.warning("RPC returned no transactions, trying Helius Enhanced API fallback...")

                if not self.helius_api_key:
                    logger.warning("No Helius API key provided, cannot fetch transactions")
                    return self._empty_transaction_analysis()

                # Calculate time filter (Unix timestamp for X days ago)
                time_cutoff = int((datetime.now() - timedelta(days=days_back)).timestamp())

                transactions = []
                before_signature = None
                max_requests = min(limit // 100 + 1, 10)  # Max 10 requests (1000 transactions)

                async with aiohttp.ClientSession() as session:
                    for i in range(max_requests):
                        url = f"https://api-mainnet.helius-rpc.com/v0/addresses/{token_address}/transactions"
                        params = {
                            "api-key": self.helius_api_key,
                            "limit": 100,  # Helius max per request
                            # Remove type filter to get ALL transactions (swaps, transfers, burns, etc.)
                            # "type": "SWAP",  # OLD: Only swaps
                            "gte-time": time_cutoff,  # Only last X days
                        }

                        # Add pagination
                        if before_signature:
                            params["before-signature"] = before_signature

                        async with session.get(url, params=params) as response:
                            if response.status == 200:
                                batch = await response.json()
                                if not batch:
                                    break  # No more transactions

                                transactions.extend(batch)
                                logger.info(f"Helius batch {i+1}: {len(batch)} transactions (total: {len(transactions)})")

                                # Check if we have enough
                                if len(transactions) >= limit:
                                    transactions = transactions[:limit]
                                    break

                                # Set pagination cursor to last transaction signature
                                if len(batch) == 100:  # Only paginate if we got a full batch
                                    before_signature = batch[-1].get("signature")
                                else:
                                    break  # Less than 100 = no more data
                            else:
                                logger.error(f"Helius API error: {response.status}")
                                if i == 0:  # Only fail if first request fails
                                    return self._empty_transaction_analysis()
                                break  # Use what we have

            if not transactions:
                logger.info("No transactions found")
                return self._empty_transaction_analysis()

            logger.info(f"Analyzing {len(transactions)} transactions from last {days_back} days...")

            # Analyze trading patterns
            return self._analyze_transaction_patterns(token_address, transactions)

        except Exception as e:
            logger.error(f"Error fetching Helius transactions: {e}")
            return self._empty_transaction_analysis()

    def _analyze_transaction_patterns(
        self,
        token_address: str,
        transactions: List[Dict]
    ) -> Dict:
        """Analyze transaction patterns for wash trading indicators."""

        # Known DEX programs and liquidity pools to filter out
        KNOWN_DEX_PROGRAMS = {
            "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8",  # Raydium AMM
            "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1",  # Raydium V4
            "CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK",  # Raydium CLMM
            "JUP4Fb2cqiRUcaTHdrPC8h2gNsA2ETXiPDD33WcGuJB",   # Jupiter
            "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4",   # Jupiter V6
            "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc",   # Orca Whirlpool
            "9W959DqEETiGZocYWCQPaJ6sBmUzgfxXfqGeTEdp3aQP",   # Orca V2
        }

        wallet_trades = defaultdict(list)  # wallet -> list of trades
        wallet_counterparties = defaultdict(set)  # wallet -> set of counterparties
        trade_pairs = defaultdict(int)  # (wallet1, wallet2) -> count
        rapid_trades = []  # trades within 60 seconds
        bot_patterns = defaultdict(int)  # wallet -> count of bot-like behavior

        # Track circular trading (A->B->C->A)
        wallet_connections = defaultdict(list)  # from_wallet -> [(to_wallet, timestamp)]

        # Track transaction types for comprehensive analysis
        tx_type_counts = defaultdict(int)  # type -> count
        swap_count = 0
        transfer_count = 0
        burn_count = 0
        unknown_count = 0

        patterns = []
        score = 0

        for tx in transactions:
            timestamp = tx.get("timestamp")
            token_transfers = tx.get("tokenTransfers", [])
            tx_type = tx.get("type", "UNKNOWN")
            source = tx.get("source", "")

            # Count transaction types
            tx_type_counts[tx_type] += 1
            if tx_type == "SWAP":
                swap_count += 1
            elif tx_type in ["TRANSFER", "TOKEN_TRANSFER"]:
                transfer_count += 1
            elif tx_type == "BURN":
                burn_count += 1
            else:
                unknown_count += 1

            # Find transfers involving our token
            for transfer in token_transfers:
                mint = transfer.get("mint")
                if mint != token_address:
                    continue

                from_addr = transfer.get("fromUserAccount")
                to_addr = transfer.get("toUserAccount")
                amount = transfer.get("tokenAmount", 0)

                if not from_addr or not to_addr:
                    continue

                # Track wallet activity (include DEX programs for analysis)
                wallet_trades[from_addr].append({
                    "timestamp": timestamp,
                    "type": "sell",
                    "amount": amount,
                    "counterparty": to_addr,
                    "source": source
                })
                wallet_trades[to_addr].append({
                    "timestamp": timestamp,
                    "type": "buy",
                    "amount": amount,
                    "counterparty": from_addr,
                    "source": source
                })

                # Track counterparties
                wallet_counterparties[from_addr].add(to_addr)
                wallet_counterparties[to_addr].add(from_addr)

                # Track pairs
                pair = tuple(sorted([from_addr, to_addr]))
                trade_pairs[pair] += 1

                # Track connections for circular trading
                wallet_connections[from_addr].append((to_addr, timestamp))

                # Check for rapid trading (bot detection)
                if from_addr in wallet_trades and len(wallet_trades[from_addr]) > 1:
                    last_trade = wallet_trades[from_addr][-2]
                    time_diff = timestamp - last_trade["timestamp"]
                    if time_diff < 60:  # Less than 60 seconds
                        rapid_trades.append({
                            "wallet": from_addr,
                            "time_gap": time_diff,
                            "source": source
                        })
                        bot_patterns[from_addr] += 1

        # 1. Detect wash trading (same pairs trading repeatedly)
        suspicious_pairs = [(pair, count) for pair, count in trade_pairs.items() if count >= 3]
        if suspicious_pairs:
            patterns.append("repeated_wallet_pairs")
            score += min(len(suspicious_pairs) * 10, 40)

            # Very suspicious if same pair trades 10+ times
            very_suspicious = [p for p, c in suspicious_pairs if c >= 10]
            if very_suspicious:
                patterns.append("extreme_wash_trading")
                score += 30

        # 2. Detect low unique trader ratio
        unique_traders = len(wallet_trades)
        total_trades = len(transactions)
        trader_ratio = unique_traders / total_trades if total_trades > 0 else 0

        if trader_ratio < 0.2:  # Less than 20% unique traders
            patterns.append("very_low_unique_traders")
            score += 35
        elif trader_ratio < 0.4:
            patterns.append("low_unique_traders")
            score += 20

        # 3. Detect bot activity
        bot_wallets = [w for w, count in bot_patterns.items() if count >= 5]
        if bot_wallets:
            patterns.append("bot_trading_detected")
            score += min(len(bot_wallets) * 5, 25)

        # 4. Detect wallets with very few counterparties (same wallets trading with each other)
        isolated_traders = []
        for wallet, counterparties in wallet_counterparties.items():
            if len(wallet_trades[wallet]) >= 5 and len(counterparties) <= 2:
                isolated_traders.append(wallet)

        if isolated_traders:
            patterns.append("isolated_trading_groups")
            score += 20

        # 5. Detect circular trading rings
        circular_rings = self._detect_circular_trading(wallet_connections)
        if circular_rings:
            patterns.append("circular_trading_detected")
            score += min(len(circular_rings) * 15, 30)

        # Build detailed wallet lists with labels
        def get_wallet_label(wallet: str) -> str:
            """Get human-readable label for wallet."""
            if wallet in KNOWN_DEX_PROGRAMS:
                dex_labels = {
                    "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8": "Raydium AMM",
                    "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1": "Raydium V4",
                    "CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK": "Raydium CLMM",
                    "JUP4Fb2cqiRUcaTHdrPC8h2gNsA2ETXiPDD33WcGuJB": "Jupiter",
                    "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4": "Jupiter V6",
                    "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc": "Orca Whirlpool",
                    "9W959DqEETiGZocYWCQPaJ6sBmUzgfxXfqGeTEdp3aQP": "Orca V2",
                }
                return dex_labels.get(wallet, "DEX Program")
            return None

        # Build suspicious wallet details (exclude DEX programs from display)
        suspicious_wallet_details = []

        # Add wallets involved in repeated pairs (skip if wallet1 is a DEX program)
        for (wallet1, wallet2), count in suspicious_pairs:
            # Skip if the primary wallet is a DEX program
            if wallet1 in KNOWN_DEX_PROGRAMS:
                continue

            label1 = get_wallet_label(wallet1)
            label2 = get_wallet_label(wallet2)
            suspicious_wallet_details.append({
                "wallet1": wallet1,
                "wallet2": wallet2,
                "wallet1_label": label1,
                "wallet2_label": label2,
                "trade_count": count,
                "pattern": "repeated_pairs"
            })

        # Add bot wallets (skip DEX programs)
        for wallet in bot_wallets:
            # Skip if wallet is a DEX program
            if wallet in KNOWN_DEX_PROGRAMS:
                continue

            label = get_wallet_label(wallet)
            if not any(w["wallet1"] == wallet or w.get("wallet2") == wallet for w in suspicious_wallet_details):
                suspicious_wallet_details.append({
                    "wallet1": wallet,
                    "wallet1_label": label,
                    "trade_count": len(wallet_trades[wallet]),
                    "pattern": "bot_activity"
                })

        # Add isolated traders (skip DEX programs)
        for wallet in isolated_traders:
            # Skip if wallet is a DEX program
            if wallet in KNOWN_DEX_PROGRAMS:
                continue

            label = get_wallet_label(wallet)
            if not any(w["wallet1"] == wallet or w.get("wallet2") == wallet for w in suspicious_wallet_details):
                suspicious_wallet_details.append({
                    "wallet1": wallet,
                    "wallet1_label": label,
                    "trade_count": len(wallet_trades[wallet]),
                    "counterparties": len(wallet_counterparties[wallet]),
                    "pattern": "isolated_trading"
                })

        # Calculate final metrics
        return {
            "wash_trading_score": min(score, 100),
            "unique_traders": unique_traders,
            "total_transactions": total_trades,
            "trader_ratio": trader_ratio,
            "suspicious_wallet_pairs": len(suspicious_pairs),
            "bot_wallets_detected": len(bot_wallets),
            "rapid_trade_count": len(rapid_trades),
            "circular_trading_rings": len(circular_rings),
            "suspicious_patterns": patterns,
            "top_suspicious_pairs": sorted(suspicious_pairs, key=lambda x: x[1], reverse=True)[:5],
            "suspicious_wallets": suspicious_wallet_details[:20],  # Limit to top 20
            # Transaction type breakdown for comprehensive analysis
            "transaction_breakdown": {
                "swaps": swap_count,
                "transfers": transfer_count,
                "burns": burn_count,
                "other": unknown_count,
                "total": len(transactions),
                "by_type": dict(tx_type_counts)
            },
            "metrics": {
                "unique_traders": unique_traders,
                "total_transactions": total_trades,
                "trader_ratio": trader_ratio,
                "wash_trading_score": min(score, 100),
                "bot_activity": len(bot_wallets) > 0,
                "transaction_types": dict(tx_type_counts)
            }
        }

    def _detect_circular_trading(
        self,
        connections: Dict[str, List[Tuple[str, int]]]
    ) -> List[List[str]]:
        """Detect circular trading patterns (A->B->C->A)."""
        rings = []

        # Simple 3-wallet ring detection
        for wallet_a in connections:
            for wallet_b, _ in connections.get(wallet_a, []):
                for wallet_c, _ in connections.get(wallet_b, []):
                    # Check if C trades back to A
                    for wallet_d, _ in connections.get(wallet_c, []):
                        if wallet_d == wallet_a:
                            ring = sorted([wallet_a, wallet_b, wallet_c])
                            if ring not in rings:
                                rings.append(ring)

        return rings

    def _empty_transaction_analysis(self) -> Dict:
        """Return empty analysis when transactions unavailable."""
        return {
            "wash_trading_score": 0,
            "unique_traders": 0,
            "total_transactions": 0,
            "trader_ratio": 0,
            "suspicious_wallet_pairs": 0,
            "bot_wallets_detected": 0,
            "rapid_trade_count": 0,
            "circular_trading_rings": 0,
            "suspicious_patterns": [],
            "top_suspicious_pairs": [],
            "metrics": {
                "unique_traders": 0,
                "total_transactions": 0,
                "trader_ratio": 0,
                "wash_trading_score": 0,
                "bot_activity": False
            }
        }
