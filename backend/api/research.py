"""Token research and fraud detection API endpoints."""
import asyncio
import json
import aiohttp
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from loguru import logger

from database.models import (
    TokenAnalysisRequest,
    TokenAnalysisReport,
    Token,
)
from services.fraud_analyzer import FraudAnalyzer
from services.helius import HeliusService
from services.wash_trading_analyzer import WashTradingAnalyzer
from services.solscan_api import SolscanProAPI
from config import settings


router = APIRouter(prefix="/research", tags=["research"])


# Request/Response models
class AnalyzeTokenRequest(BaseModel):
    token_address: str = Field(..., description="Solana token mint address")
    telegram_url: Optional[str] = Field(None, description="Telegram channel/group URL (optional)")
    force_refresh: bool = Field(False, description="Force new analysis even if cached")


class AnalysisStatusResponse(BaseModel):
    request_id: int
    status: str  # pending, processing, completed, failed
    created_at: datetime
    report_id: Optional[int] = None


class TokenReportResponse(BaseModel):
    token_address: str
    risk_score: int
    risk_level: str
    verdict: str
    summary: str

    # Token metadata
    token_name: Optional[str] = None
    token_symbol: Optional[str] = None
    token_logo_url: Optional[str] = None
    pair_created_at: Optional[datetime] = None

    # Holder stats
    total_holders: int  # Number of top holders analyzed (usually 20)
    total_holder_count: Optional[int] = None  # Total holder count from Solscan
    top_10_holder_percentage: float
    whale_count: int

    # Contract info
    is_pump_fun: bool
    has_freeze_authority: Optional[bool]
    has_mint_authority: Optional[bool]

    # Wash trading analysis
    wash_trading_score: Optional[int] = None
    wash_trading_likelihood: Optional[str] = None
    unique_traders_24h: Optional[int] = None
    volume_24h_usd: Optional[float] = None
    txns_24h_total: Optional[int] = None
    airdrop_likelihood: Optional[str] = None
    suspicious_wallets: Optional[list] = None

    # Market data
    liquidity_usd: Optional[float] = None
    price_change_24h: Optional[float] = None
    current_price_usd: Optional[float] = None

    # Red flags
    red_flags: list
    suspicious_patterns: list
    pattern_transactions: Optional[dict] = None  # pattern_name -> [transaction_signatures]

    # Transaction breakdown
    transaction_breakdown: Optional[dict] = None

    # Time period breakdowns
    time_periods: Optional[dict] = None

    # Liquidity and whale tracking
    liquidity_pools: Optional[list] = None
    whale_movements: Optional[list] = None

    # Social/GitHub
    twitter_handle: Optional[str] = None
    twitter_followers: Optional[int] = None
    telegram_members: Optional[int] = None
    github_repo_url: Optional[str] = None
    github_commit_count: Optional[int] = None

    created_at: datetime
    updated_at: datetime


# Dependency injection
def get_db():
    """Get database session (you should already have this)."""
    from database import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_fraud_analyzer():
    """Get FraudAnalyzer instance."""
    return FraudAnalyzer()


def get_helius_service():
    """Get HeliusService instance (reuse your existing service)."""
    return HeliusService()


@router.post("/analyze", response_model=AnalysisStatusResponse)
async def analyze_token(
    request: AnalyzeTokenRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Request a fraud analysis for a token.

    Returns immediately with request ID. Analysis runs in background.
    Poll /api/research/status/{request_id} for completion.
    """
    # Check for recent cached report
    if not request.force_refresh:
        cached_report = (
            db.query(TokenAnalysisReport)
            .filter(
                TokenAnalysisReport.token_address == request.token_address,
                TokenAnalysisReport.is_stale == False,
                TokenAnalysisReport.cached_until > datetime.now(timezone.utc),
            )
            .order_by(TokenAnalysisReport.created_at.desc())
            .first()
        )

        if cached_report:
            # Return existing report without creating new request
            existing_request = (
                db.query(TokenAnalysisRequest)
                .filter(TokenAnalysisRequest.report_id == cached_report.id)
                .first()
            )

            if not existing_request:
                # Create request record for cached report
                existing_request = TokenAnalysisRequest(
                    token_address=request.token_address,
                    status="completed",
                    report_id=cached_report.id,
                    completed_at=cached_report.created_at,
                )
                db.add(existing_request)
                db.commit()
                db.refresh(existing_request)

            return AnalysisStatusResponse(
                request_id=existing_request.id,
                status="completed",
                created_at=existing_request.created_at,
                report_id=cached_report.id,
            )

    # Create new analysis request
    analysis_request = TokenAnalysisRequest(
        token_address=request.token_address,
        status="pending",
    )
    db.add(analysis_request)
    db.commit()
    db.refresh(analysis_request)

    # Queue background analysis
    background_tasks.add_task(
        run_token_analysis,
        request_id=analysis_request.id,
        token_address=request.token_address,
        telegram_url=request.telegram_url,
    )

    return AnalysisStatusResponse(
        request_id=analysis_request.id,
        status="pending",
        created_at=analysis_request.created_at,
        report_id=None,
    )


@router.get("/status/{request_id}", response_model=AnalysisStatusResponse)
async def get_analysis_status(request_id: int, db: Session = Depends(get_db)):
    """Check status of an analysis request."""
    analysis_request = db.query(TokenAnalysisRequest).filter(
        TokenAnalysisRequest.id == request_id
    ).first()

    if not analysis_request:
        raise HTTPException(status_code=404, detail="Analysis request not found")

    return AnalysisStatusResponse(
        request_id=analysis_request.id,
        status=analysis_request.status,
        created_at=analysis_request.created_at,
        report_id=analysis_request.report_id,
    )


@router.get("/report/{report_id}", response_model=TokenReportResponse)
async def get_analysis_report(report_id: int, db: Session = Depends(get_db)):
    """Get full analysis report."""
    report = db.query(TokenAnalysisReport).filter(
        TokenAnalysisReport.id == report_id
    ).first()

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    # Parse JSON fields
    red_flags = json.loads(report.red_flags) if report.red_flags else []
    suspicious_patterns = json.loads(report.suspicious_patterns) if report.suspicious_patterns else []
    suspicious_wallets = json.loads(report.suspicious_wallets) if report.suspicious_wallets else []
    transaction_breakdown = json.loads(report.transaction_breakdown) if report.transaction_breakdown else None
    pattern_transactions = json.loads(report.pattern_transactions) if report.pattern_transactions else None
    time_periods = json.loads(report.time_periods) if report.time_periods else None
    liquidity_pools = json.loads(report.liquidity_pools) if report.liquidity_pools else None
    whale_movements = json.loads(report.whale_movements) if report.whale_movements else None

    return TokenReportResponse(
        token_address=report.token_address,
        risk_score=report.risk_score,
        risk_level=report.risk_level,
        verdict=report.claude_verdict or "unknown",
        summary=report.claude_summary or "No summary available",
        # Token metadata
        token_name=report.token_name,
        token_symbol=report.token_symbol,
        token_logo_url=report.token_logo_url,
        pair_created_at=report.pair_created_at,
        # Holder stats
        total_holders=report.total_holders or 0,
        total_holder_count=report.total_holder_count,
        top_10_holder_percentage=report.top_10_holder_percentage or 0.0,
        whale_count=report.whale_count or 0,
        is_pump_fun=report.is_pump_fun,
        has_freeze_authority=report.has_freeze_authority,
        has_mint_authority=report.has_mint_authority,
        # Wash trading
        wash_trading_score=report.wash_trading_score,
        wash_trading_likelihood=report.wash_trading_likelihood,
        unique_traders_24h=report.unique_traders_24h,
        volume_24h_usd=report.volume_24h_usd,
        txns_24h_total=report.txns_24h_total,
        airdrop_likelihood=report.airdrop_likelihood,
        suspicious_wallets=suspicious_wallets,
        liquidity_usd=report.liquidity_usd,
        price_change_24h=report.price_change_24h,
        current_price_usd=report.current_price_usd,
        # Transaction analysis
        transaction_breakdown=transaction_breakdown,
        pattern_transactions=pattern_transactions,
        time_periods=time_periods,
        # Liquidity and whale tracking
        liquidity_pools=liquidity_pools,
        whale_movements=whale_movements,
        # Other
        red_flags=red_flags,
        suspicious_patterns=suspicious_patterns,
        twitter_handle=report.twitter_handle,
        twitter_followers=report.twitter_followers,
        telegram_members=report.telegram_members,
        github_repo_url=report.github_repo_url,
        github_commit_count=report.github_commit_count,
        created_at=report.created_at,
        updated_at=report.updated_at,
    )


@router.get("/token/{token_address}", response_model=Optional[TokenReportResponse])
async def get_latest_report_by_address(token_address: str, db: Session = Depends(get_db)):
    """Get the most recent analysis report for a token address."""
    report = (
        db.query(TokenAnalysisReport)
        .filter(TokenAnalysisReport.token_address == token_address)
        .order_by(TokenAnalysisReport.created_at.desc())
        .first()
    )

    if not report:
        return None

    # Parse JSON fields
    red_flags = json.loads(report.red_flags) if report.red_flags else []
    suspicious_patterns = json.loads(report.suspicious_patterns) if report.suspicious_patterns else []
    suspicious_wallets = json.loads(report.suspicious_wallets) if report.suspicious_wallets else []
    transaction_breakdown = json.loads(report.transaction_breakdown) if report.transaction_breakdown else None
    pattern_transactions = json.loads(report.pattern_transactions) if report.pattern_transactions else None
    time_periods = json.loads(report.time_periods) if report.time_periods else None
    liquidity_pools = json.loads(report.liquidity_pools) if report.liquidity_pools else None
    whale_movements = json.loads(report.whale_movements) if report.whale_movements else None

    return TokenReportResponse(
        token_address=report.token_address,
        risk_score=report.risk_score,
        risk_level=report.risk_level,
        verdict=report.claude_verdict or "unknown",
        summary=report.claude_summary or "No summary available",
        # Token metadata
        token_name=report.token_name,
        token_symbol=report.token_symbol,
        token_logo_url=report.token_logo_url,
        pair_created_at=report.pair_created_at,
        # Holder stats
        total_holders=report.total_holders or 0,
        total_holder_count=report.total_holder_count,
        top_10_holder_percentage=report.top_10_holder_percentage or 0.0,
        whale_count=report.whale_count or 0,
        is_pump_fun=report.is_pump_fun,
        has_freeze_authority=report.has_freeze_authority,
        has_mint_authority=report.has_mint_authority,
        # Wash trading
        wash_trading_score=report.wash_trading_score,
        wash_trading_likelihood=report.wash_trading_likelihood,
        unique_traders_24h=report.unique_traders_24h,
        volume_24h_usd=report.volume_24h_usd,
        txns_24h_total=report.txns_24h_total,
        airdrop_likelihood=report.airdrop_likelihood,
        suspicious_wallets=suspicious_wallets,
        liquidity_usd=report.liquidity_usd,
        price_change_24h=report.price_change_24h,
        current_price_usd=report.current_price_usd,
        # Transaction analysis
        transaction_breakdown=transaction_breakdown,
        pattern_transactions=pattern_transactions,
        time_periods=time_periods,
        # Liquidity and whale tracking
        liquidity_pools=liquidity_pools,
        whale_movements=whale_movements,
        # Other
        red_flags=red_flags,
        suspicious_patterns=suspicious_patterns,
        twitter_handle=report.twitter_handle,
        twitter_followers=report.twitter_followers,
        telegram_members=report.telegram_members,
        github_repo_url=report.github_repo_url,
        github_commit_count=report.github_commit_count,
        created_at=report.created_at,
        updated_at=report.updated_at,
    )


# Background task function
async def run_token_analysis(request_id: int, token_address: str, telegram_url: Optional[str] = None):
    """Background task to run full token analysis."""
    logger.info(f"=== STARTING BACKGROUND ANALYSIS TASK for {token_address} ===")
    from database import SessionLocal

    db = SessionLocal()

    try:
        # Update status to processing
        logger.info(f"Fetching analysis request {request_id} from database...")
        analysis_request = db.query(TokenAnalysisRequest).filter(
            TokenAnalysisRequest.id == request_id
        ).first()

        if not analysis_request:
            logger.error(f"Analysis request {request_id} not found")
            return

        analysis_request.status = "processing"
        db.commit()

        # Initialize services
        helius = HeliusService()
        analyzer = FraudAnalyzer()

        # 1-4. Fetch all independent data in parallel for 5x speed boost
        logger.info(f"Fetching token data in parallel for {token_address}")

        holder_data, mint_info, dex_data, birdeye_data, solscan_data, contract_info = await asyncio.gather(
            helius.get_token_holders(token_address),
            helius.get_token_mint_info(token_address),
            helius.get_dexscreener_data(token_address),
            helius.get_birdeye_token_data(token_address),
            helius.get_solscan_token_meta(token_address),
            helius.get_token_metadata(token_address),
            return_exceptions=True  # Don't fail entire analysis if one API fails
        )

        # Handle any errors from parallel calls
        if isinstance(holder_data, Exception) or not holder_data:
            raise Exception("Failed to fetch holder data")

        # Use defaults for optional data sources if they failed
        if isinstance(mint_info, Exception):
            logger.warning(f"Mint info fetch failed: {mint_info}")
            mint_info = {}
        if isinstance(dex_data, Exception):
            logger.warning(f"DexScreener fetch failed: {dex_data}")
            dex_data = {}
        if isinstance(birdeye_data, Exception):
            logger.warning(f"Birdeye fetch failed: {birdeye_data}")
            birdeye_data = {}
        if isinstance(solscan_data, Exception):
            logger.warning(f"Solscan fetch failed: {solscan_data}")
            solscan_data = {}
        if isinstance(contract_info, Exception):
            logger.warning(f"Contract info fetch failed: {contract_info}")
            contract_info = {}

        # Merge all data into contract_info
        contract_info["has_freeze_authority"] = mint_info.get("freeze_authority") is not None
        contract_info["has_mint_authority"] = mint_info.get("mint_authority") is not None
        contract_info["decimals"] = mint_info.get("decimals", contract_info.get("decimals", 9))
        contract_info["price_usd"] = dex_data.get("price_usd", 0)
        contract_info["volume_24h"] = dex_data.get("volume_24h", 0)
        contract_info["liquidity_usd"] = dex_data.get("liquidity_usd", 0)
        contract_info["market_cap"] = dex_data.get("market_cap", 0)

        # Detect pump.fun tokens by address suffix
        contract_info["is_pump_fun"] = token_address.endswith("pump")

        # Build social data from DexScreener (now includes Twitter handle, Telegram channel, website)
        social_data = {}
        twitter_handle = None

        if dex_data.get("twitter_handle"):
            twitter_handle = dex_data["twitter_handle"]
            social_data["twitter_url"] = f"https://x.com/{twitter_handle}"
            logger.info(f"Found Twitter: @{twitter_handle}")

        telegram_source = None
        if dex_data.get("telegram_url"):
            telegram_source = dex_data["telegram_url"]
            social_data["telegram_url"] = telegram_source
            logger.info(f"Found Telegram: {telegram_source}")

        if dex_data.get("website"):
            social_data["website"] = dex_data["website"]
            logger.info(f"Found website: {social_data['website']}")

        # Use user-provided telegram_url if available, otherwise use scraped
        if telegram_url:
            telegram_source = telegram_url
            social_data["telegram_url"] = telegram_url

        # Fetch Telegram member count
        telegram_members = None
        if telegram_source:
            logger.info(f"Fetching Telegram info for {telegram_source}")
            telegram_info = await helius.get_telegram_info(telegram_source)
            if telegram_info.get("member_count"):
                telegram_members = telegram_info["member_count"]
                social_data["telegram_members"] = telegram_members
                logger.info(f"Telegram has {telegram_members} members")

        # 5. Run fraud analysis
        logger.info(f"Running fraud analysis for {token_address}")
        analysis_result = await analyzer.analyze_token(
            token_address=token_address,
            holder_data=holder_data,
            total_supply=contract_info.get("total_supply", 0),
            contract_info=contract_info,
            social_data=social_data if social_data else None,
            github_data=None,
        )

        # 5.5. Run wash trading analysis
        logger.info(f"Running wash trading analysis for {token_address}")
        wash_analyzer = WashTradingAnalyzer(
            helius_api_key=settings.HELIUS_API_KEY,
            solscan_api_key=settings.SOLSCAN_API_KEY,
            db_session=db  # Pass database session for Solscan caching
        )

        # Run Helius transaction analysis for real wash trading detection
        # Fetch up to 1000 transfers from last 7 days for faster analysis
        helius_analysis = await wash_analyzer.analyze_helius_transactions(
            token_address=token_address,
            limit=1000,  # Analyze up to 1000 transfers (faster, still catches patterns)
            days_back=7  # Last 7 days for faster analysis
        )
        logger.info(f"Helius analysis - Unique traders: {helius_analysis['unique_traders']}, "
                   f"Total txns: {helius_analysis['total_transactions']}, "
                   f"Score: {helius_analysis['wash_trading_score']}")

        # Also run holder-based analysis
        wash_analysis = wash_analyzer.analyze_trading_patterns(
            token_address=token_address,
            holder_data=holder_data,
            transaction_history=None,
            dex_data=birdeye_data if birdeye_data else dex_data,
        )

        # Combine scores - take the higher of the two
        combined_wash_score = max(
            wash_analysis['wash_trading_score'],
            helius_analysis['wash_trading_score']
        )

        # If either analysis shows high risk, mark as high risk
        if helius_analysis['wash_trading_score'] >= 50 or wash_analysis['wash_trading_score'] >= 50:
            wash_trading_likelihood = "high"
        elif helius_analysis['wash_trading_score'] >= 25 or wash_analysis['wash_trading_score'] >= 25:
            wash_trading_likelihood = "medium"
        else:
            wash_trading_likelihood = "low"

        # Merge suspicious patterns
        all_patterns = list(set(
            wash_analysis.get('suspicious_patterns', []) +
            helius_analysis.get('suspicious_patterns', [])
        ))

        logger.info(f"Combined wash trading score: {combined_wash_score}, likelihood: {wash_trading_likelihood}")

        # Merge wash trading patterns into fraud analysis patterns
        analysis_result["suspicious_patterns"].extend(all_patterns)

        # 4. Create or update token record
        token = db.query(Token).filter(Token.address == token_address).first()
        if not token:
            token = Token(
                address=token_address,
                symbol=contract_info.get("symbol"),
                name=contract_info.get("name"),
                decimals=contract_info.get("decimals", 9),
            )
            db.add(token)
            db.commit()

        # 5. Create analysis report
        # twitter_handle already extracted from DexScreener above

        # Use Birdeye data if available, fallback to DexScreener
        market_data = birdeye_data if birdeye_data else dex_data

        # Parse pair_created_at timestamp if available
        pair_created_at = None
        if dex_data.get("pair_created_at"):
            try:
                # DexScreener returns millisecond timestamp
                pair_created_at = datetime.fromtimestamp(dex_data["pair_created_at"] / 1000, tz=timezone.utc)
            except Exception as e:
                logger.warning(f"Failed to parse pair_created_at: {e}")

        report = TokenAnalysisReport(
            token_address=token_address,
            risk_score=analysis_result["risk_score"],
            risk_level=analysis_result["risk_level"],
            holder_concentration=json.dumps(analysis_result["holder_concentration"]),
            suspicious_patterns=json.dumps(analysis_result["suspicious_patterns"]),
            red_flags=json.dumps(analysis_result["red_flags"]),
            total_holders=analysis_result["total_holders"],
            total_holder_count=(
                dex_data.get("holder_count") if dex_data
                else solscan_data.get("holder_count") if solscan_data
                else None
            ),
            top_10_holder_percentage=analysis_result["top_10_holder_percentage"],
            whale_count=analysis_result["whale_count"],
            is_pump_fun=contract_info.get("is_pump_fun", False),
            has_freeze_authority=contract_info.get("has_freeze_authority"),
            has_mint_authority=contract_info.get("has_mint_authority"),
            # Token metadata
            token_name=contract_info.get("name"),
            token_symbol=contract_info.get("symbol"),
            token_logo_url=contract_info.get("logo_url"),
            pair_created_at=pair_created_at,
            # Social info
            twitter_handle=twitter_handle,
            telegram_group=social_data.get("telegram_url") if social_data else None,
            telegram_members=telegram_members,
            # Wash trading metrics (use combined scores)
            wash_trading_score=combined_wash_score,
            wash_trading_likelihood=wash_trading_likelihood,
            # Prefer Birdeye's swap-only count, fallback to our transfer-based count
            unique_traders_24h=market_data.get("unique_wallets_24h") or helius_analysis.get("unique_traders"),
            volume_24h_usd=market_data.get("volume_24h", 0),
            txns_24h_total=helius_analysis.get("total_transactions") or (market_data.get("txns_24h", {}).get("buys", 0) + market_data.get("txns_24h", {}).get("sells", 0)),
            airdrop_likelihood=wash_analysis.get("airdrop_likelihood"),
            suspicious_wallets=json.dumps(helius_analysis.get("suspicious_wallets", [])),
            liquidity_usd=market_data.get("liquidity_usd"),
            price_change_24h=market_data.get("price_change_24h"),
            current_price_usd=market_data.get("price_usd"),
            # Transaction analysis
            transaction_breakdown=json.dumps(helius_analysis.get("transaction_breakdown")) if helius_analysis.get("transaction_breakdown") else None,
            pattern_transactions=json.dumps(wash_analysis.get("pattern_transactions")) if wash_analysis.get("pattern_transactions") else None,
            time_periods=json.dumps(wash_analysis.get("time_periods")) if wash_analysis.get("time_periods") else None,
            # AI analysis
            claude_summary=analysis_result["claude_summary"],
            claude_verdict=analysis_result["claude_verdict"],
            cached_until=datetime.now(timezone.utc) + timedelta(hours=24),  # Cache for 24h
        )
        db.add(report)
        db.commit()
        db.refresh(report)

        # 5.5. Save suspicious wallets for cross-token network detection
        from database.models import SuspiciousWalletToken

        suspicious_wallets = helius_analysis.get("suspicious_wallets", [])
        saved_wallets = set()  # Track saved wallets to avoid duplicates

        for wallet_info in suspicious_wallets[:50]:  # Limit to top 50 wallet pairs
            wallet_address = wallet_info.get("wallet1")
            pattern = wallet_info.get("pattern", "unknown")
            trade_count = wallet_info.get("trade_count", 0)

            # Save wallet1 if not already saved
            if wallet_address and wallet_address not in saved_wallets:
                try:
                    suspicious_wallet_entry = SuspiciousWalletToken(
                        wallet_address=wallet_address,
                        token_address=token_address,
                        report_id=report.id,
                        pattern_type=pattern,
                        trade_count=trade_count
                    )
                    db.add(suspicious_wallet_entry)
                    saved_wallets.add(wallet_address)
                except Exception as e:
                    logger.warning(f"Failed to save suspicious wallet {wallet_address}: {e}")

            # Save wallet2 from pairs if not already saved
            wallet2 = wallet_info.get("wallet2")
            if wallet2 and wallet2 not in saved_wallets:
                try:
                    suspicious_wallet_entry = SuspiciousWalletToken(
                        wallet_address=wallet2,
                        token_address=token_address,
                        report_id=report.id,
                        pattern_type=pattern,
                        trade_count=trade_count
                    )
                    db.add(suspicious_wallet_entry)
                    saved_wallets.add(wallet2)
                except Exception as e:
                    logger.warning(f"Failed to save suspicious wallet {wallet2}: {e}")

        db.commit()
        logger.info(f"Saved {len(saved_wallets)} unique suspicious wallets for {token_address}")

        # 5.6. Fetch liquidity pools and whale movements (if Solscan API key available)
        liquidity_pools_data = None
        whale_movements_data = None

        if settings.SOLSCAN_API_KEY:
            try:
                solscan_client = SolscanProAPI(settings.SOLSCAN_API_KEY, db)

                # Fetch liquidity pools from Solscan
                liquidity_pools = await solscan_client.fetch_token_markets(token_address)
                if liquidity_pools:
                    liquidity_pools_data = json.dumps(liquidity_pools)
                    logger.info(f"Fetched {len(liquidity_pools)} liquidity pools from Solscan")
                else:
                    logger.warning(f"No Solscan liquidity pools found, trying DexScreener fallback...")
                    # Fallback to DexScreener if Solscan has no data
                    logger.info(f"Calling helius.get_dexscreener_pools({token_address[:8]}...)")
                    dex_pools = await helius.get_dexscreener_pools(token_address)
                    logger.info(f"DexScreener returned: {type(dex_pools)} with {len(dex_pools) if dex_pools else 0} pools")
                    if dex_pools:
                        liquidity_pools_data = json.dumps(dex_pools)
                        logger.info(f"✅ SUCCESS: Fetched {len(dex_pools)} liquidity pools from DexScreener")
                    else:
                        logger.error(f"❌ FAILED: No liquidity pools found for {token_address} from any source")

                # Fetch whale movements (transfers above $10k)
                whale_movements = await solscan_client.fetch_whale_movements(token_address, min_amount_usd=10000, limit=50)
                if whale_movements:
                    whale_movements_data = json.dumps(whale_movements)
                    logger.info(f"Fetched {len(whale_movements)} whale movements")
                else:
                    logger.warning(f"No whale movements found for {token_address}")

                # Update report with liquidity and whale data (even if None/empty)
                logger.info(f"📝 BEFORE UPDATE: report.liquidity_pools = {report.liquidity_pools[:100] if report.liquidity_pools else 'None'}")
                report.liquidity_pools = liquidity_pools_data
                report.whale_movements = whale_movements_data
                logger.info(f"📝 AFTER UPDATE: report.liquidity_pools = {report.liquidity_pools[:100] if report.liquidity_pools else 'None'}")
                db.commit()
                db.refresh(report)
                logger.info(f"💾 AFTER COMMIT: report.liquidity_pools = {report.liquidity_pools[:100] if report.liquidity_pools else 'None'}")

            except Exception as e:
                logger.warning(f"Failed to fetch liquidity/whale data from Solscan: {e}")

        # 6. Update request status
        analysis_request.status = "completed"
        analysis_request.report_id = report.id
        analysis_request.completed_at = datetime.now(timezone.utc)
        db.commit()

        logger.info(f"Analysis completed for {token_address} - Risk: {analysis_result['risk_level']}")

    except Exception as e:
        logger.error(f"Analysis failed for {token_address}: {e}")

        # Mark as failed
        if analysis_request:
            analysis_request.status = "failed"
            analysis_request.error_message = str(e)
            db.commit()

    finally:
        db.close()


@router.get("/related-tokens/{token_address}")
async def get_related_manipulated_tokens(token_address: str, db: Session = Depends(get_db)):
    """
    Find other tokens that share suspicious wallets with the given token.
    This helps identify coordinated manipulation networks.
    """
    from database.models import SuspiciousWalletToken
    from sqlalchemy import func, and_

    # Get suspicious wallets for this token
    suspicious_wallets_query = db.query(SuspiciousWalletToken.wallet_address).filter(
        SuspiciousWalletToken.token_address == token_address
    ).distinct()

    suspicious_wallet_addresses = [row[0] for row in suspicious_wallets_query.all()]

    if not suspicious_wallet_addresses:
        return {"related_tokens": [], "message": "No suspicious wallets found for this token"}

    # Find other tokens that share these wallets
    # Group by token_address and count how many wallets overlap
    related_tokens_query = (
        db.query(
            SuspiciousWalletToken.token_address,
            func.count(func.distinct(SuspiciousWalletToken.wallet_address)).label("shared_wallet_count")
        )
        .filter(
            and_(
                SuspiciousWalletToken.wallet_address.in_(suspicious_wallet_addresses),
                SuspiciousWalletToken.token_address != token_address  # Exclude the current token
            )
        )
        .group_by(SuspiciousWalletToken.token_address)
        .having(func.count(func.distinct(SuspiciousWalletToken.wallet_address)) >= 2)  # At least 2 shared wallets
        .order_by(func.count(func.distinct(SuspiciousWalletToken.wallet_address)).desc())
        .limit(10)  # Top 10 related tokens
    )

    related_tokens_data = related_tokens_query.all()

    # Fetch report details for each related token
    related_tokens = []
    for token_addr, shared_count in related_tokens_data:
        # Get the most recent report for this token
        report = db.query(TokenAnalysisReport).filter(
            TokenAnalysisReport.token_address == token_addr
        ).order_by(TokenAnalysisReport.created_at.desc()).first()

        if report:
            related_tokens.append({
                "token_address": token_addr,
                "token_name": report.token_name,
                "token_symbol": report.token_symbol,
                "token_logo_url": report.token_logo_url,
                "risk_score": report.risk_score,
                "risk_level": report.risk_level,
                "wash_trading_score": report.wash_trading_score,
                "shared_wallet_count": shared_count,
                "total_suspicious_wallets": len(suspicious_wallet_addresses),
                "overlap_percentage": round((shared_count / len(suspicious_wallet_addresses)) * 100, 1),
                "report_id": report.id,
                "analyzed_at": report.created_at
            })

    return {
        "token_address": token_address,
        "total_suspicious_wallets": len(suspicious_wallet_addresses),
        "related_tokens": related_tokens,
        "message": f"Found {len(related_tokens)} related tokens sharing suspicious wallets"
    }


@router.get("/shared-wallets/{token_address1}/{token_address2}")
async def get_shared_wallets(token_address1: str, token_address2: str, db: Session = Depends(get_db)):
    """
    Get the list of wallet addresses that are suspicious in both tokens.
    Returns wallet details including pattern type and trade counts.
    """
    from database.models import SuspiciousWalletToken
    from sqlalchemy import and_

    # Get wallets for token 1
    token1_wallets = db.query(SuspiciousWalletToken).filter(
        SuspiciousWalletToken.token_address == token_address1
    ).all()

    # Get wallets for token 2
    token2_wallets = db.query(SuspiciousWalletToken).filter(
        SuspiciousWalletToken.token_address == token_address2
    ).all()

    # Create sets of wallet addresses
    token1_addresses = {w.wallet_address for w in token1_wallets}
    token2_addresses = {w.wallet_address for w in token2_wallets}

    # Find intersection
    shared_addresses = token1_addresses.intersection(token2_addresses)

    # Build detailed response
    shared_wallets = []
    for wallet_addr in shared_addresses:
        # Get details from both tokens
        t1_wallet = next((w for w in token1_wallets if w.wallet_address == wallet_addr), None)
        t2_wallet = next((w for w in token2_wallets if w.wallet_address == wallet_addr), None)

        shared_wallets.append({
            "wallet_address": wallet_addr,
            "pattern_type": t1_wallet.pattern_type if t1_wallet else (t2_wallet.pattern_type if t2_wallet else None),
            "token1_trade_count": t1_wallet.trade_count if t1_wallet else 0,
            "token2_trade_count": t2_wallet.trade_count if t2_wallet else 0,
            "total_trade_count": (t1_wallet.trade_count or 0) + (t2_wallet.trade_count or 0)
        })

    # Sort by total trade count
    shared_wallets.sort(key=lambda x: x["total_trade_count"], reverse=True)

    return {
        "token_address1": token_address1,
        "token_address2": token_address2,
        "shared_wallet_count": len(shared_wallets),
        "shared_wallets": shared_wallets
    }


@router.get("/mint-distribution/{token_address}")
async def get_mint_distribution(token_address: str):
    """
    Analyze token distribution from the mint authority wallet.

    Shows how many tokens have been distributed from the original minting wallet,
    categorized by:
    - Sold via DEX (Raydium, Orca, etc.)
    - Transferred to other wallets
    - Burned

    Returns distribution breakdown with percentages and transaction details.
    """
    try:
        # Get token metadata to find mint authority
        helius = get_helius_service()
        token_info = await helius.get_token_mint_info(token_address)

        if not token_info:
            raise HTTPException(status_code=404, detail="Token not found")

        mint_authority = token_info.get("mint_authority")
        if not mint_authority:
            return {
                "error": "No mint authority found",
                "message": "This token does not have a mint authority (authority may have been revoked)"
            }

        total_supply = int(token_info.get("supply", 0))
        decimals = token_info.get("decimals", 9)

        # Adjust supply for decimals
        adjusted_supply = total_supply / (10 ** decimals)

        # Analyze distribution
        distribution = await helius.analyze_mint_authority_distribution(
            token_address,
            mint_authority,
            adjusted_supply
        )

        return {
            "token_address": token_address,
            "mint_authority": mint_authority,
            "total_supply": adjusted_supply,
            "distribution": distribution
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing mint distribution: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/token-initial-transfers/{token_address}")
async def get_token_initial_transfers(token_address: str, limit: int = 10, db: Session = Depends(get_db)):
    """
    Get the ACTUAL first N token transfers.

    Checks cache first (if Deep Track was used), otherwise fetches from Solscan API.
    Uses sort_by=block_time with sort_order=asc to get oldest transfers first.
    """
    try:
        from database.models import SolscanTransferCache

        # Check cache first
        cache_entry = db.query(SolscanTransferCache).filter(
            SolscanTransferCache.token_address == token_address
        ).first()

        if cache_entry:
            logger.info(f"Using cached transfers for {token_address[:8]} ({cache_entry.transfer_count} total, is_complete={cache_entry.is_complete})")

            # Parse cached transfers
            all_transfers = json.loads(cache_entry.transfers_json)

            # Get first N transfers (already sorted oldest first from Deep Track)
            transfer_data = all_transfers[:min(limit * 2, len(all_transfers))]

            # Convert to our format
            transfers = []
            for transfer in transfer_data:
                from_addr = transfer.get("from_address")
                to_addr = transfer.get("to_address")
                amount = float(transfer.get("amount", 0))
                decimals = transfer.get("decimals", 9)
                adjusted_amount = amount / (10 ** decimals)
                block_time = transfer.get("block_time")
                signature = transfer.get("trans_id")

                # Add both sender (negative) and receiver (positive)
                if from_addr:
                    transfers.append({
                        "signature": signature,
                        "timestamp": block_time,
                        "account": from_addr,
                        "change": -adjusted_amount,
                        "post_balance": None
                    })

                if to_addr:
                    transfers.append({
                        "signature": signature,
                        "timestamp": block_time,
                        "account": to_addr,
                        "change": adjusted_amount,
                        "post_balance": None
                    })

            return {
                "token_address": token_address,
                "transfers": transfers[:limit * 2],
                "from_cache": True,
                "cache_complete": cache_entry.is_complete
            }

        # No cache - fetch from Solscan API
        logger.info(f"No cache found for {token_address[:8]}, fetching from Solscan API")

        solscan_url = "https://pro-api.solscan.io/v2.0/token/transfer"

        params = {
            "address": token_address,
            "page": 1,
            "page_size": min(limit * 2, 50),  # Get more than requested to account for duplicates
            "sort_by": "block_time",
            "sort_order": "asc"  # OLDEST FIRST!
        }

        headers = {"token": settings.SOLSCAN_API_KEY}

        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(solscan_url, params=params, headers=headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Solscan API error: {response.status} - {error_text}")
                    raise HTTPException(status_code=500, detail=f"Solscan API returned {response.status}")

                data = await response.json()

                if not data.get("success"):
                    logger.error(f"Solscan request failed: {data}")
                    raise HTTPException(status_code=500, detail="Solscan request failed")

                transfer_data = data.get("data", [])
                logger.info(f"Fetched {len(transfer_data)} oldest transfers for {token_address[:8]}")

                # Convert to our format
                transfers = []
                for transfer in transfer_data:
                    from_addr = transfer.get("from_address")
                    to_addr = transfer.get("to_address")
                    amount = float(transfer.get("amount", 0))
                    decimals = transfer.get("decimals", 9)
                    adjusted_amount = amount / (10 ** decimals)
                    block_time = transfer.get("block_time")
                    signature = transfer.get("trans_id")

                    # Add both sender (negative) and receiver (positive)
                    if from_addr:
                        transfers.append({
                            "signature": signature,
                            "timestamp": block_time,
                            "account": from_addr,
                            "change": -adjusted_amount,
                            "post_balance": None
                        })

                    if to_addr:
                        transfers.append({
                            "signature": signature,
                            "timestamp": block_time,
                            "account": to_addr,
                            "change": adjusted_amount,
                            "post_balance": None
                        })

                return {
                    "token_address": token_address,
                    "transfers": transfers[:limit * 2],
                    "from_cache": False,
                    "cache_complete": False
                }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching initial transfers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/creator-distribution/{token_address}")
async def get_creator_distribution(token_address: str):
    """
    Analyze token distribution from the creator/deployer wallet.

    Shows how many tokens the original token creator has sold/transferred,
    categorized by:
    - Sold via DEX (Raydium, Orca, etc.)
    - Transferred to other wallets (team allocation, airdrops, etc.)
    - Burned

    Returns distribution breakdown with percentages and transaction details.
    """
    try:
        # Get token metadata to find creator
        helius = get_helius_service()

        # Get the creator address from token metadata using Helius DAS API
        creator_address = await helius.get_token_creator(token_address)

        if not creator_address:
            return {
                "error": "Creator address not found",
                "message": "Unable to identify the token creator for this token. The token may not have metadata or the creator information is not available."
            }

        # Get token info for supply
        token_info = await helius.get_token_mint_info(token_address)
        if not token_info:
            raise HTTPException(status_code=404, detail="Token not found")

        total_supply = int(token_info.get("supply", 0))
        decimals = token_info.get("decimals", 9)

        # Adjust supply for decimals
        adjusted_supply = total_supply / (10 ** decimals)

        # Analyze distribution from creator wallet
        distribution = await helius.analyze_creator_distribution(
            token_address,
            creator_address,
            adjusted_supply
        )

        return {
            "token_address": token_address,
            "creator_address": creator_address,
            "total_supply": adjusted_supply,
            "distribution": distribution
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing creator distribution: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/deep-track/{token_address}")
async def deep_track_token(token_address: str, db: Session = Depends(get_db)):
    """
    Backfill ALL historical transfers for a token using Solscan Pro API.

    This is an expensive operation that:
    1. Fetches all transfers from token creation to present
    2. Stores them in solscan_transfer_cache for future use
    3. Improves accuracy of initial transfer analysis

    WARNING: May consume significant API credits on busy tokens.
    """
    try:
        from database.models import SolscanTransferCache

        # Check if already fully backfilled
        existing = db.query(SolscanTransferCache).filter(
            SolscanTransferCache.token_address == token_address,
            SolscanTransferCache.is_complete == True
        ).first()

        if existing:
            logger.info(f"Token {token_address[:8]} already has complete backfill ({existing.transfer_count} transfers)")
            return {
                "success": True,
                "message": "Token already fully tracked",
                "transfers_count": existing.transfer_count,
                "earliest_timestamp": existing.earliest_timestamp,
                "latest_timestamp": existing.latest_timestamp,
                "cached_at": existing.cached_at.isoformat()
            }

        # Fetch all transfers using direct Solscan API calls
        all_transfers = []
        page = 1
        page_size = 100  # Max per Solscan API

        logger.info(f"Starting deep track for {token_address[:8]}...")

        headers = {
            "token": settings.SOLSCAN_API_KEY,
            "accept": "application/json"
        }

        timeout = aiohttp.ClientTimeout(total=30)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            while True:
                url = f"https://pro-api.solscan.io/v2.0/token/transfer"
                params = {
                    "address": token_address,
                    "page": page,
                    "page_size": page_size,
                    "sort_by": "block_time",
                    "sort_order": "asc",  # Oldest first for backfill
                    "exclude_amount_zero": "true"
                }

                logger.info(f"Fetching page {page}...")

                async with session.get(url, headers=headers, params=params) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Solscan API error: {response.status} - {error_text}")
                        break

                    data = await response.json()

                    if not data.get("success"):
                        logger.error(f"Solscan request failed: {data}")
                        break

                    transfers = data.get("data", [])

                    if not transfers:
                        logger.info(f"No more transfers found at page {page}")
                        break

                    all_transfers.extend(transfers)
                    logger.info(f"Fetched page {page}: {len(transfers)} transfers (total: {len(all_transfers)})")

                    # Stop if we got fewer results than requested (last page)
                    if len(transfers) < page_size:
                        logger.info(f"Last page reached (got {len(transfers)} < {page_size})")
                        break

                    page += 1

                    # Safety limit to prevent runaway costs
                    if page > 2000:  # 200K transfers max
                        logger.warning(f"Hit safety limit at 2000 pages (200K transfers)")
                        break

                    # Rate limiting
                    await asyncio.sleep(0.1)

        if not all_transfers:
            raise HTTPException(status_code=404, detail="No transfers found for this token")

        # Calculate metadata
        timestamps = [t.get("block_time", 0) for t in all_transfers if t.get("block_time")]
        earliest_ts = min(timestamps) if timestamps else 0
        latest_ts = max(timestamps) if timestamps else 0

        # Store in cache
        if existing:
            # Update existing cache
            existing.transfers_json = json.dumps(all_transfers)
            existing.transfer_count = len(all_transfers)
            existing.earliest_timestamp = earliest_ts
            existing.latest_timestamp = latest_ts
            existing.is_complete = True
            existing.cached_at = datetime.now(timezone.utc)
            existing.expires_at = datetime.now(timezone.utc) + timedelta(days=3650)  # 10 years
        else:
            # Create new cache entry
            cache_entry = SolscanTransferCache(
                token_address=token_address,
                transfers_json=json.dumps(all_transfers),
                transfer_count=len(all_transfers),
                earliest_timestamp=earliest_ts,
                latest_timestamp=latest_ts,
                is_complete=True,
                cached_at=datetime.now(timezone.utc),
                expires_at=datetime.now(timezone.utc) + timedelta(days=3650)
            )
            db.add(cache_entry)

        db.commit()

        logger.info(f"✅ Deep track complete for {token_address[:8]}: {len(all_transfers)} transfers backfilled")

        return {
            "success": True,
            "message": "Successfully backfilled all transfers",
            "transfers_count": len(all_transfers),
            "pages_fetched": page,
            "earliest_timestamp": earliest_ts,
            "latest_timestamp": latest_ts,
            "api_cost_estimate": f"{page * 100:,} C.U."
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during deep track: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/wallet-trading-history/{token_address}/{wallet_address}")
async def get_wallet_trading_history(
    token_address: str,
    wallet_address: str,
    calculate_profit: bool = True,
    db: Session = Depends(get_db)
):
    """
    Analyze a specific wallet's complete trading history for a token.

    Shows:
    - All buys and sells
    - Total profit/loss (if calculate_profit=True)
    - Entry and exit prices
    - Whether they're still holding
    - Pattern analysis (early buyer -> dumper?)

    Args:
        token_address: Token mint address
        wallet_address: Wallet address to analyze
        calculate_profit: If True, fetches SOL balance changes from Helius for P&L calculation
    """
    try:
        from database.models import SolscanTransferCache
        from services.helius import HeliusService
        from services.price import price_service

        # Check if we have cached transfers
        cache_entry = db.query(SolscanTransferCache).filter(
            SolscanTransferCache.token_address == token_address
        ).first()

        if not cache_entry:
            raise HTTPException(
                status_code=404,
                detail="No transfer data cached for this token. Run Deep Track first."
            )

        # Parse all transfers
        all_transfers = json.loads(cache_entry.transfers_json)
        logger.info(f"Analyzing wallet {wallet_address[:8]} from {len(all_transfers)} cached transfers")

        # Filter transfers involving this wallet
        wallet_transfers = []
        transaction_signatures = set()  # Track unique transaction signatures

        for transfer in all_transfers:
            from_addr = transfer.get("from_address")
            to_addr = transfer.get("to_address")

            if from_addr == wallet_address or to_addr == wallet_address:
                amount = float(transfer.get("amount", 0))
                decimals = transfer.get("decimals", 6)
                adjusted_amount = amount / (10 ** decimals)
                signature = transfer.get("trans_id")

                # Determine if this is a buy or sell for this wallet
                if to_addr == wallet_address:
                    # Wallet received tokens = BUY
                    wallet_transfers.append({
                        "signature": signature,
                        "timestamp": transfer.get("block_time"),
                        "type": "BUY",
                        "amount": adjusted_amount,
                        "from": from_addr,
                        "to": to_addr
                    })
                    transaction_signatures.add(signature)
                elif from_addr == wallet_address:
                    # Wallet sent tokens = SELL
                    wallet_transfers.append({
                        "signature": signature,
                        "timestamp": transfer.get("block_time"),
                        "type": "SELL",
                        "amount": adjusted_amount,
                        "from": from_addr,
                        "to": to_addr
                    })
                    transaction_signatures.add(signature)

        # Sort by timestamp
        wallet_transfers.sort(key=lambda x: x["timestamp"])

        if not wallet_transfers:
            return {
                "token_address": token_address,
                "wallet_address": wallet_address,
                "transactions": [],
                "total_bought": 0,
                "total_sold": 0,
                "net_position": 0,
                "first_transaction": None,
                "last_transaction": None,
                "pattern": "NO_ACTIVITY"
            }

        # Calculate totals
        total_bought = sum(t["amount"] for t in wallet_transfers if t["type"] == "BUY")
        total_sold = sum(t["amount"] for t in wallet_transfers if t["type"] == "SELL")
        net_position = total_bought - total_sold

        # Determine pattern
        first_tx = wallet_transfers[0]
        last_tx = wallet_transfers[-1]

        pattern = "UNKNOWN"
        if total_bought > 0 and total_sold == 0:
            pattern = "HOLDER"  # Bought but never sold
        elif total_bought > 0 and total_sold > 0 and net_position > 0:
            pattern = "PARTIAL_SELLER"  # Sold some, still holding
        elif total_bought > 0 and total_sold >= total_bought:
            pattern = "FULL_EXIT"  # Sold everything (potential insider dump)
        elif total_bought == 0 and total_sold > 0:
            pattern = "INITIAL_DISTRIBUTOR"  # Only sold, never bought (team wallet?)

        # Check if early buyer (within first hour of token creation)
        earliest_timestamp = cache_entry.earliest_timestamp
        first_tx_timestamp = first_tx["timestamp"]
        is_early_buyer = (first_tx_timestamp - earliest_timestamp) < 3600  # Within 1 hour

        # Base response
        response = {
            "token_address": token_address,
            "wallet_address": wallet_address,
            "transactions": wallet_transfers[:100],  # Limit to first 100 for performance
            "total_transactions": len(wallet_transfers),
            "total_bought": total_bought,
            "total_sold": total_sold,
            "net_position": net_position,
            "first_transaction": first_tx,
            "last_transaction": last_tx,
            "pattern": pattern,
            "is_early_buyer": is_early_buyer,
            "time_to_first_buy_seconds": first_tx_timestamp - earliest_timestamp if first_tx["type"] == "BUY" else None,
            "buy_count": len([t for t in wallet_transfers if t["type"] == "BUY"]),
            "sell_count": len([t for t in wallet_transfers if t["type"] == "SELL"]),
        }

        # Calculate profit/loss if requested
        if calculate_profit and len(transaction_signatures) > 0:
            logger.info(f"Calculating profit for {len(transaction_signatures)} transactions")

            # Initialize Helius service
            helius = HeliusService()

            # Fetch full transaction details for SOL balance changes
            # We need to get the actual transactions to see SOL spent/received
            sol_spent = 0.0
            sol_received = 0.0

            # Process transactions in batches to get SOL balance changes
            try:
                # For each transaction signature, we need to fetch the full transaction
                # and calculate the SOL balance change
                signature_list = list(transaction_signatures)[:100]  # Limit to 100 for performance

                logger.info(f"Fetching Helius transactions for {len(signature_list)} signatures")

                # Fetch transactions using Helius RPC
                async with aiohttp.ClientSession() as session:
                    for sig in signature_list:
                        try:
                            # Use Helius RPC to get parsed transaction
                            payload = {
                                "jsonrpc": "2.0",
                                "id": 1,
                                "method": "getTransaction",
                                "params": [
                                    sig,
                                    {
                                        "encoding": "jsonParsed",
                                        "maxSupportedTransactionVersion": 0
                                    }
                                ]
                            }

                            timeout = aiohttp.ClientTimeout(total=10)
                            async with session.post(helius.rpc_url, json=payload, timeout=timeout) as resp:
                                if resp.status == 200:
                                    data = await resp.json()
                                    tx_data = data.get("result")

                                    if tx_data:
                                        # Calculate SOL balance change for this wallet
                                        pre_balances = tx_data.get("meta", {}).get("preBalances", [])
                                        post_balances = tx_data.get("meta", {}).get("postBalances", [])
                                        account_keys = tx_data.get("transaction", {}).get("message", {}).get("accountKeys", [])

                                        # Find wallet's position in account keys
                                        wallet_index = -1
                                        for i, key in enumerate(account_keys):
                                            if isinstance(key, dict):
                                                pubkey = key.get("pubkey")
                                            else:
                                                pubkey = key

                                            if pubkey == wallet_address:
                                                wallet_index = i
                                                break

                                        if wallet_index >= 0 and wallet_index < len(pre_balances) and wallet_index < len(post_balances):
                                            pre_balance = pre_balances[wallet_index] / 1e9  # lamports to SOL
                                            post_balance = post_balances[wallet_index] / 1e9
                                            sol_change = post_balance - pre_balance

                                            # Determine if this was a buy or sell based on our transfer data
                                            tx_type = None
                                            for transfer in wallet_transfers:
                                                if transfer["signature"] == sig:
                                                    tx_type = transfer["type"]
                                                    break

                                            if tx_type == "BUY" and sol_change < 0:
                                                # Wallet spent SOL to buy tokens
                                                sol_spent += abs(sol_change)
                                            elif tx_type == "SELL" and sol_change > 0:
                                                # Wallet received SOL from selling tokens
                                                sol_received += sol_change

                                            logger.debug(f"Transaction {sig[:8]}: {tx_type}, SOL change: {sol_change:.4f}")

                        except Exception as e:
                            logger.warning(f"Error fetching transaction {sig[:8]}: {e}")
                            continue

                        # Small delay to avoid rate limiting
                        await asyncio.sleep(0.05)

                # Get current token price
                current_price = await price_service.get_token_price(token_address)

                # Get SOL price for USD calculations
                sol_price_usd = await price_service.get_sol_price()

                # Calculate profit metrics
                realized_profit_sol = sol_received - sol_spent

                # Calculate unrealized profit (tokens still held)
                unrealized_profit_sol = 0.0
                if net_position > 0 and current_price:
                    # Current value of held tokens in USD
                    current_value_usd = net_position * current_price
                    # Convert to SOL
                    unrealized_profit_sol = current_value_usd / sol_price_usd

                total_profit_sol = realized_profit_sol + unrealized_profit_sol

                # Add profit data to response
                response["profit_analysis"] = {
                    "sol_spent": round(sol_spent, 4),
                    "sol_received": round(sol_received, 4),
                    "realized_profit_sol": round(realized_profit_sol, 4),
                    "realized_profit_usd": round(realized_profit_sol * sol_price_usd, 2),
                    "unrealized_profit_sol": round(unrealized_profit_sol, 4),
                    "unrealized_profit_usd": round(unrealized_profit_sol * sol_price_usd, 2),
                    "total_profit_sol": round(total_profit_sol, 4),
                    "total_profit_usd": round(total_profit_sol * sol_price_usd, 2),
                    "current_token_price_usd": current_price,
                    "sol_price_usd": round(sol_price_usd, 2),
                    "average_buy_price_sol": round(sol_spent / total_bought, 8) if total_bought > 0 else 0,
                    "average_sell_price_sol": round(sol_received / total_sold, 8) if total_sold > 0 else 0,
                    "roi_percent": round((total_profit_sol / sol_spent * 100), 2) if sol_spent > 0 else 0
                }

                logger.info(f"Profit calculation complete: {total_profit_sol:.4f} SOL (${total_profit_sol * sol_price_usd:.2f})")

            except Exception as e:
                logger.error(f"Error calculating profit: {e}", exc_info=True)
                response["profit_analysis"] = {
                    "error": f"Failed to calculate profit: {str(e)}"
                }

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing wallet trading history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/wallet-full-history/{wallet_address}")
async def get_wallet_full_history(
    wallet_address: str,
    limit: int = 100,
    token_filter: Optional[str] = None
):
    """
    Fetch complete transaction history for a wallet from Helius.

    This endpoint:
    - Fetches ALL transactions for the wallet (not limited to cached tokens)
    - Shows transaction count and summary
    - Optionally filters by specific token mint
    - Returns enhanced transaction data from Helius

    Args:
        wallet_address: Solana wallet address
        limit: Max transactions to fetch (default 100, max 1000)
        token_filter: Optional token mint to filter transactions
    """
    try:
        from services.helius import HeliusService

        helius = HeliusService()

        # Fetch wallet transactions from Helius
        logger.info(f"Fetching transaction history for wallet {wallet_address[:8]}...")

        all_transactions = []
        before_signature = None
        fetch_limit = min(limit, 1000)

        # Fetch in batches of 100 (Helius max per request)
        while len(all_transactions) < fetch_limit:
            batch_size = min(100, fetch_limit - len(all_transactions))

            transactions = await helius.get_wallet_transactions(
                wallet_address=wallet_address,
                limit=batch_size,
                before_signature=before_signature
            )

            if not transactions:
                break

            all_transactions.extend(transactions)

            # Get last signature for pagination
            if len(transactions) == batch_size:
                before_signature = transactions[-1].get("signature")
            else:
                break

        logger.info(f"Fetched {len(all_transactions)} transactions for {wallet_address[:8]}")

        # Analyze transaction types
        tx_types = {}
        token_mints_seen = set()

        for tx in all_transactions:
            tx_type = tx.get("type", "UNKNOWN")
            tx_types[tx_type] = tx_types.get(tx_type, 0) + 1

            # Track unique token mints
            token_transfers = tx.get("tokenTransfers", [])
            for transfer in token_transfers:
                mint = transfer.get("mint")
                if mint:
                    token_mints_seen.add(mint)

        # Filter by token if requested
        filtered_transactions = all_transactions
        if token_filter:
            filtered_transactions = []
            for tx in all_transactions:
                token_transfers = tx.get("tokenTransfers", [])
                for transfer in token_transfers:
                    if transfer.get("mint") == token_filter:
                        filtered_transactions.append(tx)
                        break

            logger.info(f"Filtered to {len(filtered_transactions)} transactions for token {token_filter[:8]}")

        # Get first and last transaction timestamps
        first_tx_time = None
        last_tx_time = None

        if all_transactions:
            first_tx_time = all_transactions[0].get("timestamp")
            last_tx_time = all_transactions[-1].get("timestamp")

        return {
            "wallet_address": wallet_address,
            "total_transactions_fetched": len(all_transactions),
            "filtered_transactions": len(filtered_transactions) if token_filter else len(all_transactions),
            "token_filter": token_filter,
            "unique_tokens_traded": len(token_mints_seen),
            "transaction_types": tx_types,
            "first_transaction_time": first_tx_time,
            "last_transaction_time": last_tx_time,
            "transactions": filtered_transactions[:100],  # Return first 100 for display
            "note": f"Showing first {min(100, len(filtered_transactions))} of {len(filtered_transactions)} transactions"
        }

    except Exception as e:
        logger.error(f"Error fetching wallet history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/wallet-complete-history/{wallet_address}")
async def fetch_wallet_complete_history(
    wallet_address: str,
    force_refresh: bool = False,
    continue_fetch: bool = False,
    db: Session = Depends(get_db)
):
    """
    Fetch COMPLETE wallet transaction history using Helius Enhanced Transactions API.

    Fetches ALL transactions (not just token transfers) with pagination support.
    Results are cached permanently (immutable blockchain data).

    Args:
        wallet_address: Solana wallet address
        force_refresh: If true, clear cache and fetch fresh data from beginning
        continue_fetch: If true, continue fetching from where we left off (append older transactions)

    Returns:
        Complete transaction history with summary stats
    """
    try:
        from services.helius import HeliusService
        from database.models import WalletTransactionCache
        from config import settings
        import json

        if not settings.HELIUS_API_KEY:
            raise HTTPException(
                status_code=500,
                detail="Helius API key not configured"
            )

        # Handle force_refresh (clear cache and start fresh)
        if force_refresh:
            logger.info(f"Force refresh - clearing cache for {wallet_address[:8]}")
            db.query(WalletTransactionCache).filter(
                WalletTransactionCache.wallet_address == wallet_address
            ).delete()
            db.commit()

        # Check cache
        cache_entry = db.query(WalletTransactionCache).filter(
            WalletTransactionCache.wallet_address == wallet_address
        ).first()

        # If we have cache and not continuing, return it
        if cache_entry and not continue_fetch:
            logger.info(f"Using cached transactions for {wallet_address[:8]} ({cache_entry.transaction_count} txns)")
            transactions = json.loads(cache_entry.transactions_json)
            return _analyze_transactions(wallet_address, transactions, from_cache=True)

        # Determine starting point
        if continue_fetch and cache_entry:
            # Continue from where we left off
            cached_transactions = json.loads(cache_entry.transactions_json)
            logger.info(f"Continuing fetch from {len(cached_transactions)} cached transactions")
            # Start from the oldest cached transaction
            before_signature = cached_transactions[-1].get("signature") if cached_transactions else None
        else:
            # Start fresh
            cached_transactions = []
            before_signature = None
            logger.info(f"Fetching complete transaction history for {wallet_address[:8]} using Helius...")

        helius = HeliusService()
        new_transactions = []
        page = 0
        MAX_PAGES = 100  # Safety limit (10,000 transactions max per fetch)

        timeout = aiohttp.ClientTimeout(total=30)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            while page < MAX_PAGES:
                url = f"{helius.base_url}/v0/addresses/{wallet_address}/transactions"
                params = {
                    "api-key": helius.api_key,
                    "limit": 100,  # Max 100 per request
                }
                if before_signature:
                    params["before"] = before_signature

                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Helius API error: {response.status} - {error_text[:500]}")
                        break

                    batch = await response.json()

                if not batch or len(batch) == 0:
                    logger.info(f"No more transactions, stopping at page {page}")
                    break

                new_transactions.extend(batch)
                page += 1
                logger.info(f"Fetched page {page}: {len(batch)} transactions (total new: {len(new_transactions)})")

                # Pagination: use last transaction signature as cursor
                if len(batch) < 100:
                    # Less than full page = we got everything
                    logger.info(f"Received partial page ({len(batch)}), fetching complete")
                    break

                before_signature = batch[-1].get("signature")

                # Rate limiting
                await asyncio.sleep(0.3)

        logger.info(f"Fetched {len(new_transactions)} new transactions across {page} pages")

        # Merge with cached transactions (new transactions are OLDER, so they go at the end)
        all_transactions = cached_transactions + new_transactions

        # Save to cache (permanent storage)
        if all_transactions:
            transactions_json = json.dumps(all_transactions)

            # Calculate timestamps
            timestamps = [tx.get("timestamp") for tx in all_transactions if tx.get("timestamp")]
            earliest_ts = min(timestamps) if timestamps else None
            latest_ts = max(timestamps) if timestamps else None

            # Check if we hit the page limit (incomplete fetch)
            is_complete = (page < MAX_PAGES and len(new_transactions) > 0 and len(new_transactions) % 100 != 0) or len(new_transactions) == 0

            if cache_entry:
                # Update existing
                cache_entry.transactions_json = transactions_json
                cache_entry.transaction_count = len(all_transactions)
                cache_entry.cached_at = datetime.utcnow()
                cache_entry.earliest_timestamp = earliest_ts
                cache_entry.latest_timestamp = latest_ts
                cache_entry.is_complete = is_complete
                logger.info(f"Updated cache: {len(all_transactions)} total transactions ({len(new_transactions)} newly added)")
            else:
                # Create new
                new_cache = WalletTransactionCache(
                    wallet_address=wallet_address,
                    transactions_json=transactions_json,
                    transaction_count=len(all_transactions),
                    earliest_timestamp=earliest_ts,
                    latest_timestamp=latest_ts,
                    cached_at=datetime.utcnow(),
                    is_complete=is_complete
                )
                db.add(new_cache)
                logger.info(f"Created cache: {len(all_transactions)} transactions")

            db.commit()

        return _analyze_transactions(wallet_address, all_transactions, from_cache=False, newly_fetched=len(new_transactions))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching complete wallet history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def _analyze_transactions(wallet_address: str, transactions: list, from_cache: bool = False, newly_fetched: int = 0) -> dict:
    """Analyze transaction list and return summary statistics."""
    token_mints_seen = set()
    tx_types = {}
    token_transfer_count = 0

    for tx in transactions:
        if not isinstance(tx, dict):
            continue

        tx_type = tx.get("type", "UNKNOWN")
        tx_types[tx_type] = tx_types.get(tx_type, 0) + 1

        # Track token transfers
        token_transfers = tx.get("tokenTransfers", [])
        token_transfer_count += len(token_transfers)

        for transfer in token_transfers:
            mint = transfer.get("mint")
            if mint:
                token_mints_seen.add(mint)

    first_tx_time = transactions[0].get("timestamp") if transactions and isinstance(transactions[0], dict) else None
    last_tx_time = transactions[-1].get("timestamp") if transactions and isinstance(transactions[-1], dict) else None

    return {
        "wallet_address": wallet_address,
        "total_transactions": len(transactions),
        "newly_fetched": newly_fetched,
        "token_transfers": token_transfer_count,
        "unique_tokens": len(token_mints_seen),
        "transaction_types": tx_types,
        "first_transaction_time": first_tx_time,
        "last_transaction_time": last_tx_time,
        "tokens_seen": list(token_mints_seen)[:50],  # Show first 50 tokens
        "sample_transactions": transactions[:10],  # Show first 10 as sample
        "from_cache": from_cache
    }



@router.post("/wallet-monitor/add/{wallet_address}")
async def add_wallet_to_monitor(wallet_address: str):
    """
    Add a wallet to real-time monitoring.
    
    The monitor will check for new transactions every minute and automatically
    update the cache.
    """
    from services.wallet_monitor import wallet_monitor
    
    wallet_monitor.add_wallet(wallet_address)
    
    return {
        "status": "success",
        "wallet_address": wallet_address,
        "monitored_wallets": list(wallet_monitor.monitored_wallets),
        "message": f"Wallet {wallet_address[:8]}... added to monitor"
    }


@router.post("/wallet-monitor/remove/{wallet_address}")
async def remove_wallet_from_monitor(wallet_address: str):
    """Remove a wallet from monitoring."""
    from services.wallet_monitor import wallet_monitor
    
    wallet_monitor.remove_wallet(wallet_address)
    
    return {
        "status": "success",
        "wallet_address": wallet_address,
        "monitored_wallets": list(wallet_monitor.monitored_wallets),
        "message": f"Wallet {wallet_address[:8]}... removed from monitor"
    }


@router.get("/wallet-monitor/status")
async def get_monitor_status():
    """Get current wallet monitor status."""
    from services.wallet_monitor import wallet_monitor
    
    return {
        "is_running": wallet_monitor.is_running,
        "monitored_wallets": list(wallet_monitor.monitored_wallets),
        "check_interval_seconds": wallet_monitor.check_interval_seconds
    }


@router.post("/wallet-monitor/configure")
async def configure_monitor(interval_seconds: int = 60):
    """Configure wallet monitor settings."""
    from services.wallet_monitor import wallet_monitor
    
    wallet_monitor.configure(interval_seconds=interval_seconds)
    
    return {
        "status": "success",
        "check_interval_seconds": interval_seconds,
        "message": f"Monitor will check every {interval_seconds} seconds"
    }


@router.get("/wallet-transactions-detailed/{wallet_address}")
async def get_wallet_transactions_detailed(wallet_address: str, db: Session = Depends(get_db)):
    """
    Get detailed transaction history organized by token.
    
    Returns transactions grouped by token with buy/sell counts,
    transfer destinations, and amounts.
    """
    try:
        from database.models import WalletTransactionCache
        import json
        from collections import defaultdict
        
        # Get cached transactions
        cache_entry = db.query(WalletTransactionCache).filter(
            WalletTransactionCache.wallet_address == wallet_address
        ).first()
        
        if not cache_entry:
            raise HTTPException(
                status_code=404,
                detail=f"No transaction history found for wallet. Please fetch it first using /wallet-complete-history/{wallet_address}"
            )
        
        transactions = json.loads(cache_entry.transactions_json)
        
        # Organize transactions by token
        token_data = defaultdict(lambda: {
            "buys": [],
            "sells": [],
            "transfers_out": [],
            "transfers_in": []
        })
        
        # Native SOL tracking
        sol_data = {
            "buys": [],
            "sells": [],
            "transfers_out": [],
            "transfers_in": []
        }
        
        for tx in transactions:
            if not isinstance(tx, dict):
                continue
            
            signature = tx.get("signature", "")
            timestamp = tx.get("timestamp")
            tx_type = tx.get("type", "UNKNOWN")
            token_transfers = tx.get("tokenTransfers", [])
            native_transfers = tx.get("nativeTransfers", [])
            
            # Process token transfers
            for transfer in token_transfers:
                mint = transfer.get("mint", "UNKNOWN")
                from_addr = transfer.get("fromUserAccount", "")
                to_addr = transfer.get("toUserAccount", "")
                amount = transfer.get("tokenAmount", 0)
                
                tx_info = {
                    "signature": signature,
                    "timestamp": timestamp,
                    "type": tx_type,
                    "amount": amount,
                    "from": from_addr,
                    "to": to_addr,
                    "mint": mint
                }
                
                # Categorize as buy, sell, or transfer
                if from_addr == wallet_address and to_addr != wallet_address:
                    if tx_type in ["SWAP", "EXCHANGE"]:
                        token_data[mint]["sells"].append(tx_info)
                    else:
                        token_data[mint]["transfers_out"].append(tx_info)
                elif to_addr == wallet_address and from_addr != wallet_address:
                    if tx_type in ["SWAP", "EXCHANGE"]:
                        token_data[mint]["buys"].append(tx_info)
                    else:
                        token_data[mint]["transfers_in"].append(tx_info)
            
            # Process native SOL transfers
            for transfer in native_transfers:
                from_addr = transfer.get("fromUserAccount", "")
                to_addr = transfer.get("toUserAccount", "")
                amount = transfer.get("amount", 0) / 1e9
                
                tx_info = {
                    "signature": signature,
                    "timestamp": timestamp,
                    "type": tx_type,
                    "amount": amount,
                    "from": from_addr,
                    "to": to_addr,
                    "mint": "So11111111111111111111111111111111111111112"
                }
                
                if from_addr == wallet_address and to_addr != wallet_address:
                    if tx_type in ["SWAP", "EXCHANGE"]:
                        sol_data["sells"].append(tx_info)
                    else:
                        sol_data["transfers_out"].append(tx_info)
                elif to_addr == wallet_address and from_addr != wallet_address:
                    if tx_type in ["SWAP", "EXCHANGE"]:
                        sol_data["buys"].append(tx_info)
                    else:
                        sol_data["transfers_in"].append(tx_info)
        
        # Convert to list format with summary stats
        tokens_summary = []

        # Add SOL first if it has activity
        if any(sol_data.values()):
            tokens_summary.append({
                "mint": "So11111111111111111111111111111111111111112",
                "symbol": "SOL",
                "name": "Solana",
                "buy_count": len(sol_data["buys"]),
                "sell_count": len(sol_data["sells"]),
                "transfer_out_count": len(sol_data["transfers_out"]),
                "transfer_in_count": len(sol_data["transfers_in"]),
                "buys": sol_data["buys"][:100],
                "sells": sol_data["sells"][:100],
                "transfers_out": sol_data["transfers_out"][:100],
                "transfers_in": sol_data["transfers_in"][:100]
            })

        # Add other tokens with metadata lookup
        from database.models import Token
        for mint, data in token_data.items():
            # Look up token metadata from database
            token_metadata = db.query(Token).filter(Token.address == mint).first()

            if token_metadata:
                symbol = token_metadata.symbol or (mint[:8] + "...")
                name = token_metadata.name
            else:
                # Fallback to shortened mint address
                symbol = mint[:8] + "..."
                name = None

            tokens_summary.append({
                "mint": mint,
                "symbol": symbol,
                "name": name,
                "buy_count": len(data["buys"]),
                "sell_count": len(data["sells"]),
                "transfer_out_count": len(data["transfers_out"]),
                "transfer_in_count": len(data["transfers_in"]),
                "buys": data["buys"][:100],
                "sells": data["sells"][:100],
                "transfers_out": data["transfers_out"][:100],
                "transfers_in": data["transfers_in"][:100]
            })
        
        # Sort by total activity
        tokens_summary.sort(
            key=lambda x: x["buy_count"] + x["sell_count"] + x["transfer_out_count"] + x["transfer_in_count"],
            reverse=True
        )
        
        return {
            "wallet_address": wallet_address,
            "total_transactions": len(transactions),
            "unique_tokens": len(tokens_summary),
            "cached_at": cache_entry.cached_at.isoformat() if cache_entry.cached_at else None,
            "tokens": tokens_summary
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting detailed transactions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
