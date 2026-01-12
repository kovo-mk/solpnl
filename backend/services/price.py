"""Price fetching service using Jupiter and other APIs."""
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import aiohttp
from loguru import logger


class PriceService:
    """Service for fetching token prices."""

    # Jupiter Lite API (free, no API key required until Jan 2026)
    JUPITER_LITE_URL = "https://lite-api.jup.ag/price/v3"
    # Fallback to DexScreener
    DEXSCREENER_URL = "https://api.dexscreener.com/latest/dex/tokens"

    def __init__(self):
        self._sol_price_cache: Optional[float] = None
        self._sol_price_updated: Optional[datetime] = None
        self._token_price_cache: Dict[str, tuple] = {}  # mint -> (price, updated_at)
        self._cache_duration = timedelta(minutes=1)

    async def get_sol_price(self) -> float:
        """Get current SOL price in USD."""
        # Check cache
        if (
            self._sol_price_cache is not None
            and self._sol_price_updated
            and datetime.utcnow() - self._sol_price_updated < self._cache_duration
        ):
            return self._sol_price_cache

        timeout = aiohttp.ClientTimeout(total=10)
        sol_mint = "So11111111111111111111111111111111111111112"

        # Try Jupiter Lite API first
        try:
            url = f"{self.JUPITER_LITE_URL}?ids={sol_mint}"
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        token_data = data.get("data", {}).get(sol_mint)
                        if token_data:
                            price = token_data.get("price")
                            if price:
                                self._sol_price_cache = float(price)
                                self._sol_price_updated = datetime.utcnow()
                                logger.debug(f"Jupiter Lite SOL price: ${price}")
                                return self._sol_price_cache
        except Exception as e:
            logger.warning(f"Jupiter Lite SOL price error: {e}")

        # Fallback to CoinGecko
        try:
            url = "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd"
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        price = data.get("solana", {}).get("usd")
                        if price:
                            self._sol_price_cache = float(price)
                            self._sol_price_updated = datetime.utcnow()
                            return self._sol_price_cache
        except Exception as e:
            logger.warning(f"CoinGecko price error: {e}")

        # Return cached or default
        return self._sol_price_cache or 200.0

    async def get_token_price(self, token_mint: str) -> Optional[float]:
        """
        Get token price in USD.

        Args:
            token_mint: Token mint address

        Returns:
            Price in USD or None if unavailable
        """
        # Check cache
        if token_mint in self._token_price_cache:
            price, updated_at = self._token_price_cache[token_mint]
            if datetime.utcnow() - updated_at < self._cache_duration:
                return price

        timeout = aiohttp.ClientTimeout(total=10)

        # Try Jupiter Lite API first
        try:
            url = f"{self.JUPITER_LITE_URL}?ids={token_mint}"
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        token_data = data.get("data", {}).get(token_mint)
                        if token_data:
                            price = token_data.get("price")
                            if price:
                                self._token_price_cache[token_mint] = (float(price), datetime.utcnow())
                                return float(price)
        except Exception as e:
            logger.warning(f"Jupiter Lite price error for {token_mint[:8]}...: {e}")

        # Fallback to DexScreener
        try:
            url = f"{self.DEXSCREENER_URL}/{token_mint}"
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        pairs = data.get("pairs", [])
                        if pairs:
                            # Get Solana pairs with highest liquidity
                            solana_pairs = [p for p in pairs if p.get("chainId") == "solana"]
                            if solana_pairs:
                                best_pair = max(solana_pairs, key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0))
                                price = best_pair.get("priceUsd")
                                if price:
                                    self._token_price_cache[token_mint] = (float(price), datetime.utcnow())
                                    return float(price)
        except Exception as e:
            logger.warning(f"DexScreener price error for {token_mint[:8]}...: {e}")

        return None

    async def _fetch_jupiter_batch(self, mints: List[str], session: aiohttp.ClientSession) -> Dict[str, float]:
        """Fetch prices for a batch of tokens from Jupiter (max 50 per request)."""
        results = {}
        if not mints:
            return results

        try:
            # Jupiter allows up to 50 tokens per request
            ids_param = ",".join(mints)
            url = f"{self.JUPITER_LITE_URL}?ids={ids_param}"
            timeout = aiohttp.ClientTimeout(total=15)

            async with session.get(url, timeout=timeout) as response:
                if response.status == 200:
                    data = await response.json()
                    token_data = data.get("data", {})

                    for mint in mints:
                        if mint in token_data and token_data[mint]:
                            price = token_data[mint].get("price")
                            if price:
                                results[mint] = float(price)
                                self._token_price_cache[mint] = (float(price), datetime.utcnow())

                    logger.debug(f"Jupiter batch: {len(results)}/{len(mints)} prices found")
                elif response.status == 429:
                    logger.warning("Jupiter rate limit hit, falling back to DexScreener")
                else:
                    logger.warning(f"Jupiter batch error: {response.status}")
        except Exception as e:
            logger.warning(f"Jupiter batch error: {e}")

        return results

    async def _fetch_dexscreener_single(self, mint: str, session: aiohttp.ClientSession) -> Optional[float]:
        """Fetch price for a single token from DexScreener."""
        try:
            url = f"{self.DEXSCREENER_URL}/{mint}"
            timeout = aiohttp.ClientTimeout(total=8)

            async with session.get(url, timeout=timeout) as response:
                if response.status == 200:
                    data = await response.json()
                    pairs = data.get("pairs", [])
                    if pairs:
                        solana_pairs = [p for p in pairs if p.get("chainId") == "solana"]
                        if solana_pairs:
                            best_pair = max(solana_pairs, key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0))
                            price = best_pair.get("priceUsd")
                            if price:
                                return float(price)
        except Exception as e:
            logger.warning(f"DexScreener error for {mint[:8]}...: {e}")

        return None

    async def get_multiple_token_prices(self, token_mints: list) -> Dict[str, Optional[float]]:
        """
        Get prices for multiple tokens efficiently.

        Uses Jupiter Lite API for batch requests (up to 50 tokens at once),
        then falls back to DexScreener for any missing prices.

        Args:
            token_mints: List of token mint addresses

        Returns:
            Dict mapping mint -> price (or None)
        """
        results = {}
        mints_to_fetch = []

        # Check cache first
        for mint in token_mints:
            if mint in self._token_price_cache:
                cached_price, cached_time = self._token_price_cache[mint]
                if datetime.utcnow() - cached_time < self._cache_duration:
                    results[mint] = cached_price
                    continue
            mints_to_fetch.append(mint)

        if not mints_to_fetch:
            return results

        logger.info(f"Fetching prices for {len(mints_to_fetch)} tokens ({len(token_mints) - len(mints_to_fetch)} cached)")

        async with aiohttp.ClientSession() as session:
            # Try Jupiter Lite API first (batch requests, up to 50 tokens each)
            for i in range(0, len(mints_to_fetch), 50):
                batch = mints_to_fetch[i:i + 50]
                jupiter_results = await self._fetch_jupiter_batch(batch, session)
                results.update(jupiter_results)

                # Small delay between batches to avoid rate limiting
                if i + 50 < len(mints_to_fetch):
                    await asyncio.sleep(0.2)

            # Find tokens still missing prices
            missing_mints = [m for m in mints_to_fetch if m not in results]

            if missing_mints:
                logger.info(f"Fetching {len(missing_mints)} missing prices from DexScreener")

                # Limit DexScreener calls to avoid rate limiting
                MAX_DEXSCREENER_CALLS = 20
                for mint in missing_mints[:MAX_DEXSCREENER_CALLS]:
                    price = await self._fetch_dexscreener_single(mint, session)
                    if price:
                        results[mint] = price
                        self._token_price_cache[mint] = (price, datetime.utcnow())
                    await asyncio.sleep(0.15)  # Rate limiting

        logger.info(f"Price fetch complete: {len(results)} prices found for {len(token_mints)} tokens")
        return results


# Singleton instance
price_service = PriceService()
