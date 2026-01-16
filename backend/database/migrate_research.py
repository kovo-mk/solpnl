"""Migration script to add research/fraud detection tables."""
from sqlalchemy import create_engine
from loguru import logger

from config import settings
from database.models import Base


def run_migration():
    """Create new research tables in the database."""
    logger.info("Running research tables migration...")

    engine = create_engine(settings.database_url)

    # Create only the new tables (won't affect existing tables)
    Base.metadata.create_all(bind=engine, checkfirst=True)

    logger.info("Migration complete! New tables created:")
    logger.info("  - token_analysis_requests")
    logger.info("  - token_analysis_reports")
    logger.info("  - wallet_reputations")
    logger.info("  - rate_limits")


if __name__ == "__main__":
    run_migration()
