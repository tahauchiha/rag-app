CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE documents (
  id         SERIAL PRIMARY KEY,
  name       TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE chunks (
  id          SERIAL PRIMARY KEY,
  document_id INT REFERENCES documents(id) ON DELETE CASCADE,
  page        INT,
  content     TEXT NOT NULL,
  embedding   vector(384)
);

CREATE INDEX chunks_embedding_idx ON chunks USING hnsw (embedding vector_cosine_ops);