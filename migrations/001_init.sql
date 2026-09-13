CREATE TABLE IF NOT EXISTS sources (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    weight NUMERIC(6,2) NOT NULL DEFAULT 1.0,
    last_success_at TIMESTAMPTZ,
    last_error_at TIMESTAMPTZ,
    consecutive_errors INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS articles (
    id BIGSERIAL PRIMARY KEY,
    source_id BIGINT REFERENCES sources(id),
    title TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    summary TEXT,
    published_at TIMESTAMPTZ,
    discovered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    title_hash CHAR(64) NOT NULL,
    category TEXT,
    language TEXT DEFAULT 'tr',
    cluster_id BIGINT,
    status TEXT NOT NULL DEFAULT 'new',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_articles_discovered ON articles(discovered_at DESC);
CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_articles_title_hash ON articles(title_hash);
CREATE INDEX IF NOT EXISTS idx_articles_cluster ON articles(cluster_id);

CREATE TABLE IF NOT EXISTS story_clusters (
    id BIGSERIAL PRIMARY KEY,
    canonical_title TEXT NOT NULL,
    category TEXT,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    article_count INTEGER NOT NULL DEFAULT 0,
    source_count INTEGER NOT NULL DEFAULT 0,
    velocity_score NUMERIC(6,2) NOT NULL DEFAULT 0,
    source_score NUMERIC(6,2) NOT NULL DEFAULT 0,
    freshness_score NUMERIC(6,2) NOT NULL DEFAULT 0,
    urgency_score NUMERIC(6,2) NOT NULL DEFAULT 0,
    trend_score NUMERIC(6,2) NOT NULL DEFAULT 0,
    viral_score NUMERIC(6,2) NOT NULL DEFAULT 0,
    state TEXT NOT NULL DEFAULT 'watching'
);

CREATE INDEX IF NOT EXISTS idx_clusters_trend ON story_clusters(trend_score DESC);
CREATE INDEX IF NOT EXISTS idx_clusters_viral ON story_clusters(viral_score DESC);
CREATE INDEX IF NOT EXISTS idx_clusters_last_seen ON story_clusters(last_seen_at DESC);

CREATE TABLE IF NOT EXISTS trend_snapshots (
    id BIGSERIAL PRIMARY KEY,
    cluster_id BIGINT NOT NULL REFERENCES story_clusters(id) ON DELETE CASCADE,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    article_count INTEGER NOT NULL,
    source_count INTEGER NOT NULL,
    trend_score NUMERIC(6,2) NOT NULL,
    viral_score NUMERIC(6,2) NOT NULL
);

CREATE TABLE IF NOT EXISTS posts (
    id BIGSERIAL PRIMARY KEY,
    cluster_id BIGINT REFERENCES story_clusters(id),
    text TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    scheduled_at TIMESTAMPTZ,
    published_at TIMESTAMPTZ,
    external_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS system_health (
    component TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    detail TEXT,
    checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
