"""Add token_logo_url column to token_analysis_reports table."""
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
        # Check if column already exists
        result = conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name='token_analysis_reports'
            AND column_name='token_logo_url';
        """))

        exists = result.fetchone() is not None

        if exists:
            print("Column 'token_logo_url' already exists. Skipping.")
        else:
            # Add the column
            print("Adding 'token_logo_url' column...")
            conn.execute(text("""
                ALTER TABLE token_analysis_reports
                ADD COLUMN token_logo_url TEXT NULL;
            """))
            conn.commit()
            print("✓ Column 'token_logo_url' added successfully!")

except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)

print("\n✓ Migration completed successfully!")
