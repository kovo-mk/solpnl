"""Background monitor for specific wallet transaction updates."""
import asyncio
import json
from datetime import datetime
from typing import Optional
from loguru import logger

from database.connection import SessionLocal
from database.models import WalletTransactionCache
from services.helius import HeliusService


class WalletMonitor:
    """Monitors specific wallets for new transactions."""

    def __init__(self):
        self.is_running = False
        self.task: Optional[asyncio.Task] = None
        self.monitored_wallets = set()
        self.check_interval_seconds = 60  # Check every minute by default

    def add_wallet(self, wallet_address: str):
        """Add a wallet to monitor."""
        self.monitored_wallets.add(wallet_address)
        logger.info(f"Added wallet to monitor: {wallet_address[:8]}...")

    def remove_wallet(self, wallet_address: str):
        """Remove a wallet from monitoring."""
        self.monitored_wallets.discard(wallet_address)
        logger.info(f"Removed wallet from monitor: {wallet_address[:8]}...")

    def configure(self, interval_seconds: int = 60):
        """Configure monitor settings."""
        self.check_interval_seconds = interval_seconds
        logger.info(f"Wallet monitor configured: interval={interval_seconds}s")

    async def check_wallet_for_new_transactions(self, wallet_address: str) -> dict:
        """
        Check a wallet for new transactions and update cache.

        Returns:
            dict with new_transactions_count and total_transactions_count
        """
        db = SessionLocal()
        try:
            # Get current cache
            cache_entry = db.query(WalletTransactionCache).filter(
                WalletTransactionCache.wallet_address == wallet_address
            ).first()

            if not cache_entry:
                logger.warning(f"No cache entry found for {wallet_address[:8]}, skipping monitor")
                return {"new_transactions": 0, "total_transactions": 0}

            # Load existing transactions
            cached_transactions = json.loads(cache_entry.transactions_json)
            if not cached_transactions:
                logger.warning(f"Cache is empty for {wallet_address[:8]}, skipping")
                return {"new_transactions": 0, "total_transactions": len(cached_transactions)}

            # Get the most recent transaction signature from cache
            latest_signature = cached_transactions[0].get("signature")

            # Fetch new transactions from Helius (only first page, up to 100)
            helius = HeliusService()
            url = f"{helius.base_url}/v0/addresses/{wallet_address}/transactions"
            params = {
                "api-key": helius.api_key,
                "limit": 100,
            }

            import aiohttp
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        logger.error(f"Helius API error for {wallet_address[:8]}: {response.status}")
                        return {"new_transactions": 0, "total_transactions": len(cached_transactions)}

                    new_batch = await response.json()

            if not new_batch:
                logger.debug(f"No new transactions for {wallet_address[:8]}")
                return {"new_transactions": 0, "total_transactions": len(cached_transactions)}

            # Find new transactions (those that appear before our latest cached signature)
            new_transactions = []
            for tx in new_batch:
                if tx.get("signature") == latest_signature:
                    # Found our latest cached transaction, stop here
                    break
                new_transactions.append(tx)

            if not new_transactions:
                logger.debug(f"No new transactions for {wallet_address[:8]}")
                return {"new_transactions": 0, "total_transactions": len(cached_transactions)}

            # Prepend new transactions to the cache (they're newer, so they go at the beginning)
            all_transactions = new_transactions + cached_transactions

            # Update cache
            transactions_json = json.dumps(all_transactions)
            timestamps = [tx.get("timestamp") for tx in all_transactions if tx.get("timestamp")]

            cache_entry.transactions_json = transactions_json
            cache_entry.transaction_count = len(all_transactions)
            cache_entry.updated_at = datetime.utcnow()
            if timestamps:
                cache_entry.earliest_timestamp = min(timestamps)
                cache_entry.latest_timestamp = max(timestamps)

            db.commit()

            logger.info(f"✓ Found {len(new_transactions)} new transaction(s) for {wallet_address[:8]} (total: {len(all_transactions)})")

            return {
                "new_transactions": len(new_transactions),
                "total_transactions": len(all_transactions),
                "latest_signature": new_transactions[0].get("signature") if new_transactions else None,
                "latest_timestamp": new_transactions[0].get("timestamp") if new_transactions else None
            }

        except Exception as e:
            logger.error(f"Error checking wallet {wallet_address[:8]}: {e}")
            return {"new_transactions": 0, "total_transactions": 0, "error": str(e)}
        finally:
            db.close()

    async def run(self):
        """Run the monitor loop."""
        self.is_running = True
        logger.info("Wallet monitor started")

        while self.is_running:
            try:
                if self.monitored_wallets:
                    logger.debug(f"Checking {len(self.monitored_wallets)} wallet(s) for new transactions...")

                    for wallet_address in list(self.monitored_wallets):
                        try:
                            result = await self.check_wallet_for_new_transactions(wallet_address)
                            if result.get("new_transactions", 0) > 0:
                                logger.info(f"Monitor update: {wallet_address[:8]} - {result}")
                        except Exception as e:
                            logger.error(f"Error checking {wallet_address[:8]}: {e}")

                        # Small delay between wallets
                        await asyncio.sleep(1)
                else:
                    logger.debug("No wallets being monitored")

                # Wait for the configured interval
                await asyncio.sleep(self.check_interval_seconds)

            except asyncio.CancelledError:
                logger.info("Wallet monitor cancelled")
                break
            except Exception as e:
                logger.error(f"Error in wallet monitor: {e}")
                await asyncio.sleep(60)

        self.is_running = False
        logger.info("Wallet monitor stopped")

    def start(self):
        """Start the monitor in the background."""
        if self.task is None or self.task.done():
            self.task = asyncio.create_task(self.run())
            logger.info("Wallet monitor task created")
        else:
            logger.warning("Wallet monitor is already running")

    def stop(self):
        """Stop the monitor."""
        self.is_running = False
        if self.task and not self.task.done():
            self.task.cancel()
            logger.info("Wallet monitor stop requested")


# Singleton instance
wallet_monitor = WalletMonitor()
