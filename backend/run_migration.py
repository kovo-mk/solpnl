#!/usr/bin/env python3
"""Run database migrations."""

import sys
from pathlib import Path
from sqlalchemy import create_engine, text
from config import settings
from loguru import logger

def run_migration(sql_file: str):
    """Run a SQL migration file."""
    logger.info(f"Running migration: {sql_file}")

    # Read SQL file
    sql_path = Path(__file__).parent / "migrations" / sql_file
    if not sql_path.exists():
        logger.error(f"Migration file not found: {sql_path}")
        return False

    sql = sql_path.read_text()
    logger.info(f"SQL content:\n{sql}")

    # Connect to database
    engine = create_engine(settings.database_url)

    try:
        with engine.connect() as conn:
            # Execute migration
            conn.execute(text(sql))
            conn.commit()
            logger.success(f"Migration {sql_file} completed successfully!")
            return True
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1:
        migration_file = sys.argv[1]
    else:
        migration_file = "001_add_total_holder_count.sql"

    success = run_migration(migration_file)
    sys.exit(0 if success else 1)
