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
async def get_token_initial_transfers(token_address: str, limit: int = 10):
    """
    Get the ACTUAL first N token transfers using Solscan API.

    Uses sort_by=block_time with sort_order=asc to get oldest transfers first.
    Much faster than blockchain pagination.
    """
    try:
        # Use Solscan Pro API - it can sort by block_time ascending!
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
                    "transfers": transfers[:limit * 2]
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
