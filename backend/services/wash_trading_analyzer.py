"""Wash trading and market manipulation detection."""
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from loguru import logger


class WashTradingAnalyzer:
    """Analyzes tokens for wash trading and market manipulation patterns."""

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
