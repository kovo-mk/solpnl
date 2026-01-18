"""Add liquidity_pools, whale_movements columns and new_token_feed table."""
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
        # Check if columns already exist
        result = conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name='token_analysis_reports'
            AND column_name IN ('liquidity_pools', 'whale_movements');
        """))

        existing_columns = {row[0] for row in result.fetchall()}

        columns_to_add = []
        if 'liquidity_pools' not in existing_columns:
            columns_to_add.append(('liquidity_pools', 'TEXT'))
        if 'whale_movements' not in existing_columns:
            columns_to_add.append(('whale_movements', 'TEXT'))

        if columns_to_add:
            print(f"Adding {len(columns_to_add)} new columns to 'token_analysis_reports' table...")

            for column_name, column_type in columns_to_add:
                print(f"  Adding column '{column_name}' ({column_type})...")
                conn.execute(text(f"""
                    ALTER TABLE token_analysis_reports
                    ADD COLUMN IF NOT EXISTS {column_name} {column_type};
                """))

            conn.commit()
            print("✓ All columns added successfully!")
        else:
            print("All columns already exist in 'token_analysis_reports'. Skipping column migration.")

        # Check if new_token_feed table exists
        result = conn.execute(text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_name='new_token_feed';
        """))

        table_exists = result.fetchone() is not None

        if table_exists:
            print("Table 'new_token_feed' already exists. Skipping.")
        else:
            # Create the table
            print("Creating 'new_token_feed' table...")
            conn.execute(text("""
                CREATE TABLE new_token_feed (
                    id SERIAL PRIMARY KEY,
                    token_address VARCHAR(255) NOT NULL UNIQUE,
                    token_name VARCHAR(500),
                    token_symbol VARCHAR(50),
                    token_logo_url TEXT,
                    platform VARCHAR(50),
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
                    initial_liquidity_usd FLOAT,
                    pool_address VARCHAR(255),
                    discovered_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    has_been_analyzed BOOLEAN DEFAULT FALSE
                );
            """))

            # Create indexes
            print("Creating indexes...")
            conn.execute(text("""
                CREATE INDEX ix_new_token_feed_token_address
                ON new_token_feed(token_address);
            """))

            conn.execute(text("""
                CREATE INDEX ix_new_token_feed_created_at
                ON new_token_feed(created_at);
            """))

            conn.execute(text("""
                CREATE INDEX ix_new_token_feed_has_been_analyzed
                ON new_token_feed(has_been_analyzed);
            """))

            conn.execute(text("""
                CREATE INDEX ix_new_token_created
                ON new_token_feed(created_at, has_been_analyzed);
            """))

            conn.execute(text("""
                CREATE INDEX ix_new_token_platform
                ON new_token_feed(platform, created_at);
            """))

            conn.commit()
            print("✓ Table 'new_token_feed' created successfully!")

except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)

print("\n✓ Migration completed successfully!")
