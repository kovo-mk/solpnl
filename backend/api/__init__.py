"""API package."""
from fastapi import APIRouter
from .routes import router as pnl_router
from .research import router as research_router

# Combine all routers
router = APIRouter()
router.include_router(pnl_router)
router.include_router(research_router)

__all__ = ["router"]
