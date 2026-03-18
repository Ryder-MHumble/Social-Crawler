#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vibe Coding Pipeline - Implementation Script

Orchestrates the complete workflow from data collection to design generation.
Called by Claude Code via /vibe-coding-pipeline skill.
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from database.supabase_client import get_supabase
from vibe_coding.store import VibeCodingStore
from tools import utils


class VibeCodingPipeline:
    """Main pipeline orchestrator."""

    def __init__(self, args):
        self.args = args
        self.output_dir = Path(args.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.output_dir / "logs" / f"pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.stats = {
            "crawled": 0,
            "analyzed": 0,
            "designed": 0,
            "errors": []
        }

    def log(self, message: str, level: str = "INFO"):
        """Log message to both console and file."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{timestamp}] [{level}] {message}"
        print(log_line)
        with open(self.log_file, "a") as f:
            f.write(log_line + "\n")

    async def run(self):
        """Execute the pipeline based on phase argument."""
        phases = ["crawl", "analyze", "design", "export"] if self.args.phase == "all" else [self.args.phase]

        self.log(f"Starting Vibe Coding Pipeline - Phases: {', '.join(phases)}")
        self.log(f"Output directory: {self.output_dir}")

        for phase in phases:
            self.log(f"\n{'='*60}")
            self.log(f"Phase: {phase.upper()}")
            self.log(f"{'='*60}")

            try:
                if phase == "crawl":
                    await self.phase_crawl()
                elif phase == "analyze":
                    await self.phase_analyze()
                elif phase == "design":
                    await self.phase_design()
                elif phase == "export":
                    await self.phase_export()
            except Exception as e:
                self.log(f"Phase {phase} failed: {e}", "ERROR")
                self.stats["errors"].append({"phase": phase, "error": str(e)})
                if not self.args.continue_on_error:
                    raise

        self.log("\n" + "="*60)
        self.log("Pipeline Complete!")
        self.log(f"Crawled: {self.stats['crawled']}")
        self.log(f"Analyzed: {self.stats['analyzed']}")
        self.log(f"Designed: {self.stats['designed']}")
        if self.stats["errors"]:
            self.log(f"Errors: {len(self.stats['errors'])}", "WARNING")
        self.log("="*60)

    async def phase_crawl(self):
        """Phase 1: Crawl social media platforms."""
        import subprocess

        platforms = self.args.platform.split(",")
        self.log(f"Crawling platforms: {platforms}")

        for platform in platforms:
            self.log(f"Starting crawl: {platform}")
            cmd = ["python", "run_vibe_coding.py", "--platform", platform.strip()]
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                # Parse output for statistics
                output = result.stdout
                # Simple heuristic: count "SAVED" log lines
                saved_count = output.count("[VibeCodingStore] SAVED")
                self.stats["crawled"] += saved_count
                self.log(f"✓ {platform}: {saved_count} items collected")
            else:
                self.log(f"✗ {platform} crawl failed: {result.stderr}", "ERROR")
                self.stats["errors"].append({"phase": "crawl", "platform": platform, "error": result.stderr})

        self.log(f"Crawl complete: {self.stats['crawled']} total items")

    async def phase_analyze(self):
        """Phase 2: Analyze pending items with Claude API."""
        sb = get_supabase()

        # Fetch pending items
        query = sb.table("vibe_coding_raw_data").select("*").eq("analysis_status", "pending")

        if self.args.platform != "xhs,bili":
            platforms = self.args.platform.split(",")
            query = query.in_("platform", platforms)

        if self.args.category:
            query = query.eq("trend_category", self.args.category)

        query = query.order("publish_time", desc=True).limit(self.args.limit)

        result = query.execute()
        items = result.data or []

        self.log(f"Found {len(items)} pending items to analyze")

        for idx, item in enumerate(items, 1):
            self.log(f"Analyzing {idx}/{len(items)}: {item['title'][:50]}...")

            try:
                analysis = await self._analyze_item(item)
                await self._save_analysis(item, analysis)
                self.stats["analyzed"] += 1
                self.log(f"✓ Innovation score: {analysis['innovation_score']:.2f}")
            except Exception as e:
                self.log(f"✗ Analysis failed: {e}", "ERROR")
                self.stats["errors"].append({
                    "phase": "analyze",
                    "content_id": item["content_id"],
                    "error": str(e)
                })

        self.log(f"Analysis complete: {self.stats['analyzed']} items")

    async def _analyze_item(self, item: Dict) -> Dict:
        """Analyze a single item using Claude API."""
        # Format top comments
        top_comments = item.get("top_comments") or []
        comments_text = "\n".join([
            f"- {c.get('nickname', 'Anonymous')}: {c.get('content', '')} ({c.get('like_count', 0)} likes)"
            for c in top_comments[:10]
        ])

        prompt = f"""Analyze this vibe coding content for innovation potential:

Title: {item['title']}
Description: {item['description']}
Platform: {item['platform']}
Engagement: {item['liked_count']} likes, {item['comment_count']} comments
URL: {item.get('content_url', 'N/A')}

Top Comments:
{comments_text or 'No comments available'}

Provide structured analysis in JSON format:

{{
  "innovation_score": 0.0-1.0,
  "feasibility_score": 0.0-1.0,
  "impact_score": 0.0-1.0,
  "key_ideas": ["idea 1", "idea 2", "idea 3"],
  "technical_stack": ["tech 1", "tech 2"],
  "use_cases": ["use case 1", "use case 2"],
  "implementation_complexity": "Low|Medium|High",
  "recommended_category": "category name",
  "summary": "one-sentence summary"
}}

Focus on extracting replicable patterns and innovative workflows that could be implemented by indie developers or small teams.
"""

        # Call Claude API (placeholder - implement actual API call)
        # For now, return mock data
        # TODO: Integrate with actual Claude API via anthropic SDK
        return {
            "innovation_score": 0.75,
            "feasibility_score": 0.80,
            "impact_score": 0.70,
            "key_ideas": ["Extracted idea 1", "Extracted idea 2"],
            "technical_stack": ["Cursor", "Next.js", "Supabase"],
            "use_cases": ["Use case 1", "Use case 2"],
            "implementation_complexity": "Medium",
            "recommended_category": item["trend_category"],
            "summary": "AI-powered tool for rapid prototyping"
        }

    async def _save_analysis(self, item: Dict, analysis: Dict):
        """Save analysis results to database."""
        store = VibeCodingStore(item["platform"])
        await store.update_analysis_result(
            content_id=item["content_id"],
            innovation_score=analysis["innovation_score"],
            extracted_ideas=analysis,
            trend_category=analysis.get("recommended_category")
        )

    async def phase_design(self):
        """Phase 3: Generate design proposals for high-scoring items."""
        sb = get_supabase()

        # Fetch analyzed items with high scores
        query = (
            sb.table("vibe_coding_raw_data")
            .select("*")
            .eq("analysis_status", "analyzed")
            .gte("innovation_score", self.args.min_score)
        )

        if self.args.platform != "xhs,bili":
            platforms = self.args.platform.split(",")
            query = query.in_("platform", platforms)

        query = query.order("innovation_score", desc=True).limit(self.args.limit)

        result = query.execute()
        items = result.data or []

        self.log(f"Found {len(items)} high-scoring items for design generation")

        for idx, item in enumerate(items, 1):
            self.log(f"Generating design {idx}/{len(items)}: {item['title'][:50]}...")

            try:
                design_content = await self._generate_design(item)
                design_file = self._save_design(item, design_content)
                await self._mark_design_generated(item, design_file.name)
                self.stats["designed"] += 1
                self.log(f"✓ Design saved: {design_file.name}")
            except Exception as e:
                self.log(f"✗ Design generation failed: {e}", "ERROR")
                self.stats["errors"].append({
                    "phase": "design",
                    "content_id": item["content_id"],
                    "error": str(e)
                })

        self.log(f"Design generation complete: {self.stats['designed']} proposals")

    async def _generate_design(self, item: Dict) -> str:
        """Generate design proposal using Claude API."""
        analysis = item.get("extracted_ideas") or {}
        top_comments = item.get("top_comments") or []
        comments_summary = "\n".join([
            f"- {c.get('content', '')} ({c.get('like_count', 0)} likes)"
            for c in top_comments[:5]
        ])

        prompt = f"""Generate a professional technical design proposal based on this vibe coding idea:

## Source Content
- Title: {item['title']}
- Platform: {item['platform']}
- URL: {item.get('content_url', 'N/A')}
- Engagement: {item['liked_count']} likes, {item['comment_count']} comments

## Analysis Results
- Innovation Score: {item.get('innovation_score', 0):.2f}
- Feasibility Score: {analysis.get('feasibility_score', 0):.2f}
- Impact Score: {analysis.get('impact_score', 0):.2f}
- Key Ideas: {', '.join(analysis.get('key_ideas', []))}
- Technical Stack: {', '.join(analysis.get('technical_stack', []))}
- Use Cases: {', '.join(analysis.get('use_cases', []))}

## Top Community Insights
{comments_summary or 'No comments available'}

---

Create a comprehensive design proposal with these sections:

# [Project Name]

## Executive Summary
One-paragraph overview of the idea and its value proposition.

## Problem Statement
What specific pain point or opportunity does this address?

## Proposed Solution
Detailed description of the approach.

## Technical Architecture
System design with component diagram (mermaid syntax).

## Implementation Plan
Phase-by-phase breakdown with specific tasks.

## Technology Stack
Specific tools, frameworks, and services.

## User Stories
3-5 key scenarios.

## Success Metrics
Quantitative and qualitative measures.

## Risks & Mitigations
Table format.

## Next Steps
Immediate actions to start implementation.

Make the proposal actionable and ready for implementation using AI coding tools.
"""

        # TODO: Integrate with actual Claude API
        # For now, return template
        return f"""# {item['title']}

## Executive Summary
{analysis.get('summary', 'AI-powered solution for modern developers')}

## Problem Statement
[To be filled by Claude API]

## Proposed Solution
[To be filled by Claude API]

## Technical Architecture
[To be filled by Claude API]

## Implementation Plan
[To be filled by Claude API]

## Technology Stack
{', '.join(analysis.get('technical_stack', []))}

## User Stories
[To be filled by Claude API]

## Success Metrics
[To be filled by Claude API]

## Risks & Mitigations
[To be filled by Claude API]

## Next Steps
[To be filled by Claude API]

---
Source: {item.get('content_url', 'N/A')}
Innovation Score: {item.get('innovation_score', 0):.2f}
"""

    def _save_design(self, item: Dict, content: str) -> Path:
        """Save design proposal to file."""
        filename = f"{item['platform']}_{item['content_id']}_design.md"
        filepath = self.output_dir / filename
        filepath.write_text(content, encoding="utf-8")
        return filepath

    async def _mark_design_generated(self, item: Dict, design_id: str):
        """Mark item as design_generated in database."""
        store = VibeCodingStore(item["platform"])
        await store.mark_design_generated(item["content_id"], design_id)

    async def phase_export(self):
        """Phase 4: Export summary and implementation queue."""
        sb = get_supabase()

        # Fetch all analyzed items
        result = sb.table("vibe_coding_raw_data").select("*").neq("analysis_status", "pending").execute()
        items = result.data or []

        # Generate summary
        summary = self._generate_summary(items)
        summary_file = self.output_dir / "SUMMARY.md"
        summary_file.write_text(summary, encoding="utf-8")
        self.log(f"✓ Summary saved: {summary_file}")

        # Generate implementation queue
        queue = self._generate_queue(items)
        queue_file = self.output_dir / "QUEUE.json"
        queue_file.write_text(json.dumps(queue, indent=2, ensure_ascii=False), encoding="utf-8")
        self.log(f"✓ Queue saved: {queue_file}")

        self.log("Export complete")

    def _generate_summary(self, items: List[Dict]) -> str:
        """Generate summary report."""
        total = len(items)
        by_category = {}
        top_10 = sorted(
            [i for i in items if i.get("innovation_score")],
            key=lambda x: x.get("innovation_score", 0),
            reverse=True
        )[:10]

        for item in items:
            cat = item.get("trend_category", "other")
            by_category[cat] = by_category.get(cat, 0) + 1

        summary = f"""# Vibe Coding Pipeline Summary

Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Overview
- Total items: {total}
- Analyzed: {sum(1 for i in items if i.get('innovation_score'))}
- Designs generated: {sum(1 for i in items if i.get('analysis_status') == 'design_generated')}

## Top 10 Ideas by Innovation Score

"""
        for idx, item in enumerate(top_10, 1):
            summary += f"{idx}. **{item['title']}** (Score: {item.get('innovation_score', 0):.2f})\n"
            summary += f"   - Platform: {item['platform']}\n"
            summary += f"   - Category: {item.get('trend_category', 'N/A')}\n"
            summary += f"   - URL: {item.get('content_url', 'N/A')}\n\n"

        summary += "\n## Category Breakdown\n\n"
        for cat, count in sorted(by_category.items(), key=lambda x: x[1], reverse=True):
            summary += f"- {cat}: {count}\n"

        summary += "\n## Recommended Implementation Priority\n\n"
        summary += "See QUEUE.json for prioritized implementation queue.\n"

        return summary

    def _generate_queue(self, items: List[Dict]) -> List[Dict]:
        """Generate implementation queue sorted by priority."""
        queue = []
        for item in items:
            if item.get("analysis_status") == "design_generated":
                analysis = item.get("extracted_ideas") or {}
                priority = (
                    item.get("innovation_score", 0) *
                    analysis.get("feasibility_score", 0.5) *
                    analysis.get("impact_score", 0.5)
                )
                queue.append({
                    "priority": round(priority, 3),
                    "title": item["title"],
                    "platform": item["platform"],
                    "content_id": item["content_id"],
                    "design_file": f"{item['platform']}_{item['content_id']}_design.md",
                    "innovation_score": item.get("innovation_score", 0),
                    "url": item.get("content_url", ""),
                    "category": item.get("trend_category", "")
                })

        return sorted(queue, key=lambda x: x["priority"], reverse=True)


def main():
    parser = argparse.ArgumentParser(description="Vibe Coding Pipeline")
    parser.add_argument("--phase", default="all", choices=["all", "crawl", "analyze", "design", "export"])
    parser.add_argument("--platform", default="xhs,bili", help="Comma-separated platforms")
    parser.add_argument("--min-score", type=float, default=0.7, help="Min innovation score for design")
    parser.add_argument("--category", help="Filter by trend category")
    parser.add_argument("--limit", type=int, default=50, help="Max items to process")
    parser.add_argument("--output-dir", default="./vibe_coding_designs", help="Output directory")
    parser.add_argument("--continue-on-error", action="store_true", help="Continue on phase errors")

    args = parser.parse_args()

    pipeline = VibeCodingPipeline(args)
    asyncio.run(pipeline.run())


if __name__ == "__main__":
    main()
