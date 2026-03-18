#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vibe Coding Pipeline - Usage Examples

Quick examples for using the skill from Python or command line.
"""

import asyncio
import json
from pathlib import Path

# ============================================================
# COMMAND LINE USAGE
# ============================================================

# Full pipeline (all phases)
# python .claude/skills/vibe-coding-pipeline/pipeline.py

# Individual phases
# python .claude/skills/vibe-coding-pipeline/pipeline.py --phase crawl --platform xhs
# python .claude/skills/vibe-coding-pipeline/pipeline.py --phase analyze --limit 20
# python .claude/skills/vibe-coding-pipeline/pipeline.py --phase design --min-score 0.8
# python .claude/skills/vibe-coding-pipeline/pipeline.py --phase export

# With filters
# python .claude/skills/vibe-coding-pipeline/pipeline.py --category "AI-assisted coding"
# python .claude/skills/vibe-coding-pipeline/pipeline.py --min-score 0.85 --limit 100

# ============================================================
# PYTHON API USAGE
# ============================================================


async def example_full_pipeline():
    """Run the complete pipeline programmatically."""
    from .claude.skills.vibe_coding_pipeline.pipeline import VibeCodingPipeline
    import argparse

    # Create args
    args = argparse.Namespace(
        phase="all",
        platform="xhs,bili",
        min_score=0.7,
        category=None,
        limit=50,
        output_dir="./vibe_coding_designs",
        continue_on_error=False
    )

    # Run pipeline
    pipeline = VibeCodingPipeline(args)
    await pipeline.run()

    print(f"Pipeline complete!")
    print(f"Crawled: {pipeline.stats['crawled']}")
    print(f"Analyzed: {pipeline.stats['analyzed']}")
    print(f"Designed: {pipeline.stats['designed']}")


async def example_query_database():
    """Query the vibe_coding_raw_data table."""
    from database.supabase_client import get_supabase

    sb = get_supabase()

    # Get pending items
    pending = sb.table("vibe_coding_raw_data").select("*").eq("analysis_status", "pending").execute()
    print(f"Pending items: {len(pending.data)}")

    # Get high-scoring items
    top = (
        sb.table("vibe_coding_raw_data")
        .select("*")
        .gte("innovation_score", 0.7)
        .order("innovation_score", desc=True)
        .limit(10)
        .execute()
    )
    print(f"\nTop 10 high-scoring items:")
    for item in top.data:
        print(f"  - {item['title'][:50]} (score: {item['innovation_score']:.2f})")

    # Get by category
    category_items = (
        sb.table("vibe_coding_raw_data")
        .select("*")
        .eq("trend_category", "AI-assisted coding")
        .execute()
    )
    print(f"\nAI-assisted coding items: {len(category_items.data)}")


async def example_read_queue():
    """Read and process the implementation queue."""
    queue_file = Path("./vibe_coding_designs/QUEUE.json")

    if not queue_file.exists():
        print("Queue file not found. Run export phase first.")
        return

    with open(queue_file) as f:
        queue = json.load(f)

    print(f"Implementation queue: {len(queue)} items")
    print("\nTop 5 priority items:")

    for idx, item in enumerate(queue[:5], 1):
        print(f"\n{idx}. {item['title']}")
        print(f"   Priority: {item['priority']:.3f}")
        print(f"   Innovation: {item['innovation_score']:.2f}")
        print(f"   Design: {item['design_file']}")
        print(f"   URL: {item['url']}")


async def example_manual_analysis():
    """Manually analyze a single item (for testing prompts)."""
    from database.supabase_client import get_supabase

    sb = get_supabase()

    # Get one pending item
    result = sb.table("vibe_coding_raw_data").select("*").eq("analysis_status", "pending").limit(1).execute()

    if not result.data:
        print("No pending items found")
        return

    item = result.data[0]

    # Format analysis prompt
    top_comments = item.get("top_comments") or []
    comments_text = "\n".join([
        f"- {c.get('nickname', 'Anonymous')}: {c.get('content', '')} ({c.get('like_count', 0)} likes)"
        for c in top_comments[:10]
    ])

    prompt = f"""Analyze this vibe coding content:

Title: {item['title']}
Description: {item['description']}
Platform: {item['platform']}
Engagement: {item['liked_count']} likes, {item['comment_count']} comments

Top Comments:
{comments_text or 'No comments'}

Provide structured JSON analysis:
{{
  "innovation_score": 0.0-1.0,
  "feasibility_score": 0.0-1.0,
  "impact_score": 0.0-1.0,
  "key_ideas": ["idea 1", "idea 2"],
  "technical_stack": ["tech 1", "tech 2"],
  "use_cases": ["use case 1", "use case 2"],
  "implementation_complexity": "Low|Medium|High",
  "summary": "one-sentence summary"
}}
"""

    print("Analysis Prompt:")
    print("=" * 60)
    print(prompt)
    print("=" * 60)

    # TODO: Call Claude API with this prompt
    # For now, just print the prompt for manual testing


async def example_openclaw_integration():
    """Example OpenClaw integration workflow."""
    print("OpenClaw Integration Example")
    print("=" * 60)

    # Step 1: Run vibe coding pipeline
    print("\n1. Running vibe coding pipeline...")
    print("   openclaw.run_skill('vibe-coding-pipeline', {...})")

    # Step 2: Read implementation queue
    print("\n2. Reading implementation queue...")
    queue_file = Path("./vibe_coding_designs/QUEUE.json")
    if queue_file.exists():
        with open(queue_file) as f:
            queue = json.load(f)
        print(f"   Found {len(queue)} designs")

        # Step 3: Process top priority items
        print("\n3. Processing top priority items...")
        for item in queue[:3]:  # Top 3
            print(f"\n   Item: {item['title']}")
            print(f"   Priority: {item['priority']:.3f}")
            print(f"   Design: {item['design_file']}")
            print(f"   Action: openclaw.run_project('ai-product-builder', {{...}})")
    else:
        print("   Queue not found. Run pipeline first.")


# ============================================================
# CLAUDE CODE SKILL USAGE
# ============================================================

# In Claude Code, simply use:
# /vibe-coding-pipeline
# /vibe-coding-pipeline --platform xhs --min-score 0.8
# /vibe-coding-pipeline --phase analyze --limit 20

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        example = sys.argv[1]
        if example == "query":
            asyncio.run(example_query_database())
        elif example == "queue":
            asyncio.run(example_read_queue())
        elif example == "analyze":
            asyncio.run(example_manual_analysis())
        elif example == "openclaw":
            asyncio.run(example_openclaw_integration())
        else:
            print(f"Unknown example: {example}")
            print("Available: query, queue, analyze, openclaw")
    else:
        print("Vibe Coding Pipeline - Usage Examples")
        print("=" * 60)
        print("\nCommand line:")
        print("  python examples.py query      # Query database")
        print("  python examples.py queue      # Read implementation queue")
        print("  python examples.py analyze    # Test analysis prompt")
        print("  python examples.py openclaw   # OpenClaw integration example")
        print("\nClaude Code:")
        print("  /vibe-coding-pipeline")
        print("  /vibe-coding-pipeline --platform xhs --min-score 0.8")
