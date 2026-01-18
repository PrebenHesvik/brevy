-- Initialize Brevy database schemas
-- This script runs automatically when the PostgreSQL container starts for the first time

-- Create schemas for service separation
CREATE SCHEMA IF NOT EXISTS api;
CREATE SCHEMA IF NOT EXISTS analytics;

-- Grant permissions (for future use with separate service users)
-- For now, the default postgres user has full access

COMMENT ON SCHEMA api IS 'API service schema - users and links';
COMMENT ON SCHEMA analytics IS 'Analytics service schema - clicks and aggregations';
