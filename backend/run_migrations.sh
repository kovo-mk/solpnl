#!/bin/bash
# Auto-run migrations on Railway deployment

echo "Running database migrations..."

# Run the migration script
python /app/backend/add_logo_column.py

# Exit successfully even if migration already ran
exit 0
