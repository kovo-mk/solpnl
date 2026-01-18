"""Solscan Pro API integration for token transfer data."""

import asyncio
import aiohttp
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from loguru import logger
from sqlalchemy.orm import Session


class SolscanProAPI:
    """Solscan Pro API client for fetching token transfer data with database caching."""

    def __init__(self, api_key: str, db_session: Optional[Session] = None):
        """Initialize with Solscan Pro API key and optional database session for caching."""
        self.api_key = api_key
        self.base_url = "https://pro-api.solscan.io/v2.0"
        self.db = db_session

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

            # Check cache first if database session is available
            cached_data = []
            latest_cached_timestamp = None

            if self.db:
                cache_result = self._get_from_cache(token_address, days_back)
                if cache_result:
                    cached_data, latest_cached_timestamp = cache_result

                    # Fetch only NEW transfers since last cache (incremental update)
                    if latest_cached_timestamp:
                        start_time = latest_cached_timestamp + 1  # Start from 1 second after latest cached transfer
                        logger.info(
                            f"Incremental fetch: Getting transfers AFTER timestamp {latest_cached_timestamp} "
                            f"(adding to {len(cached_data)} cached transfers)"
                        )

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
                        "block_time[]": start_time,  # Array format: block_time[]=start&block_time[]=end
                        "sort_by": "block_time",
                        "sort_order": "desc",
                        "exclude_amount_zero": "true"  # Skip zero-amount transfers
                    }

                    # Add end time as second array element
                    params["block_time[]"] = [start_time, end_time]

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

            logger.info(f"Fetched {len(all_transfers)} NEW transfers from Solscan Pro")

            # Merge new transfers with cached data (if any)
            if cached_data:
                logger.info(f"Merging {len(all_transfers)} new transfers with {len(cached_data)} cached transfers")
                all_transfers = cached_data + all_transfers
                logger.info(f"Total transfers after merge: {len(all_transfers)}")

            # Save to cache if database session is available
            if self.db and all_transfers:
                self._save_to_cache(token_address, all_transfers, days_back, is_complete=(len(all_transfers) < limit))
                logger.info(f"✓ Saved {len(all_transfers)} total transfers to cache for {token_address[:8]}")

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

    def _get_from_cache(self, token_address: str, days_back: int) -> Optional[Tuple[List[Dict], Optional[int]]]:
        """
        Retrieve cached transfers from database.

        Returns:
            Tuple of (cached_transfers, latest_timestamp) or None if no cache exists
            latest_timestamp is used to fetch only newer transfers incrementally
        """
        if not self.db:
            return None

        try:
            from database.models import SolscanTransferCache

            # Find the most recent cache entry (no expiry check - data never expires)
            cache_entry = (
                self.db.query(SolscanTransferCache)
                .filter(
                    SolscanTransferCache.token_address == token_address,
                )
                .order_by(SolscanTransferCache.cached_at.desc())
                .first()
            )

            if cache_entry:
                transfers = json.loads(cache_entry.transfers_json)
                age_minutes = (datetime.now(timezone.utc) - cache_entry.cached_at).seconds // 60
                logger.info(
                    f"Cache HIT for {token_address[:8]}: "
                    f"{cache_entry.transfer_count} transfers, "
                    f"cached {age_minutes} min ago, "
                    f"latest_timestamp: {cache_entry.latest_timestamp}"
                )
                return transfers, cache_entry.latest_timestamp

            logger.info(f"Cache MISS for {token_address[:8]} - will fetch full history")
            return None

        except Exception as e:
            logger.warning(f"Error reading from cache: {e}")
            return None

    def _save_to_cache(
        self,
        token_address: str,
        transfers: List[Dict],
        days_back: int,
        is_complete: bool
    ) -> None:
        """Save transfers to database cache (permanent historical storage)."""
        if not self.db or not transfers:
            return

        try:
            from database.models import SolscanTransferCache

            # Extract timestamp range from the complete transfer list
            timestamps = [t.get("block_time", 0) for t in transfers if t.get("block_time")]
            earliest_timestamp = min(timestamps) if timestamps else 0
            latest_timestamp = max(timestamps) if timestamps else 0

            # No expiry - data persists permanently
            expires_at = datetime.now(timezone.utc) + timedelta(days=365 * 10)  # Far future date

            # Delete old cache entry (we're replacing with updated merged data)
            self.db.query(SolscanTransferCache).filter(
                SolscanTransferCache.token_address == token_address
            ).delete()

            # Create new cache entry with merged data
            cache_entry = SolscanTransferCache(
                token_address=token_address,
                transfers_json=json.dumps(transfers),
                transfer_count=len(transfers),
                earliest_timestamp=earliest_timestamp,
                latest_timestamp=latest_timestamp,
                days_back=days_back,
                expires_at=expires_at,
                is_complete=is_complete
            )

            self.db.add(cache_entry)
            self.db.commit()

            logger.info(
                f"Cached {len(transfers)} total transfers for {token_address[:8]} "
                f"(range: {earliest_timestamp} to {latest_timestamp})"
            )

        except Exception as e:
            logger.warning(f"Error saving to cache: {e}")
            self.db.rollback()
