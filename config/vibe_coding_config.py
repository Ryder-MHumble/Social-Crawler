# -*- coding: utf-8 -*-
"""
Vibe Coding Data Collection Configuration

This module configures the collection of vibe coding related content from social media
platforms for trend analysis and innovative idea extraction.
"""

# ==================== Vibe Coding Collection ====================

# Enable vibe coding data collection mode
# When enabled, matching content will be saved to vibe_coding_raw_data table
ENABLE_VIBE_CODING_COLLECTION = True

# Vibe coding related keywords for content discovery
# These keywords target AI-assisted coding, no-code tools, and modern dev workflows
VIBE_CODING_KEYWORDS = [
    # AI coding assistants - Claude系列
    "claude code", "claude编程", "claude开发",
    "claude sonnet", "claude api",
    "anthropic", "claude ai",

    # AI coding assistants - 其他
    "cursor", "cursor编程", "cursor ai", "cursor ide",
    "v0", "v0.dev", "vercel v0",
    "bolt.new", "bolt", "stackblitz",
    "github copilot", "copilot",
    "windsurf", "codeium",
    "replit", "replit ai",
    "tabnine", "kite",

    # Vibe coding concepts
    "vibe coding", "vibe编程", "氛围感编程",
    "ai编程", "ai写代码", "ai生成代码",
    "ai辅助开发", "ai pair programming",
    "提示词编程", "prompt编程", "prompt engineering",
    "零代码", "低代码", "no code", "low code",
    "可视化编程", "拖拽编程",

    # Workflow and tools
    "编程副业", "编程兼职", "独立开发", "独立开发者",
    "一人公司", "solopreneur", "indie hacker",
    "快速开发", "mvp开发", "原型开发",
    "ai工具流", "开发工具链", "效率工具",
    "自动化开发", "智能开发",

    # Specific use cases
    "ai做网站", "ai开发app", "ai写代码",
    "10分钟做网站", "一天做app", "一小时开发",
    "不会编程做产品", "零基础开发",
    "ai全栈开发", "ai前端", "ai后端",

    # Hot topics
    "chatgpt编程", "gpt-4编程",
    "ai代码生成", "代码补全",
    "智能代码助手", "编程助手",
]

# Trend categories for classification
VIBE_CODING_TREND_CATEGORIES = [
    "AI-assisted coding",      # AI辅助编程工具
    "no-code tools",           # 零代码/低代码工具
    "workflow automation",     # 工作流自动化
    "indie hacking",           # 独立开发/副业
    "rapid prototyping",       # 快速原型开发
    "tool integration",        # 工具集成方案
    "learning resources",      # 学习资源/教程
    "case studies",            # 实战案例
    "other",                   # 其他
]

# Minimum engagement for vibe coding content (higher threshold for quality)
# Vibe coding content should have meaningful discussion
VIBE_CODING_MIN_ENGAGEMENT = 10  # likes + comments

# Minimum comment length for idea extraction
VIBE_CODING_MIN_COMMENT_LENGTH = 10

# Number of top comments to save per content (for idea mining)
VIBE_CODING_TOP_COMMENTS_COUNT = 20

# Platforms to crawl for vibe coding content
VIBE_CODING_PLATFORMS = ["xhs", "bili"]  # Start with XHS and Bilibili

# Whether to save to both sentiment_contents and vibe_coding_raw_data
# True = dual save (for backward compatibility)
# False = only save to vibe_coding_raw_data
VIBE_CODING_DUAL_SAVE = False

# ==================== AI Analysis Configuration ====================

# Enable automatic AI analysis of collected content
# When enabled, content will be analyzed for innovation score and idea extraction
ENABLE_VIBE_CODING_AI_ANALYSIS = False  # Disabled by default, enable when AI pipeline is ready

# AI analysis model configuration (for future use)
VIBE_CODING_AI_MODEL = "claude-sonnet-4-6"
VIBE_CODING_AI_ANALYSIS_PROMPT = """
Analyze this vibe coding content and extract:
1. Innovation score (0-1): How novel/creative is this idea?
2. Trend category: Which category does this belong to?
3. Key ideas: What are the main innovative concepts?
4. Implementation feasibility: How practical is this to replicate?
5. Potential impact: What problem does this solve?

Content: {title}
Description: {description}
Top comments: {comments}
"""

# ==================== Batch Processing ====================

# Generate unique session ID for each crawl run
# This helps track which content was collected together
import uuid
from datetime import datetime

def generate_crawl_session_id() -> str:
    """Generate a unique session ID for batch tracking."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    short_uuid = str(uuid.uuid4())[:8]
    return f"vibe_{timestamp}_{short_uuid}"

# Current session ID (will be set at runtime)
CURRENT_CRAWL_SESSION_ID = None
