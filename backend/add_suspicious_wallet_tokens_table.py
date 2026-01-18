"""Add suspicious_wallet_tokens table for cross-token wash trading network detection."""
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
            WHERE table_name='suspicious_wallet_tokens';
        """))

        exists = result.fetchone() is not None

        if exists:
            print("Table 'suspicious_wallet_tokens' already exists. Skipping.")
        else:
            # Create the table
            print("Creating 'suspicious_wallet_tokens' table...")
            conn.execute(text("""
                CREATE TABLE suspicious_wallet_tokens (
                    id SERIAL PRIMARY KEY,
                    wallet_address VARCHAR(255) NOT NULL,
                    token_address VARCHAR(255) NOT NULL,
                    report_id INTEGER NOT NULL REFERENCES token_analysis_reports(id) ON DELETE CASCADE,
                    pattern_type VARCHAR(50),
                    trade_count INTEGER,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    CONSTRAINT unique_wallet_token_report UNIQUE (wallet_address, token_address, report_id)
                );
            """))

            # Create indexes
            print("Creating indexes...")
            conn.execute(text("""
                CREATE INDEX ix_suspicious_wallet_address
                ON suspicious_wallet_tokens(wallet_address);
            """))

            conn.execute(text("""
                CREATE INDEX ix_suspicious_token_address
                ON suspicious_wallet_tokens(token_address);
            """))

            conn.commit()
            print("✓ Table 'suspicious_wallet_tokens' created successfully!")

except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)

print("\n✓ Migration completed successfully!")
