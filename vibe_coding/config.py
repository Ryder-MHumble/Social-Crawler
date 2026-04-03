# -*- coding: utf-8 -*-
"""
Vibe Coding Collection Configuration

Keywords are split into tiers with different match scores.
Content must reach KEYWORD_SCORE_THRESHOLD to be saved.
"""

import uuid
from datetime import datetime

# ===================== Master Switch =====================

ENABLE_VIBE_CODING_COLLECTION = False

# ===================== Platforms =====================

VIBE_CODING_PLATFORMS = ["xhs", "bili"]

# ===================== Keyword Scoring =====================
#
# Score rules:
#   TIER_A (score=4): Exact tool names / unambiguous brand terms
#   TIER_B (score=2): Behaviour phrases clearly about AI coding
#   TIER_C (score=1): General terms that need support from other keywords
#
# Content passes if:
#   sum(matched scores) >= KEYWORD_SCORE_THRESHOLD
#   AND no BLACKLIST term is found
#
KEYWORD_SCORE_THRESHOLD = 4   # must hit ≥1 Tier-A OR ≥2 Tier-B

# --- Tier A: specific tool names (4 pts each) ---
KEYWORDS_TIER_A: list[str] = [
    # Claude family
    "claude code", "claude.ai", "anthropic claude",
    # Cursor
    "cursor ide", "cursor editor", "cursor ai", "cursor composer",
    # Vercel / v0
    "v0.dev", "vercel v0",
    # Bolt / StackBlitz
    "bolt.new", "bolt ai",
    # Lovable
    "lovable.dev", "lovable ai", "lovable app",
    # Same.dev
    "same.dev", "same ai",
    # Replit
    "replit agent", "replit ghostwriter",
    # Devin / Manus
    "devin ai", "cognition devin", "manus ai",
    # Cline / Aider
    "cline ai", "aider ai", "aider coding",
    # Windsurf
    "windsurf ide", "windsurf editor", "windsurf ai",
    # GitHub Copilot
    "github copilot", "copilot workspace",
    # Gemini Code / Tabnine
    "gemini code", "tabnine ai",
    # OpenAI Codex / Operator
    "codex ai", "openai codex",
    # Zed AI
    "zed editor", "zed ai",
    # Continue.dev
    "continue.dev",
    # Supermaven
    "supermaven",
]

# --- Tier B: behaviour phrases about AI coding (2 pts each) ---
KEYWORDS_TIER_B: list[str] = [
    "用ai写代码", "用ai做产品", "用ai开发", "用ai做网站", "用ai做app",
    "ai帮我写", "ai帮我做", "ai生成代码", "ai生成网站",
    "ai编程实战", "ai开发实战", "ai全栈开发", "ai写了个",
    "vibe coding", "vibe编程", "氛围感编程",
    "不写代码做产品", "零基础做app", "零基础做网站",
    "提示词写代码", "prompt写代码",
    "ai做独立产品", "ai副业项目", "ai做saas",
    "10分钟做网站", "一小时做app", "一天做产品",
    "no-code开发", "low-code开发",
    "ai pair programming",
]

# --- Tier C: general terms (1 pt each, need combined score ≥4) ---
KEYWORDS_TIER_C: list[str] = [
    "cursor", "windsurf", "copilot", "codeium",
    "ai编程", "ai写代码", "ai开发工具", "ai coding",
    "零代码", "低代码", "no code", "low code",
    "独立开发", "独立开发者", "indie hacker", "indiehacker",
    "一人公司", "solopreneur",
    "mvp开发", "快速原型",
    "编程副业", "副业项目",
    "智能编程", "代码补全", "ai代码",
]

# --- Blacklist: auto-reject if any found in title+description ---
KEYWORDS_BLACKLIST: list[str] = [
    "鼠标cursor", "cursor鼠标", "cursor手势",
    "bolt螺栓", "bolt螺丝", "bolt扳手",
    "游戏cursor", "css cursor",
    "low code歌", "no code歌",
    "求职", "招聘", "内推",          # job posts
    "转让", "出售", "二手",           # sales
]

# ===================== Engagement Filter =====================

# Min total engagement (likes + comments) before accepting content
VIBE_CODING_MIN_ENGAGEMENT = 5

# ===================== Comment Collection =====================

VIBE_CODING_TOP_COMMENTS_COUNT = 20
VIBE_CODING_MIN_COMMENT_LENGTH = 8  # skip very short/emoji-only comments

# ===================== Dedup =====================

# Also deduplicate by title fingerprint (normalized title hash)
# Catches reposts with different content_id but same text
ENABLE_TITLE_FINGERPRINT_DEDUP = True

# ===================== Trend Categories =====================

VIBE_CODING_TREND_CATEGORIES = [
    "AI-assisted coding",    # AI辅助编程工具
    "no-code tools",         # 零代码/低代码工具
    "workflow automation",   # 工作流自动化
    "indie hacking",         # 独立开发/副业
    "rapid prototyping",     # 快速原型开发
    "tool comparison",       # 工具横评/对比
    "learning resources",    # 学习资源/教程
    "case studies",          # 实战案例
    "other",
]

# Category detection rules: {category: [trigger_keywords]}
CATEGORY_RULES: dict[str, list[str]] = {
    "AI-assisted coding": [
        "cursor", "copilot", "claude code", "windsurf", "codeium",
        "ai编程", "ai写代码", "ai coding", "ai辅助",
    ],
    "no-code tools": [
        "零代码", "低代码", "no code", "low code",
        "v0", "bolt", "lovable", "same.dev",
    ],
    "indie hacking": [
        "独立开发", "副业", "一人公司", "solopreneur", "indie hacker",
    ],
    "rapid prototyping": [
        "快速开发", "mvp", "10分钟", "一天做", "一小时",
        "原型", "prototype",
    ],
    "workflow automation": [
        "工作流", "workflow", "自动化", "工具链",
    ],
    "tool comparison": [
        "对比", "横评", "vs", "哪个好", "哪个强", "推荐",
    ],
    "learning resources": [
        "教程", "学习", "入门", "教学", "课程",
    ],
    "case studies": [
        "实战", "案例", "项目", "做了", "分享",
    ],
}

# ===================== Search Keywords =====================
# These are the keywords actually passed to platform search APIs.
# Keep this list focused and non-redundant (platforms limit query count).

SEARCH_KEYWORDS: list[str] = [
    # High-signal tool searches
    "cursor ai编程",
    "claude code开发",
    "bolt.new做网站",
    "v0.dev教程",
    "lovable ai",
    "windsurf ide",
    "github copilot实战",
    "devin ai",
    "manus ai",
    # Concept searches
    "vibe coding",
    "ai编程实战",
    "用ai做独立产品",
    "零基础ai开发",
    "ai副业项目",
]

# Max search results per keyword (per platform)
VIBE_CODING_MAX_NOTES_PER_KEYWORD = 20

# ===================== AI Analysis (future) =====================

ENABLE_VIBE_CODING_AI_ANALYSIS = False
VIBE_CODING_AI_MODEL = "claude-sonnet-4-6"

# ===================== Session Tracking =====================

CURRENT_CRAWL_SESSION_ID: str | None = None


def generate_crawl_session_id() -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    short_uuid = str(uuid.uuid4())[:8]
    return f"vibe_{timestamp}_{short_uuid}"
