"""SolPnL - Solana Portfolio P/L Tracker."""
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from config import settings
from database import init_db
from api import router
from services.scheduler import scheduler

# Create FastAPI app
app = FastAPI(
    title="SolPnL",
    description="Solana Portfolio Profit/Loss Tracker",
    version="0.1.0"
)

# CORS middleware - more permissive for Vercel preview deployments
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins (Vercel generates dynamic preview URLs)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api")


@app.on_event("startup")
async def startup():
    """Initialize on startup."""
    logger.info("Starting SolPnL API...")
    init_db()
    logger.info("Database initialized")

    # Start auto-sync scheduler (disabled by default)
    scheduler.start()
    logger.info("Auto-sync scheduler initialized (use /api/sync/auto/configure to enable)")


@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown."""
    logger.info("Shutting down SolPnL API...")
    scheduler.stop()
    logger.info("Auto-sync scheduler stopped")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "SolPnL",
        "description": "Solana Portfolio P/L Tracker",
        "docs": "/docs",
        "api": "/api"
    }


@app.post("/migrate")
async def run_migration():
    """Run database migration to add total_holder_count column."""
    from sqlalchemy import text
    from database import SessionLocal

    db = SessionLocal()
    try:
        # Add the column if it doesn't exist
        sql = """
        ALTER TABLE token_analysis_reports
        ADD COLUMN IF NOT EXISTS total_holder_count INTEGER;
        """
        db.execute(text(sql))
        db.commit()
        logger.info("Migration completed: added total_holder_count column")
        return {"status": "success", "message": "Migration completed successfully"}
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=True
    )
