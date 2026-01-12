"""SolPnL - Solana Portfolio P/L Tracker."""
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from config import settings
from database import init_db
from api import router

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


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "SolPnL",
        "description": "Solana Portfolio P/L Tracker",
        "docs": "/docs",
        "api": "/api"
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=True
    )
