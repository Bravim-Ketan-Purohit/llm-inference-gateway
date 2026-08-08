-- Initialize pgvector extension and semantic cache table
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS semantic_cache (
    id BIGSERIAL PRIMARY KEY,
    cache_key VARCHAR(64) UNIQUE NOT NULL,
    embedding vector(384) NOT NULL,
    response TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- HNSW index for fast cosine similarity search
CREATE INDEX IF NOT EXISTS idx_semantic_cache_embedding
    ON semantic_cache
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 200);

-- Index for key lookups
CREATE INDEX IF NOT EXISTS idx_semantic_cache_key
    ON semantic_cache (cache_key);

-- Index for cleanup queries
CREATE INDEX IF NOT EXISTS idx_semantic_cache_updated
    ON semantic_cache (updated_at);
