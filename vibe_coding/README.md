# Vibe Coding Data Collection

独立的 AI 编程 / Vibe Coding 内容爬取模块，用于从社交媒体平台收集 AI 辅助编程、零代码工具、独立开发等相关内容，作为创新灵感来源。

---

## 📋 目录

- [功能特性](#功能特性)
- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [关键词策略](#关键词策略)
- [数据库表结构](#数据库表结构)
- [OpenClaw 集成](#openclaw-集成)
- [工作流程](#工作流程)

---

## 🎯 功能特性

### 核心功能
- **关键词分层评分**：Tier A/B/C 三级关键词权重系统，精准过滤相关内容
- **黑名单过滤**：自动排除无关内容（如"鼠标cursor"、"bolt螺栓"等）
- **多层去重**：
  - 内容 ID 去重（跨会话持久化）
  - 标题指纹去重（捕获跨平台转发）
- **互动量筛选**：仅保存有意义讨论的内容（点赞+评论 ≥ 5）
- **Top 评论收集**：自动保存每条内容的前 20 条高赞评论
- **趋势分类**：自动归类为 8 大类别（AI 辅助编程、零代码工具、独立开发等）

### 支持平台
- 小红书 (xhs)
- B站 (bili)
- 抖音 (dy) — 可选
- 微博 (wb) — 可选

---

## 🚀 快速开始

### 1. 数据库初始化

在 Supabase SQL Editor 中执行：

```bash
cat vibe_coding/schema.sql | pbcopy  # 复制到剪贴板
# 然后粘贴到 Supabase SQL Editor 执行
```

### 2. 启用模块

编辑 `vibe_coding/config.py`：

```python
ENABLE_VIBE_CODING_COLLECTION = True
```

### 3. 运行爬虫

```bash
# 爬取所有平台
python run_vibe_coding.py

# 爬取指定平台
python run_vibe_coding.py --platform xhs
python run_vibe_coding.py --platform xhs bili

# 查看关键词配置
python run_vibe_coding.py --list-keywords
```

---

## ⚙️ 配置说明

### 关键参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `KEYWORD_SCORE_THRESHOLD` | 4 | 内容必须达到的最低关键词得分 |
| `VIBE_CODING_MIN_ENGAGEMENT` | 5 | 最低互动量（点赞+评论） |
| `VIBE_CODING_TOP_COMMENTS_COUNT` | 20 | 每条内容保存的评论数 |
| `VIBE_CODING_MAX_NOTES_PER_KEYWORD` | 20 | 每个搜索词的最大结果数 |
| `ENABLE_TITLE_FINGERPRINT_DEDUP` | True | 启用标题指纹去重 |

### 平台配置

```python
VIBE_CODING_PLATFORMS = ["xhs", "bili"]  # 默认爬取小红书和B站
```

---

## 🔑 关键词策略

### 三级评分体系

#### Tier A（4 分/个）— 精确工具名
明确的 AI 编程工具品牌名，命中即高度相关：

```python
"cursor ide", "claude code", "v0.dev", "bolt.new",
"lovable.dev", "same.dev", "devin ai", "manus ai",
"github copilot", "windsurf ide", "replit agent", ...
```

#### Tier B（2 分/个）— 行为短语
明确描述使用 AI 编程的行为：

```python
"用ai写代码", "用ai做产品", "ai帮我写", "ai生成代码",
"vibe coding", "不写代码做产品", "10分钟做网站",
"ai编程实战", "提示词写代码", ...
```

#### Tier C（1 分/个）— 通用词
需要与其他关键词组合才有效：

```python
"cursor", "ai编程", "零代码", "独立开发",
"mvp开发", "编程副业", ...
```

### 黑名单（自动拒绝）

```python
"鼠标cursor", "bolt螺栓", "游戏cursor", "css cursor",
"求职", "招聘", "转让", "出售", ...
```

### 评分规则

内容通过条件：
1. **总分 ≥ 4**（至少 1 个 Tier A 或 2 个 Tier B）
2. **无黑名单词汇**
3. **互动量 ≥ 5**（点赞+评论）

---

## 🗄️ 数据库表结构

### `vibe_coding_raw_data` 表

| 字段 | 类型 | 说明 |
|------|------|------|
| `platform` | TEXT | 平台标识 (xhs/bili/dy/wb) |
| `content_id` | TEXT | 内容唯一 ID |
| `title` | TEXT | 标题 |
| `description` | TEXT | 描述/正文 |
| `vibe_coding_keywords` | TEXT[] | 匹配的关键词数组 |
| `trend_category` | TEXT | 趋势分类 |
| `innovation_score` | FLOAT | AI 分析的创新分数（0-1） |
| `extracted_ideas` | JSONB | AI 提取的创意点 |
| `top_comments` | JSONB | 前 N 条高赞评论 |
| `analysis_status` | TEXT | 分析状态（pending/analyzed/design_generated/implemented） |
| `crawl_session_id` | TEXT | 爬取批次 ID |
| `platform_data` | JSONB | 平台原始数据 + `_keyword_score` |

**唯一约束**：`(platform, content_id)`

---

## 🤖 OpenClaw 集成

### 调用方式

```json
{
  "command": "python run_vibe_coding.py",
  "cwd": "/path/to/MediaCrawler",
  "args": ["--platform", "xhs"]
}
```

### 后续 AI 分析流程（规划中）

```python
from vibe_coding.store import VibeCodingStore

# 1. 获取待分析内容
pending = VibeCodingStore.get_pending_analysis(platform="xhs", limit=100)

# 2. AI 分析（OpenClaw + Claude API）
for item in pending:
    score, ideas = analyze_with_claude(item)
    await store.update_analysis_result(
        content_id=item["content_id"],
        innovation_score=score,
        extracted_ideas=ideas,
        trend_category="AI-assisted coding"
    )

# 3. 生成设计方案
top_items = VibeCodingStore.get_top_by_score(min_score=0.7, limit=50)
for item in top_items:
    design_id = generate_design_proposal(item)
    await store.mark_design_generated(item["content_id"], design_id)
```

---

## 📊 工作流程

```
┌─────────────────────────────────────────────────────────────┐
│  1. 爬取阶段 (run_vibe_coding.py)                           │
│     - 使用 SEARCH_KEYWORDS 搜索平台                         │
│     - VibeCodingStore 评分过滤                              │
│     - 保存到 vibe_coding_raw_data (status=pending)          │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  2. AI 分析阶段 (OpenClaw 调用 Claude API)                  │
│     - 读取 status=pending 的内容                            │
│     - 提取创新点、可行性、影响力                             │
│     - 更新 innovation_score + extracted_ideas               │
│     - status → analyzed                                     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  3. 设计生成阶段 (OpenClaw + Claude Code)                   │
│     - 筛选高分内容 (innovation_score ≥ 0.7)                 │
│     - 生成技术设计方案                                       │
│     - status → design_generated                             │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  4. 实现阶段 (Claude Code)                                  │
│     - 根据设计方案编写代码                                   │
│     - status → implemented                                  │
└─────────────────────────────────────────────────────────────┘
```

---

## 📝 趋势分类

| 分类 | 触发关键词示例 |
|------|---------------|
| AI-assisted coding | cursor, copilot, claude code, ai编程 |
| no-code tools | 零代码, v0, bolt, lovable |
| indie hacking | 独立开发, 副业, 一人公司 |
| rapid prototyping | 快速开发, mvp, 10分钟, 一天做 |
| workflow automation | 工作流, 自动化, 工具链 |
| tool comparison | 对比, 横评, vs, 哪个好 |
| learning resources | 教程, 学习, 入门 |
| case studies | 实战, 案例, 项目, 做了 |

---

## 🔍 查询示例

### Python API

```python
from vibe_coding.store import VibeCodingStore

# 获取待分析内容
pending = VibeCodingStore.get_pending_analysis(platform="xhs", limit=100)

# 获取高分内容
top = VibeCodingStore.get_top_by_score(min_score=0.7, limit=50)

# 更新分析结果
store = VibeCodingStore("xhs")
await store.update_analysis_result(
    content_id="123456",
    innovation_score=0.85,
    extracted_ideas={"main": "用 Cursor + v0 快速开发 SaaS"},
    trend_category="rapid prototyping"
)
```

### SQL 查询

```sql
-- 查看最近收集的内容
SELECT platform, title, vibe_coding_keywords, trend_category, liked_count
FROM vibe_coding_raw_data
WHERE analysis_status = 'pending'
ORDER BY publish_time DESC
LIMIT 20;

-- 按趋势分类统计
SELECT trend_category, COUNT(*) as count
FROM vibe_coding_raw_data
GROUP BY trend_category
ORDER BY count DESC;

-- 查看高互动内容
SELECT title, liked_count, comment_count, content_url
FROM vibe_coding_raw_data
WHERE liked_count + comment_count > 100
ORDER BY liked_count DESC
LIMIT 10;
```

---

## 🛠️ 故障排查

### 问题：没有内容被保存

**检查清单**：
1. `ENABLE_VIBE_CODING_COLLECTION = True` 是否已设置
2. 查看日志中的 `[VibeCodingStore] SKIP` 消息，了解过滤原因：
   - `low score` → 关键词匹配不足
   - `blacklisted` → 命中黑名单
   - `low engagement` → 互动量不足
3. 尝试降低 `KEYWORD_SCORE_THRESHOLD` 或 `VIBE_CODING_MIN_ENGAGEMENT`

### 问题：保存了无关内容

**解决方案**：
1. 检查 `platform_data._keyword_score` 字段，查看评分详情
2. 添加更多黑名单词汇到 `KEYWORDS_BLACKLIST`
3. 提高 `KEYWORD_SCORE_THRESHOLD`（建议 4-6）

### 问题：重复内容

**检查**：
- 跨会话去重依赖 `_ensure_preloaded()`，首次调用会从 DB 加载已有 ID
- 标题指纹去重仅在 `ENABLE_TITLE_FINGERPRINT_DEDUP = True` 时生效

---

## 📦 文件结构

```
vibe_coding/
├── __init__.py          # 模块入口
├── config.py            # 配置（关键词、评分规则、平台）
├── store.py             # 数据存储层（评分、去重、持久化）
├── wrapper.py           # Store 包装器（拦截平台 store 调用）
├── crawler.py           # 爬虫编排（临时覆盖全局配置）
├── schema.sql           # Supabase 表结构
└── README.md            # 本文档

run_vibe_coding.py       # 项目根目录启动脚本
```

---

## 🔗 相关文档

- [主项目 README](../README.md)
- [Supabase 配置](../docs/supabase_setup.md)
- [平台爬虫文档](../docs/crawler_guide.md)

---

## 📄 许可证

本模块遵循主项目的 NON-COMMERCIAL LEARNING LICENSE 1.1 许可证。
