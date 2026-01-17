-- Migration: Add total_holder_count column to token_analysis_reports
-- Date: 2026-01-17

ALTER TABLE token_analysis_reports
ADD COLUMN IF NOT EXISTS total_holder_count INTEGER;

COMMENT ON COLUMN token_analysis_reports.total_holder_count IS 'Total holder count from Solscan API';
