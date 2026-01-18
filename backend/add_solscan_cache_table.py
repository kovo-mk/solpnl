"""Add solscan_transfer_cache table for caching Solscan Pro API data."""
import os
import sys
from sqlalchemy import create_engine, text

# Get database URL from environment or Railway
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("ERROR: DATABASE_URL environment variable not set")
    print("Please set it with: export DATABASE_URL='your_railway_postgres_url'")
    sys.exit(1)

print(f"Connecting to database...")
engine = create_engine(DATABASE_URL)

try:
    with engine.connect() as conn:
        # Check if table already exists
        result = conn.execute(text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_name='solscan_transfer_cache';
        """))

        exists = result.fetchone() is not None

        if exists:
            print("Table 'solscan_transfer_cache' already exists. Skipping.")
        else:
            # Create the table
            print("Creating 'solscan_transfer_cache' table...")
            conn.execute(text("""
                CREATE TABLE solscan_transfer_cache (
                    id SERIAL PRIMARY KEY,
                    token_address VARCHAR(255) NOT NULL,
                    transfers_json TEXT NOT NULL,
                    transfer_count INTEGER NOT NULL,
                    earliest_timestamp INTEGER NOT NULL,
                    latest_timestamp INTEGER NOT NULL,
                    days_back INTEGER DEFAULT 30,
                    cached_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                    is_complete BOOLEAN DEFAULT FALSE
                );
            """))

            # Create indexes
            print("Creating indexes...")
            conn.execute(text("""
                CREATE INDEX ix_solscan_cache_token_cached
                ON solscan_transfer_cache(token_address, cached_at);
            """))

            conn.execute(text("""
                CREATE INDEX ix_solscan_cache_expires
                ON solscan_transfer_cache(expires_at);
            """))

            conn.commit()
            print("✓ Table 'solscan_transfer_cache' created successfully!")

except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)

print("\n✓ Migration completed successfully!")
