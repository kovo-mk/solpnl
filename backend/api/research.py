"""Token research and fraud detection API endpoints."""
import json
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

    # Red flags
    red_flags: list
    suspicious_patterns: list

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

        # 1. Fetch holder data from Helius
        logger.info(f"Fetching holder data for {token_address}")
        holder_data = await helius.get_token_holders(token_address)

        if not holder_data:
            raise Exception("Failed to fetch holder data")

        # 2. Get token mint info (authorities)
        mint_info = await helius.get_token_mint_info(token_address)

        # 3. Get DexScreener data (price, liquidity, socials, holder count)
        logger.info(f"Fetching DexScreener data for {token_address}")
        dex_data = await helius.get_dexscreener_data(token_address)

        # 3.5. Get Birdeye data (volume, transactions, liquidity)
        logger.info(f"Fetching Birdeye token data for {token_address}")
        birdeye_data = await helius.get_birdeye_token_data(token_address)

        # 3.6. Get Solscan data (holder count, market data)
        logger.info(f"Fetching Solscan token metadata for {token_address}")
        solscan_data = await helius.get_solscan_token_meta(token_address)

        # 4. Get contract metadata
        contract_info = await helius.get_token_metadata(token_address)

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
            solscan_api_key=settings.SOLSCAN_API_KEY
        )

        # Run Helius transaction analysis for real wash trading detection
        # Fetch up to 1000 transactions from last 30 days for comprehensive analysis
        helius_analysis = await wash_analyzer.analyze_helius_transactions(
            token_address=token_address,
            limit=1000,  # Analyze up to 1000 transactions (all types)
            days_back=30  # Last 30 days for better pattern detection
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
            unique_traders_24h=helius_analysis.get("unique_traders") or market_data.get("unique_wallets_24h"),
            volume_24h_usd=market_data.get("volume_24h", 0),
            txns_24h_total=helius_analysis.get("total_transactions") or (market_data.get("txns_24h", {}).get("buys", 0) + market_data.get("txns_24h", {}).get("sells", 0)),
            airdrop_likelihood=wash_analysis.get("airdrop_likelihood"),
            suspicious_wallets=json.dumps(helius_analysis.get("suspicious_wallets", [])),
            liquidity_usd=market_data.get("liquidity_usd"),
            price_change_24h=market_data.get("price_change_24h"),
            # AI analysis
            claude_summary=analysis_result["claude_summary"],
            claude_verdict=analysis_result["claude_verdict"],
            cached_until=datetime.now(timezone.utc) + timedelta(hours=24),  # Cache for 24h
        )
        db.add(report)
        db.commit()
        db.refresh(report)

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
