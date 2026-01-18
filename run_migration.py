#!/usr/bin/env python3
"""
Run database migration by connecting to Railway's deployed database.
This script uses the Railway API to get the DATABASE_URL and run the migration.
"""
import subprocess
import sys
import os

print("=" * 80)
print("DATABASE MIGRATION RUNNER")
print("=" * 80)

# Try to get DATABASE_URL from Railway variables command
print("\n[1/3] Fetching DATABASE_URL from Railway...")

try:
    result = subprocess.run(
        ["railway", "variables"],
        capture_output=True,
        text=True,
        cwd=os.path.dirname(__file__)
    )

    if result.returncode != 0:
        print("❌ Railway CLI not found or not logged in.")
        print("\nPlease run the migration manually:")
        print("1. Install Railway CLI: npm install -g @railway/cli")
        print("2. Login: railway login")
        print("3. Link project: railway link")
        print("4. Run: railway run python backend/add_logo_column.py")
        sys.exit(1)

    # Parse DATABASE_URL from output
    database_url = None
    for line in result.stdout.split('\n'):
        if 'DATABASE_URL' in line and '=' in line:
            database_url = line.split('=', 1)[1].strip()
            break

    if not database_url:
        print("❌ Could not find DATABASE_URL in Railway variables")
        sys.exit(1)

    print(f"✓ Found DATABASE_URL: {database_url[:30]}...")

    # Set environment variable
    os.environ['DATABASE_URL'] = database_url

    # Run the migration script
    print("\n[2/3] Running migration script...")
    migration_script = os.path.join(os.path.dirname(__file__), 'backend', 'add_logo_column.py')

    result = subprocess.run(
        [sys.executable, migration_script],
        env=os.environ,
        cwd=os.path.dirname(__file__)
    )

    if result.returncode == 0:
        print("\n[3/3] ✓ Migration completed successfully!")
        print("\n" + "=" * 80)
        print("SUCCESS! Token logo feature is now fully deployed.")
        print("=" * 80)
    else:
        print("\n❌ Migration failed")
        sys.exit(1)

except Exception as e:
    print(f"❌ Error: {e}")
    print("\nPlease run the migration manually:")
    print("  railway run python backend/add_logo_column.py")
    sys.exit(1)
