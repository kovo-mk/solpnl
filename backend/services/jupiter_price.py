"""Jupiter Price API service for accurate Solana token prices."""
import aiohttp
from typing import Dict, List, Optional
from loguru import logger


class JupiterPriceService:
    """Service for fetching token prices from Jupiter API."""

    def __init__(self):
        self.base_url = "https://api.jup.ag/price/v2"
        # Jupiter uses token mint addresses as IDs
        self.vsToken = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"  # USDC

    async def get_token_price(self, token_mint: str) -> Optional[float]:
        """
        Get price for a single token from Jupiter.

        Args:
            token_mint: Token mint address

        Returns:
            Price in USD or None if not found
        """
        try:
            url = f"{self.base_url}?ids={token_mint}"

            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        logger.warning(f"Jupiter API error: {response.status}")
                        return None

                    data = await response.json()

                    # Jupiter response format: {"data": {"MINT_ADDRESS": {"price": 1.23}}}
                    if "data" in data and token_mint in data["data"]:
                        price_data = data["data"][token_mint]
                        return float(price_data.get("price", 0))

                    return None

        except Exception as e:
            logger.warning(f"Error fetching Jupiter price for {token_mint[:8]}...: {e}")
            return None

    async def get_multiple_token_prices(self, token_mints: List[str]) -> Dict[str, float]:
        """
        Get prices for multiple tokens in a single request.

        Args:
            token_mints: List of token mint addresses (max 100)

        Returns:
            Dict mapping mint address to USD price
        """
        if not token_mints:
            return {}

        try:
            # Jupiter allows up to 100 tokens per request
            mints_batch = token_mints[:100]
            ids_param = ",".join(mints_batch)
            url = f"{self.base_url}?ids={ids_param}"

            timeout = aiohttp.ClientTimeout(total=15)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        logger.warning(f"Jupiter API error: {response.status}")
                        return {}

                    data = await response.json()

                    # Parse response
                    prices = {}
                    if "data" in data:
                        for mint, price_data in data["data"].items():
                            if price_data and "price" in price_data:
                                prices[mint] = float(price_data["price"])

                    logger.info(f"Fetched {len(prices)} prices from Jupiter API")
                    return prices

        except Exception as e:
            logger.error(f"Error fetching Jupiter prices: {e}")
            return {}

    async def get_sol_price(self) -> float:
        """
        Get current SOL price from Jupiter.

        Returns:
            SOL price in USD
        """
        # Wrapped SOL mint address
        wsol_mint = "So11111111111111111111111111111111111111112"
        price = await self.get_token_price(wsol_mint)
        return price if price else 0.0


# Singleton instance
jupiter_price_service = JupiterPriceService()
