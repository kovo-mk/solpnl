"""Database connection and session management."""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from loguru import logger

from config import settings
from .models import Base


# Create engine based on database URL
if settings.database_url.startswith("sqlite"):
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False}
    )
else:
    engine = create_engine(settings.database_url)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Dependency for getting database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_migrations():
    """Run database migrations for new columns."""
    with engine.connect() as conn:
        # Check if is_verified column exists in tokens table
        if settings.database_url.startswith("sqlite"):
            result = conn.execute(text("PRAGMA table_info(tokens)"))
            columns = [row[1] for row in result.fetchall()]
            if "is_verified" not in columns:
                logger.info("Adding is_verified column to tokens table...")
                conn.execute(text("ALTER TABLE tokens ADD COLUMN is_verified BOOLEAN DEFAULT 0"))
                conn.commit()
                logger.info("is_verified column added successfully")
            if "is_hidden" not in columns:
                logger.info("Adding is_hidden column to tokens table...")
                conn.execute(text("ALTER TABLE tokens ADD COLUMN is_hidden BOOLEAN DEFAULT 0"))
                conn.commit()
                logger.info("is_hidden column added successfully")
        else:
            # PostgreSQL
            result = conn.execute(text("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'tokens' AND column_name = 'is_verified'
            """))
            if result.fetchone() is None:
                logger.info("Adding is_verified column to tokens table...")
                conn.execute(text("ALTER TABLE tokens ADD COLUMN is_verified BOOLEAN DEFAULT FALSE"))
                conn.commit()
                logger.info("is_verified column added successfully")

            result = conn.execute(text("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'tokens' AND column_name = 'is_hidden'
            """))
            if result.fetchone() is None:
                logger.info("Adding is_hidden column to tokens table...")
                conn.execute(text("ALTER TABLE tokens ADD COLUMN is_hidden BOOLEAN DEFAULT FALSE"))
                conn.commit()
                logger.info("is_hidden column added successfully")


def init_db():
    """Initialize database tables."""
    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")

    # Run migrations for any new columns
    run_migrations()
