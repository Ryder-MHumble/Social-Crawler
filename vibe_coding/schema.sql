-- Vibe Coding Raw Data Table
-- Stores raw social media content related to vibe coding for trend analysis and idea extraction
-- This table is designed to feed into an AI pipeline that:
-- 1. Analyzes trends and patterns in vibe coding discussions
-- 2. Identifies innovative ideas worth replicating
-- 3. Generates design proposals for OpenClaw/Claude Code implementation

CREATE TABLE IF NOT EXISTS vibe_coding_raw_data (
    -- Primary key
    id BIGINT PRIMARY KEY,

    -- Platform and content identification
    platform TEXT NOT NULL,  -- xhs, bili, dy, wb, etc.
    content_id TEXT NOT NULL,
    content_type TEXT,  -- video, note, article, etc.

    -- Content metadata
    title TEXT,
    description TEXT,
    content_url TEXT,
    cover_url TEXT,

    -- Creator information
    user_id TEXT,
    nickname TEXT,
    avatar TEXT,

    -- Engagement metrics (for trend analysis)
    liked_count INTEGER DEFAULT 0,
    comment_count INTEGER DEFAULT 0,
    share_count INTEGER DEFAULT 0,
    collected_count INTEGER DEFAULT 0,

    -- Location and timing
    ip_location TEXT,
    publish_time BIGINT,

    -- Vibe coding specific fields
    vibe_coding_keywords TEXT[],  -- Array of matched keywords (e.g., ["cursor", "v0", "bolt.new"])
    innovation_score FLOAT,  -- AI-generated score for innovation potential (0-1)
    trend_category TEXT,  -- e.g., "AI-assisted coding", "no-code tools", "workflow automation"
    extracted_ideas JSONB,  -- Structured ideas extracted from content and comments

    -- Analysis status
    analysis_status TEXT DEFAULT 'pending',  -- pending, analyzed, design_generated, implemented
    analyzed_at BIGINT,
    design_proposal_id TEXT,  -- Reference to generated design proposal

    -- Raw platform data
    platform_data JSONB,  -- Platform-specific fields

    -- Comments snapshot (for idea mining)
    top_comments JSONB,  -- Array of top comments with high engagement or innovative ideas

    -- Source tracking
    source_keyword TEXT,  -- Original search keyword or official account marker
    crawl_session_id TEXT,  -- Session identifier for batch tracking

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    last_modify_ts BIGINT NOT NULL,

    -- Unique constraint
    UNIQUE(platform, content_id)
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_vibe_coding_platform ON vibe_coding_raw_data(platform);
CREATE INDEX IF NOT EXISTS idx_vibe_coding_analysis_status ON vibe_coding_raw_data(analysis_status);
CREATE INDEX IF NOT EXISTS idx_vibe_coding_innovation_score ON vibe_coding_raw_data(innovation_score DESC);
CREATE INDEX IF NOT EXISTS idx_vibe_coding_publish_time ON vibe_coding_raw_data(publish_time DESC);
CREATE INDEX IF NOT EXISTS idx_vibe_coding_trend_category ON vibe_coding_raw_data(trend_category);
CREATE INDEX IF NOT EXISTS idx_vibe_coding_crawl_session ON vibe_coding_raw_data(crawl_session_id);

-- GIN index for JSONB fields (for efficient JSON queries)
CREATE INDEX IF NOT EXISTS idx_vibe_coding_extracted_ideas ON vibe_coding_raw_data USING GIN(extracted_ideas);
CREATE INDEX IF NOT EXISTS idx_vibe_coding_keywords ON vibe_coding_raw_data USING GIN(vibe_coding_keywords);

-- Comments
COMMENT ON TABLE vibe_coding_raw_data IS 'Raw social media content for vibe coding trend analysis and idea extraction';
COMMENT ON COLUMN vibe_coding_raw_data.innovation_score IS 'AI-generated score (0-1) indicating innovation potential';
COMMENT ON COLUMN vibe_coding_raw_data.extracted_ideas IS 'Structured ideas extracted by AI from content and comments';
COMMENT ON COLUMN vibe_coding_raw_data.top_comments IS 'Snapshot of high-value comments for idea mining';
COMMENT ON COLUMN vibe_coding_raw_data.analysis_status IS 'Workflow status: pending -> analyzed -> design_generated -> implemented';
