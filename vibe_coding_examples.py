#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vibe Coding Usage Examples

Quick examples for using the vibe coding data collection system.
"""

# ============================================================
# SETUP
# ============================================================

# 1. Create the table in Supabase SQL Editor:
#    Copy and paste: schema/vibe_coding_schema.sql

# 2. Enable in config/vibe_coding_config.py:
#    ENABLE_VIBE_CODING_COLLECTION = True

# ============================================================
# BASIC USAGE
# ============================================================

# Crawl all platforms for vibe coding content
# python run_vibe_coding.py

# Crawl specific platform
# python run_vibe_coding.py --platform xhs
# python run_vibe_coding.py --platform bili

# ============================================================
# QUERY EXAMPLES
# ============================================================

from database.vibe_coding_store import VibeCodingStore

async def example_queries():
    """Example queries for vibe coding data."""

    # Get pending content for analysis
    pending = VibeCodingStore.get_pending_analysis_content(
        platform="xhs",
        limit=100
    )
    print(f"Found {len(pending)} items pending analysis")

    # Get top innovative content
    top_content = VibeCodingStore.get_top_innovative_content(
        limit=50,
        min_score=0.7
    )
    print(f"Found {len(top_content)} high-scoring items")

    # Update analysis results
    store = VibeCodingStore("xhs")
    await store.update_analysis_result(
        content_id="123456",
        innovation_score=0.85,
        extracted_ideas={
            "main_idea": "使用 Cursor + v0 快速开发 SaaS",
            "key_points": ["AI 辅助", "快速迭代", "低成本"],
            "feasibility": "high"
        },
        trend_category="rapid prototyping"
    )

    # Mark design generated
    await store.mark_design_generated(
        content_id="123456",
        design_proposal_id="design_001"
    )

# ============================================================
# CONFIGURATION
# ============================================================

# Key config options in config/vibe_coding_config.py:

# ENABLE_VIBE_CODING_COLLECTION = True
# VIBE_CODING_PLATFORMS = ["xhs", "bili"]
# VIBE_CODING_MIN_ENGAGEMENT = 10
# VIBE_CODING_TOP_COMMENTS_COUNT = 20

# Add custom keywords:
# VIBE_CODING_KEYWORDS = [
#     "cursor", "v0", "bolt.new",
#     "ai编程", "零代码",
#     # ... more keywords
# ]

# ============================================================
# WORKFLOW
# ============================================================

# 1. Data Collection:
#    python run_vibe_coding.py
#    → Saves to vibe_coding_raw_data table
#    → Status: pending

# 2. AI Analysis (future):
#    python run_vibe_coding.py --analyze
#    → Analyzes content with Claude API
#    → Updates innovation_score, extracted_ideas
#    → Status: analyzed

# 3. Design Generation (future):
#    → Generates design proposals for high-scoring content
#    → Status: design_generated

# 4. Implementation (future):
#    → Passes to OpenClaw + Claude Code
#    → Status: implemented

# ============================================================
# DATABASE SCHEMA
# ============================================================

# Table: vibe_coding_raw_data
# Key fields:
# - platform, content_id (unique)
# - title, description
# - vibe_coding_keywords (TEXT[])
# - innovation_score (FLOAT 0-1)
# - trend_category (TEXT)
# - extracted_ideas (JSONB)
# - top_comments (JSONB)
# - analysis_status (pending/analyzed/design_generated/implemented)
# - crawl_session_id (batch tracking)

# ============================================================
# TREND CATEGORIES
# ============================================================

# - AI-assisted coding: AI 辅助编程工具
# - no-code tools: 零代码/低代码工具
# - workflow automation: 工作流自动化
# - indie hacking: 独立开发/副业
# - rapid prototyping: 快速原型开发
# - tool integration: 工具集成方案
# - learning resources: 学习资源/教程
# - case studies: 实战案例
