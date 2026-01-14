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
        if settings.database_url.startswith("sqlite"):
            # SQLite migrations
            # Check tokens table columns
            result = conn.execute(text("PRAGMA table_info(tokens)"))
            token_columns = [row[1] for row in result.fetchall()]
            if "is_verified" not in token_columns:
                logger.info("Adding is_verified column to tokens table...")
                conn.execute(text("ALTER TABLE tokens ADD COLUMN is_verified BOOLEAN DEFAULT 0"))
                conn.commit()
                logger.info("is_verified column added successfully")
            if "is_hidden" not in token_columns:
                logger.info("Adding is_hidden column to tokens table...")
                conn.execute(text("ALTER TABLE tokens ADD COLUMN is_hidden BOOLEAN DEFAULT 0"))
                conn.commit()
                logger.info("is_hidden column added successfully")

            # Check tracked_wallets table columns
            result = conn.execute(text("PRAGMA table_info(tracked_wallets)"))
            wallet_columns = [row[1] for row in result.fetchall()]
            if "user_id" not in wallet_columns:
                logger.info("Adding user_id column to tracked_wallets table...")
                conn.execute(text("ALTER TABLE tracked_wallets ADD COLUMN user_id INTEGER"))
                conn.commit()
                logger.info("user_id column added successfully")

            # Check users table columns
            result = conn.execute(text("PRAGMA table_info(users)"))
            user_columns = [row[1] for row in result.fetchall()]
            if "auth_message" not in user_columns:
                logger.info("Adding auth_message column to users table...")
                conn.execute(text("ALTER TABLE users ADD COLUMN auth_message TEXT"))
                conn.commit()
                logger.info("auth_message column added successfully")
        else:
            # PostgreSQL migrations
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

            result = conn.execute(text("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'tracked_wallets' AND column_name = 'user_id'
            """))
            if result.fetchone() is None:
                logger.info("Adding user_id column to tracked_wallets table...")
                conn.execute(text("ALTER TABLE tracked_wallets ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE CASCADE"))
                conn.commit()
                logger.info("user_id column added successfully")

            # Check users table for auth_message column
            result = conn.execute(text("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = 'auth_message'
            """))
            if result.fetchone() is None:
                logger.info("Adding auth_message column to users table...")
                conn.execute(text("ALTER TABLE users ADD COLUMN auth_message TEXT"))
                conn.commit()
                logger.info("auth_message column added successfully")

            # Drop old unique index on address alone (replaced by composite unique constraint)
            result = conn.execute(text("""
                SELECT indexname FROM pg_indexes
                WHERE tablename = 'tracked_wallets' AND indexname = 'ix_tracked_wallets_address'
            """))
            if result.fetchone() is not None:
                logger.info("Dropping old ix_tracked_wallets_address unique index...")
                conn.execute(text("DROP INDEX IF EXISTS ix_tracked_wallets_address"))
                conn.commit()
                logger.info("Old unique index dropped successfully")

            # Add new transaction fields for comprehensive tracking
            # Check if category column exists
            result = conn.execute(text("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'transactions' AND column_name = 'category'
            """))
            if result.fetchone() is None:
                logger.info("Adding new transaction tracking columns...")

                # Add category column
                conn.execute(text("ALTER TABLE transactions ADD COLUMN category VARCHAR(20)"))

                # Expand tx_type from VARCHAR(10) to VARCHAR(20)
                conn.execute(text("ALTER TABLE transactions ALTER COLUMN tx_type TYPE VARCHAR(20)"))

                # Add transfer_destination column
                conn.execute(text("ALTER TABLE transactions ADD COLUMN transfer_destination VARCHAR(255)"))

                # Add helius_type column
                conn.execute(text("ALTER TABLE transactions ADD COLUMN helius_type VARCHAR(50)"))

                conn.commit()
                logger.info("Transaction tracking columns added successfully")


def init_db():
    """Initialize database tables."""
    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")

    # Run migrations for any new columns
    run_migrations()
