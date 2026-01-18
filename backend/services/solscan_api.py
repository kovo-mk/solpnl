"""Solscan Pro API integration for token transfer data."""

import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import Dict, List
from loguru import logger


class SolscanProAPI:
    """Solscan Pro API client for fetching token transfer data."""

    def __init__(self, api_key: str):
        """Initialize with Solscan Pro API key."""
        self.api_key = api_key
        self.base_url = "https://pro-api.solscan.io/v2.0"

    async def fetch_token_transfers(
        self,
        token_address: str,
        limit: int = 1000,
        days_back: int = 30
    ) -> List[Dict]:
        """
        Fetch token transfers from Solscan Pro API.

        Args:
            token_address: Token mint address
            limit: Max transfers to fetch
            days_back: Days to look back

        Returns:
            List of transactions in Helius-compatible format
        """
        logger.info(f"Fetching token transfers from Solscan Pro for {token_address[:8]}...")
        logger.info(f"API Key present: {bool(self.api_key)}, Key length: {len(self.api_key) if self.api_key else 0}")

        try:
            # Calculate time range
            end_time = int(datetime.now().timestamp())
            start_time = int((datetime.now() - timedelta(days=days_back)).timestamp())

            logger.info(f"Time range: {start_time} to {end_time} ({days_back} days)")

            all_transfers = []
            page = 1
            page_size = 100  # Max per request

            headers = {
                "token": self.api_key,
                "accept": "application/json"
            }

            logger.info(f"Request headers: token={self.api_key[:10]}...")

            async with aiohttp.ClientSession() as session:
                while len(all_transfers) < limit:
                    url = f"{self.base_url}/token/transfer"
                    params = {
                        "address": token_address,
                        "page": page,
                        "page_size": page_size,
                        "block_time": f"{start_time},{end_time}",
                        "sort_by": "block_time",
                        "sort_order": "desc",
                        "exclude_amount_zero": "true"  # Skip zero-amount transfers
                    }

                    logger.info(f"Fetching page {page} from {url}")
                    logger.info(f"Params: {params}")

                    async with session.get(url, headers=headers, params=params) as response:
                        if response.status != 200:
                            error_text = await response.text()
                            logger.error(f"Solscan API error: {response.status}")
                            logger.error(f"Response: {error_text[:500]}")
                            logger.error(f"Request URL: {url}")
                            logger.error(f"Request params: {params}")
                            break

                        data = await response.json()

                        if not data.get("success"):
                            logger.error(f"Solscan API returned success=false: {data}")
                            break

                        transfers = data.get("data", [])

                        if not transfers:
                            logger.info(f"No more transfers (page {page})")
                            break

                        all_transfers.extend(transfers)
                        logger.info(f"  Fetched {len(transfers)} transfers (total: {len(all_transfers)})")

                        # Check if we have all data
                        if len(transfers) < page_size:
                            logger.info("Received less than full page - no more data")
                            break

                        if len(all_transfers) >= limit:
                            break

                        page += 1

                        # Rate limiting
                        await asyncio.sleep(0.1)

            logger.info(f"Fetched {len(all_transfers)} total transfers from Solscan Pro")

            # Convert to Helius-compatible format
            transactions = self._convert_to_helius_format(all_transfers, token_address)

            return transactions[:limit]

        except Exception as e:
            logger.error(f"Error fetching Solscan Pro transfers: {e}")
            return []

    def _convert_to_helius_format(self, transfers: List[Dict], token_address: str) -> List[Dict]:
        """Convert Solscan transfer format to Helius-compatible format."""
        transactions = []
        seen_trans_ids = set()

        for transfer in transfers:
            trans_id = transfer.get("trans_id")

            # Group transfers by transaction ID
            if trans_id not in seen_trans_ids:
                seen_trans_ids.add(trans_id)

                # Find all transfers for this transaction
                tx_transfers = [t for t in transfers if t.get("trans_id") == trans_id]

                # Convert to Helius format
                token_transfers = []
                for t in tx_transfers:
                    token_transfers.append({
                        "mint": token_address,
                        "fromUserAccount": t.get("from_address"),
                        "toUserAccount": t.get("to_address"),
                        "tokenAmount": int(t.get("amount", 0)),
                    })

                transactions.append({
                    "signature": trans_id,
                    "timestamp": transfer.get("block_time", 0),
                    "type": self._map_activity_type(transfer.get("activity_type")),
                    "source": "solscan_pro",
                    "tokenTransfers": token_transfers,
                })

        return transactions

    def _map_activity_type(self, activity_type: str) -> str:
        """Map Solscan activity types to Helius types."""
        mapping = {
            "ACTIVITY_SPL_TRANSFER": "TRANSFER",
            "ACTIVITY_SPL_MINT": "TOKEN_MINT",
            "ACTIVITY_SPL_BURN": "BURN",
        }
        return mapping.get(activity_type, "TRANSFER")
