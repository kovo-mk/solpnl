"""Token fraud detection and risk analysis using Claude AI."""
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from anthropic import Anthropic
from loguru import logger

from config import settings


class FraudAnalyzer:
    """Analyzes tokens for fraud patterns using Claude AI."""

    def __init__(self, api_key: Optional[str] = None):
        final_key = api_key or settings.anthropic_api_key
        if final_key:
            # Strip any whitespace that might have been added
            final_key = final_key.strip()
            logger.info(f"Initializing FraudAnalyzer with API key length: {len(final_key)}")
            logger.info(f"API key starts with: {final_key[:15]}...")
            logger.info(f"API key ends with: ...{final_key[-10:]}")
        else:
            logger.warning("No API key provided to FraudAnalyzer!")
        self.client = Anthropic(api_key=final_key)

    async def analyze_token(
        self,
        token_address: str,
        holder_data: List[Dict],
        total_supply: float,
        contract_info: Dict,
        social_data: Optional[Dict] = None,
        github_data: Optional[Dict] = None,
    ) -> Dict:
        """
        Comprehensive token fraud analysis.

        Args:
            token_address: Token mint address
            holder_data: List of {address, balance, percentage} dicts
            total_supply: Total token supply
            contract_info: {is_pump_fun, freeze_authority, mint_authority, created_at}
            social_data: Optional {twitter, telegram, website} info
            github_data: Optional repo analysis data

        Returns:
            {
                risk_score: 0-100,
                risk_level: "low"|"medium"|"high"|"critical",
                holder_concentration: {...},
                suspicious_patterns: [...],
                red_flags: [...],
                claude_summary: "...",
                claude_verdict: "safe"|"suspicious"|"likely_scam"|"confirmed_scam"
            }
        """
        # Calculate holder metrics
        holder_metrics = self._calculate_holder_metrics(holder_data, total_supply)

        # Detect suspicious patterns
        patterns = self._detect_patterns(holder_data, contract_info, social_data, github_data)
        logger.info(f"Detected {len(patterns)} suspicious patterns")

        # Get Claude's analysis
        logger.info("About to call _get_claude_analysis...")
        claude_analysis = await self._get_claude_analysis(
            token_address=token_address,
            holder_metrics=holder_metrics,
            contract_info=contract_info,
            patterns=patterns,
            social_data=social_data,
            github_data=github_data,
        )
        logger.info(f"Claude analysis returned: {claude_analysis.get('verdict', 'unknown')}")

        # Calculate risk score
        risk_score = self._calculate_risk_score(
            holder_metrics=holder_metrics,
            patterns=patterns,
            contract_info=contract_info,
            claude_verdict=claude_analysis.get("verdict", "unknown"),
        )

        # Determine risk level
        risk_level = self._risk_level_from_score(risk_score)

        return {
            "risk_score": risk_score,
            "risk_level": risk_level,
            "holder_concentration": holder_metrics,
            "suspicious_patterns": patterns,
            "red_flags": self._generate_red_flags(patterns, holder_metrics, contract_info),
            "claude_summary": claude_analysis.get("summary", ""),
            "claude_verdict": claude_analysis.get("verdict", "unknown"),
            "total_holders": len(holder_data),
            "top_10_holder_percentage": holder_metrics["top_10_percentage"],
            "whale_count": holder_metrics["whale_count"],
        }

    def _calculate_holder_metrics(self, holder_data: List[Dict], total_supply: float) -> Dict:
        """Calculate holder concentration metrics."""
        if not holder_data:
            return {
                "top_1_percentage": 0,
                "top_5_percentage": 0,
                "top_10_percentage": 0,
                "top_20_percentage": 0,
                "whale_count": 0,
                "distribution_score": 0,
            }

        # Sort by balance descending
        sorted_holders = sorted(holder_data, key=lambda x: x.get("balance", 0), reverse=True)

        # Calculate percentages
        top_1_pct = sorted_holders[0]["percentage"] if len(sorted_holders) >= 1 else 0
        top_5_pct = sum(h["percentage"] for h in sorted_holders[:5])
        top_10_pct = sum(h["percentage"] for h in sorted_holders[:10])
        top_20_pct = sum(h["percentage"] for h in sorted_holders[:20])

        # Count whales (>5% holders)
        whale_count = sum(1 for h in sorted_holders if h["percentage"] > 5.0)

        # Distribution score (0-100, higher = better distribution)
        # Perfect distribution would be equal among all holders
        # Heavily concentrated = low score
        if top_10_pct > 80:
            distribution_score = 10
        elif top_10_pct > 60:
            distribution_score = 30
        elif top_10_pct > 40:
            distribution_score = 50
        elif top_10_pct > 25:
            distribution_score = 70
        else:
            distribution_score = 90

        return {
            "top_1_percentage": round(top_1_pct, 2),
            "top_5_percentage": round(top_5_pct, 2),
            "top_10_percentage": round(top_10_pct, 2),
            "top_20_percentage": round(top_20_pct, 2),
            "whale_count": whale_count,
            "distribution_score": distribution_score,
        }

    def _detect_patterns(
        self,
        holder_data: List[Dict],
        contract_info: Dict,
        social_data: Optional[Dict],
        github_data: Optional[Dict],
    ) -> List[str]:
        """Detect suspicious patterns."""
        patterns = []

        # Holder concentration patterns
        sorted_holders = sorted(holder_data, key=lambda x: x.get("balance", 0), reverse=True)
        top_10_pct = sum(h["percentage"] for h in sorted_holders[:10])

        if top_10_pct > 70:
            patterns.append("extreme_holder_concentration")
        if sorted_holders and sorted_holders[0]["percentage"] > 20:
            patterns.append("single_whale_dominance")

        # Look for clusters of similar-sized wallets (Sybil attack indicator)
        if len(sorted_holders) > 20:
            top_20_balances = [h["balance"] for h in sorted_holders[:20]]
            similar_count = sum(
                1 for i in range(len(top_20_balances) - 1)
                if abs(top_20_balances[i] - top_20_balances[i + 1]) / top_20_balances[i] < 0.05
            )
            if similar_count > 5:
                patterns.append("suspicious_wallet_clustering")

        # Contract patterns
        if contract_info.get("is_pump_fun"):
            patterns.append("pump_fun_token")
        if contract_info.get("has_freeze_authority"):
            patterns.append("freeze_authority_enabled")
        if contract_info.get("has_mint_authority"):
            patterns.append("mint_authority_enabled")

        # Social patterns
        if social_data:
            twitter = social_data.get("twitter", {})
            telegram = social_data.get("telegram", {})

            if twitter.get("followers", 0) < 100:
                patterns.append("low_twitter_following")
            if telegram.get("members", 0) < 50:
                patterns.append("small_telegram_group")

            # Bot followers indicator
            posts = twitter.get("posts", 0)
            followers = twitter.get("followers", 0)
            if posts > 100 and followers < posts:
                patterns.append("suspicious_twitter_engagement")

        # GitHub patterns (based on Oxedium investigation)
        if github_data:
            commit_count = github_data.get("commit_count", 0)
            developer_count = github_data.get("developer_count", 0)
            created_at = github_data.get("created_at")
            first_commit_at = github_data.get("first_commit_at")

            if developer_count == 1:
                patterns.append("solo_developer")
            if commit_count < 50:
                patterns.append("low_commit_count")

            # Rushed development timeline
            if created_at and first_commit_at:
                days_to_first_commit = (first_commit_at - created_at).days
                if 0 < days_to_first_commit < 30 and commit_count < 100:
                    patterns.append("rushed_development")

        return patterns

    async def _get_claude_analysis(
        self,
        token_address: str,
        holder_metrics: Dict,
        contract_info: Dict,
        patterns: List[str],
        social_data: Optional[Dict],
        github_data: Optional[Dict],
    ) -> Dict:
        """Get Claude's AI analysis of the token."""
        prompt = f"""You are a cryptocurrency fraud detection expert. Analyze this Solana token for potential scams or red flags.

**Token Address:** {token_address}

**Holder Metrics:**
- Total holders: {len(patterns)}
- Top 1 holder: {holder_metrics['top_1_percentage']}%
- Top 10 holders: {holder_metrics['top_10_percentage']}%
- Whale count (>5%): {holder_metrics['whale_count']}
- Distribution score: {holder_metrics['distribution_score']}/100

**Contract Info:**
- Pump.fun token: {contract_info.get('is_pump_fun', False)}
- Freeze authority: {contract_info.get('has_freeze_authority', 'unknown')}
- Mint authority: {contract_info.get('has_mint_authority', 'unknown')}

**Detected Patterns:**
{chr(10).join(f'- {p}' for p in patterns) if patterns else '- None detected'}

**Social Presence:**
{json.dumps(social_data, indent=2) if social_data else 'No data available'}

**GitHub Activity:**
{json.dumps(github_data, indent=2) if github_data else 'No data available'}

Based on your analysis of similar scam tokens like Oxedium (solo dev, 41% top-10 concentration, rushed timeline), provide:

1. **Summary** (2-3 sentences): Natural language summary of your assessment
2. **Verdict**: Choose one: "safe", "suspicious", "likely_scam", "confirmed_scam"

Respond ONLY with valid JSON in this exact format:
{{
  "summary": "Your 2-3 sentence analysis here",
  "verdict": "safe|suspicious|likely_scam|confirmed_scam"
}}"""

        try:
            logger.info("Calling Claude API for fraud analysis...")
            logger.info(f"Using API key prefix: {str(self.client.api_key)[:15] if self.client.api_key else 'None'}...")
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",  # Use Sonnet (more widely available)
                max_tokens=500,
                temperature=0.3,  # Lower temp for consistent analysis
                messages=[{"role": "user", "content": prompt}],
            )
            logger.info(f"Claude API call successful! Response length: {len(response.content[0].text)}")

            # Parse Claude's response
            content = response.content[0].text.strip()

            # Extract JSON (handle markdown code blocks)
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            analysis = json.loads(content)
            return analysis

        except Exception as e:
            logger.error(f"Claude analysis failed: {e}")
            logger.error(f"Error type: {type(e).__name__}")
            logger.error(f"Error details: {str(e)}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return {
                "summary": f"Analysis unavailable due to AI service error: {type(e).__name__}",
                "verdict": "unknown",
            }

    def _calculate_risk_score(
        self,
        holder_metrics: Dict,
        patterns: List[str],
        contract_info: Dict,
        claude_verdict: str,
    ) -> int:
        """Calculate overall risk score (0-100)."""
        score = 0

        # Holder concentration (0-40 points)
        top_10 = holder_metrics["top_10_percentage"]
        if top_10 > 80:
            score += 40
        elif top_10 > 60:
            score += 30
        elif top_10 > 40:
            score += 20
        elif top_10 > 25:
            score += 10

        # Pattern penalties (up to 30 points)
        pattern_scores = {
            "extreme_holder_concentration": 10,
            "single_whale_dominance": 8,
            "suspicious_wallet_clustering": 12,
            "freeze_authority_enabled": 6,
            "mint_authority_enabled": 8,
            "solo_developer": 4,
            "rushed_development": 6,
            "low_commit_count": 3,
            "low_twitter_following": 2,
            "small_telegram_group": 2,
            "suspicious_twitter_engagement": 5,
        }
        pattern_score = sum(pattern_scores.get(p, 2) for p in patterns)
        score += min(pattern_score, 30)

        # Claude verdict (0-30 points)
        verdict_scores = {
            "safe": 0,
            "suspicious": 15,
            "likely_scam": 25,
            "confirmed_scam": 30,
        }
        score += verdict_scores.get(claude_verdict, 10)

        return min(score, 100)

    def _risk_level_from_score(self, score: int) -> str:
        """Convert numeric score to risk level."""
        if score >= 70:
            return "critical"
        elif score >= 50:
            return "high"
        elif score >= 30:
            return "medium"
        else:
            return "low"

    def _generate_red_flags(
        self, patterns: List[str], holder_metrics: Dict, contract_info: Dict
    ) -> List[Dict]:
        """Generate human-readable red flag objects."""
        flags = []

        # Map patterns to red flags
        flag_descriptions = {
            "extreme_holder_concentration": {
                "severity": "high",
                "title": "Extreme Holder Concentration",
                "description": f"Top 10 holders control {holder_metrics['top_10_percentage']:.1f}% of supply. This creates massive dump risk.",
            },
            "single_whale_dominance": {
                "severity": "high",
                "title": "Single Whale Control",
                "description": f"One wallet holds {holder_metrics['top_1_percentage']:.1f}% of supply. Developer or insider control likely.",
            },
            "suspicious_wallet_clustering": {
                "severity": "critical",
                "title": "Sybil Attack Pattern Detected",
                "description": "Multiple wallets with suspiciously similar balances. Likely controlled by same entity.",
            },
            "freeze_authority_enabled": {
                "severity": "medium",
                "title": "Freeze Authority Active",
                "description": "Developer can freeze token transfers at any time.",
            },
            "mint_authority_enabled": {
                "severity": "high",
                "title": "Mint Authority Active",
                "description": "Developer can create unlimited new tokens, diluting your holdings.",
            },
            "solo_developer": {
                "severity": "medium",
                "title": "Solo Developer Project",
                "description": "Only one developer committed to the GitHub repo. Single point of failure.",
            },
            "rushed_development": {
                "severity": "high",
                "title": "Rushed Development Timeline",
                "description": "Project went from first commit to mainnet in <30 days. Similar to confirmed scam patterns.",
            },
            "pump_fun_token": {
                "severity": "low",
                "title": "Pump.fun Launch",
                "description": "Token launched via Pump.fun. Not inherently bad, but common for memecoins.",
            },
        }

        for pattern in patterns:
            if pattern in flag_descriptions:
                flags.append(flag_descriptions[pattern])

        return flags
