-- B站私信发送记录表
-- 在 Supabase SQL Editor 中执行此脚本

CREATE TABLE IF NOT EXISTS bilibili_dm_records (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    username TEXT NOT NULL,
    message TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('success', 'failed')),
    error_msg TEXT,
    sent_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    campaign TEXT NOT NULL DEFAULT 'openclaw_2026',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- 唯一约束：同一活动中，每个用户只能有一条成功记录
    UNIQUE(user_id, campaign, status)
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_dm_records_user_id ON bilibili_dm_records(user_id);
CREATE INDEX IF NOT EXISTS idx_dm_records_campaign ON bilibili_dm_records(campaign);
CREATE INDEX IF NOT EXISTS idx_dm_records_status ON bilibili_dm_records(status);
CREATE INDEX IF NOT EXISTS idx_dm_records_sent_at ON bilibili_dm_records(sent_at DESC);

-- 添加注释
COMMENT ON TABLE bilibili_dm_records IS 'B站私信发送记录表';
COMMENT ON COLUMN bilibili_dm_records.user_id IS 'B站用户ID';
COMMENT ON COLUMN bilibili_dm_records.username IS '用户名';
COMMENT ON COLUMN bilibili_dm_records.message IS '发送的消息内容';
COMMENT ON COLUMN bilibili_dm_records.status IS '发送状态: success/failed';
COMMENT ON COLUMN bilibili_dm_records.error_msg IS '错误信息（失败时）';
COMMENT ON COLUMN bilibili_dm_records.sent_at IS '发送时间';
COMMENT ON COLUMN bilibili_dm_records.campaign IS '活动标识';

-- 查询统计
-- 成功发送数量
SELECT campaign, COUNT(*) as success_count
FROM bilibili_dm_records
WHERE status = 'success'
GROUP BY campaign;

-- 失败记录
SELECT username, error_msg, sent_at
FROM bilibili_dm_records
WHERE status = 'failed'
ORDER BY sent_at DESC;

-- 今天发送的记录
SELECT username, status, sent_at
FROM bilibili_dm_records
WHERE DATE(sent_at) = CURRENT_DATE
ORDER BY sent_at DESC;
