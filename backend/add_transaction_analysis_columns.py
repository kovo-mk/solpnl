"""Add transaction analysis columns to token_analysis_reports table."""
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
            AND column_name IN ('current_price_usd', 'transaction_breakdown', 'pattern_transactions', 'time_periods');
        """))

        existing_columns = {row[0] for row in result.fetchall()}

        columns_to_add = []
        if 'current_price_usd' not in existing_columns:
            columns_to_add.append(('current_price_usd', 'FLOAT'))
        if 'transaction_breakdown' not in existing_columns:
            columns_to_add.append(('transaction_breakdown', 'TEXT'))
        if 'pattern_transactions' not in existing_columns:
            columns_to_add.append(('pattern_transactions', 'TEXT'))
        if 'time_periods' not in existing_columns:
            columns_to_add.append(('time_periods', 'TEXT'))

        if not columns_to_add:
            print("All columns already exist. Skipping migration.")
        else:
            print(f"Adding {len(columns_to_add)} new columns to 'token_analysis_reports' table...")

            for column_name, column_type in columns_to_add:
                print(f"  Adding column '{column_name}' ({column_type})...")
                conn.execute(text(f"""
                    ALTER TABLE token_analysis_reports
                    ADD COLUMN IF NOT EXISTS {column_name} {column_type};
                """))

            conn.commit()
            print("✓ All columns added successfully!")

except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)

print("\n✓ Migration completed successfully!")
