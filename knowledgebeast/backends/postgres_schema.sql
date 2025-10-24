-- PostgresBackend schema for vector storage
-- Requires: PostgreSQL 15+ with pgvector extension

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Documents table with vector embeddings
CREATE TABLE IF NOT EXISTS {collection_name}_documents (
    id TEXT PRIMARY KEY,
    embedding vector({embedding_dimension}),
    document TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Vector similarity index (HNSW for fast approximate search)
CREATE INDEX IF NOT EXISTS {collection_name}_embedding_idx
    ON {collection_name}_documents
    USING hnsw (embedding vector_cosine_ops);

-- Text search index (for keyword search)
CREATE INDEX IF NOT EXISTS {collection_name}_document_idx
    ON {collection_name}_documents
    USING gin (to_tsvector('english', document));

-- Metadata index (for filtering)
CREATE INDEX IF NOT EXISTS {collection_name}_metadata_idx
    ON {collection_name}_documents
    USING gin (metadata);

-- Updated timestamp trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_{collection_name}_updated_at
    BEFORE UPDATE ON {collection_name}_documents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
