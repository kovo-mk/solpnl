"""Background scheduler for automatic wallet syncing."""
import asyncio
from datetime import datetime, timedelta
from typing import Optional
from loguru import logger


class SyncScheduler:
    """Manages scheduled automatic syncs for wallets."""

    def __init__(self):
        self.is_running = False
        self.task: Optional[asyncio.Task] = None
        self.sync_interval_hours = 24  # Default: sync every 24 hours
        self.enabled = False

    def configure(self, enabled: bool = False, interval_hours: int = 24):
        """
        Configure auto-sync settings.

        Args:
            enabled: Enable/disable auto-sync
            interval_hours: Hours between automatic syncs
        """
        self.enabled = enabled
        self.sync_interval_hours = interval_hours
        logger.info(f"Auto-sync configured: enabled={enabled}, interval={interval_hours}h")

    async def sync_all_wallets(self):
        """Sync all tracked wallets."""
        from database.connection import SessionLocal
        from database.models import TrackedWallet
        from api.routes import sync_wallet_transactions

        db = SessionLocal()
        try:
            wallets = db.query(TrackedWallet).all()
            logger.info(f"Auto-sync: Processing {len(wallets)} wallets")

            for wallet in wallets:
                try:
                    logger.info(f"Auto-syncing wallet: {wallet.label or wallet.address[:8]}")
                    # Use incremental sync for efficiency
                    await sync_wallet_transactions(wallet.address, wallet.id, incremental=True)
                    await asyncio.sleep(1)  # Small delay between wallets
                except Exception as e:
                    logger.error(f"Failed to auto-sync wallet {wallet.address}: {e}")

            logger.info("Auto-sync completed for all wallets")
        finally:
            db.close()

    async def run(self):
        """Run the scheduler loop."""
        self.is_running = True
        logger.info("Sync scheduler started")

        while self.is_running:
            try:
                if self.enabled:
                    logger.info("Starting scheduled sync...")
                    await self.sync_all_wallets()
                    logger.info(f"Scheduled sync complete. Next sync in {self.sync_interval_hours} hours")
                else:
                    logger.debug("Auto-sync is disabled, skipping")

                # Wait for the configured interval
                await asyncio.sleep(self.sync_interval_hours * 3600)

            except asyncio.CancelledError:
                logger.info("Sync scheduler cancelled")
                break
            except Exception as e:
                logger.error(f"Error in sync scheduler: {e}")
                # Wait a bit before retrying to avoid rapid failures
                await asyncio.sleep(60)

        self.is_running = False
        logger.info("Sync scheduler stopped")

    def start(self):
        """Start the scheduler in the background."""
        if self.task is None or self.task.done():
            self.task = asyncio.create_task(self.run())
            logger.info("Sync scheduler task created")
        else:
            logger.warning("Scheduler is already running")

    def stop(self):
        """Stop the scheduler."""
        self.is_running = False
        if self.task and not self.task.done():
            self.task.cancel()
            logger.info("Sync scheduler stop requested")


# Singleton instance
scheduler = SyncScheduler()
