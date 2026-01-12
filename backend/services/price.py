"""Price fetching service using Jupiter and other APIs."""
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict
import aiohttp
from loguru import logger


class PriceService:
    """Service for fetching token prices."""

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

        # Try CoinGecko
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

        # Fallback to Jupiter
        try:
            sol_mint = "So11111111111111111111111111111111111111112"
            url = f"https://api.jup.ag/price/v2?ids={sol_mint}"
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        price = data.get("data", {}).get(sol_mint, {}).get("price")
                        if price:
                            self._sol_price_cache = float(price)
                            self._sol_price_updated = datetime.utcnow()
                            return self._sol_price_cache
        except Exception as e:
            logger.warning(f"Jupiter SOL price error: {e}")

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

        # Try Jupiter v2 API
        try:
            url = f"https://api.jup.ag/price/v2?ids={token_mint}"
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        price = data.get("data", {}).get(token_mint, {}).get("price")
                        if price:
                            self._token_price_cache[token_mint] = (float(price), datetime.utcnow())
                            return float(price)
        except Exception as e:
            logger.warning(f"Jupiter v2 price error for {token_mint[:8]}...: {e}")

        # Try Jupiter v4 API
        try:
            url = f"https://price.jup.ag/v4/price?ids={token_mint}"
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        price = data.get("data", {}).get(token_mint, {}).get("price")
                        if price:
                            self._token_price_cache[token_mint] = (float(price), datetime.utcnow())
                            return float(price)
        except Exception as e:
            logger.warning(f"Jupiter v4 price error for {token_mint[:8]}...: {e}")

        # Try DexScreener
        try:
            url = f"https://api.dexscreener.com/latest/dex/tokens/{token_mint}"
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        pairs = data.get("pairs", [])
                        if pairs:
                            price = pairs[0].get("priceUsd")
                            if price:
                                self._token_price_cache[token_mint] = (float(price), datetime.utcnow())
                                return float(price)
        except Exception as e:
            logger.warning(f"DexScreener price error for {token_mint[:8]}...: {e}")

        return None

    async def get_multiple_token_prices(self, token_mints: list) -> Dict[str, Optional[float]]:
        """
        Get prices for multiple tokens efficiently using DexScreener.

        Args:
            token_mints: List of token mint addresses

        Returns:
            Dict mapping mint -> price (or None)
        """
        results = {}

        # DexScreener is now the primary source (Jupiter requires API key)
        logger.info(f"Fetching prices for {len(token_mints)} tokens from DexScreener")

        # Limit number of API calls to avoid rate limiting
        MAX_DEXSCREENER_CALLS = 40
        mints_to_check = token_mints[:MAX_DEXSCREENER_CALLS]

        async with aiohttp.ClientSession() as session:
            for mint in mints_to_check:
                # Check cache first
                if mint in self._token_price_cache:
                    cached_price, cached_time = self._token_price_cache[mint]
                    if datetime.utcnow() - cached_time < self._cache_duration:
                        results[mint] = cached_price
                        continue

                try:
                    url = f"https://api.dexscreener.com/latest/dex/tokens/{mint}"
                    timeout = aiohttp.ClientTimeout(total=8)
                    async with session.get(url, timeout=timeout) as response:
                        if response.status == 200:
                            data = await response.json()
                            pairs = data.get("pairs", [])
                            if pairs:
                                # Get the pair with highest liquidity on Solana
                                solana_pairs = [p for p in pairs if p.get("chainId") == "solana"]
                                if solana_pairs:
                                    best_pair = max(solana_pairs, key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0))
                                    price = best_pair.get("priceUsd")
                                    if price:
                                        results[mint] = float(price)
                                        self._token_price_cache[mint] = (float(price), datetime.utcnow())
                                        logger.debug(f"DexScreener price for {mint[:8]}...: ${price}")
                    await asyncio.sleep(0.1)  # Rate limiting for DexScreener
                except asyncio.TimeoutError:
                    logger.warning(f"DexScreener timeout for {mint[:8]}...")
                except Exception as e:
                    logger.warning(f"DexScreener error for {mint[:8]}...: {e}")

        logger.info(f"Price fetch complete: {len(results)} prices found for {len(token_mints)} tokens")
        return results


# Singleton instance
price_service = PriceService()
