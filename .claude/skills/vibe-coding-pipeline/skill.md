---
name: vibe-coding-pipeline
description: Complete pipeline for vibe coding data collection, idea extraction, and design proposal generation
version: 1.0.0
author: MediaCrawler Team
tags: [data-collection, ai-coding, idea-extraction, design-generation]
model: claude-sonnet-4-6
---

# Vibe Coding Pipeline Skill

Complete workflow for discovering innovative AI coding ideas from social media, extracting actionable insights, and generating professional design proposals.

## Overview

This skill orchestrates a 4-phase pipeline:

1. **Crawl Phase**: Collect vibe coding content from social media platforms
2. **Analysis Phase**: Extract innovative ideas and assess feasibility
3. **Design Phase**: Generate detailed technical design proposals
4. **Export Phase**: Prepare implementation-ready documentation

## Usage

```bash
# Full pipeline (crawl → analyze → design)
/vibe-coding-pipeline

# Individual phases
/vibe-coding-pipeline --phase crawl
/vibe-coding-pipeline --phase analyze
/vibe-coding-pipeline --phase design
/vibe-coding-pipeline --phase export

# With filters
/vibe-coding-pipeline --platform xhs --min-score 0.8
/vibe-coding-pipeline --phase analyze --category "AI-assisted coding"
```

## Parameters

- `--phase`: Specific phase to run (crawl|analyze|design|export). Default: all phases
- `--platform`: Platform to crawl (xhs|bili|dy|wb). Default: xhs,bili
- `--min-score`: Minimum innovation score for design generation (0-1). Default: 0.7
- `--category`: Filter by trend category. Default: all
- `--limit`: Max items to process. Default: 50
- `--output-dir`: Directory for generated designs. Default: ./vibe_coding_designs

## Phase Details

### Phase 1: Crawl

**Goal**: Collect fresh vibe coding content from social media

**Actions**:
1. Run `python run_vibe_coding.py --platform {platforms}`
2. Monitor crawl progress and log statistics
3. Report newly collected items count

**Success Criteria**: At least 10 new items collected

### Phase 2: Analysis

**Goal**: Extract innovative ideas and assess feasibility

**For each pending item**:
1. Read content title, description, and top comments
2. Use Claude API to analyze:
   - **Innovation Score** (0-1): Novelty and creativity
   - **Feasibility Score** (0-1): Technical practicality
   - **Impact Score** (0-1): Potential user value
   - **Key Ideas**: Structured list of actionable concepts
   - **Technical Stack**: Inferred technologies
   - **Use Cases**: Practical applications
3. Update database with analysis results
4. Categorize into refined trend categories

**Analysis Prompt Template**:
```
Analyze this vibe coding content for innovation potential:

Title: {title}
Description: {description}
Platform: {platform}
Engagement: {liked_count} likes, {comment_count} comments

Top Comments:
{top_comments}

Provide structured analysis:

1. Innovation Score (0-1): Rate the novelty and creativity
2. Feasibility Score (0-1): Rate technical practicality
3. Impact Score (0-1): Rate potential user value
4. Key Ideas: List 3-5 actionable concepts extracted
5. Technical Stack: Inferred technologies (e.g., Cursor, v0, Next.js)
6. Use Cases: 2-3 practical applications
7. Implementation Complexity: Low/Medium/High
8. Recommended Category: Best fit from [AI-assisted coding, no-code tools, workflow automation, indie hacking, rapid prototyping, tool comparison, learning resources, case studies]

Focus on extracting replicable patterns and innovative workflows.
```

**Success Criteria**: All pending items analyzed and scored

### Phase 3: Design

**Goal**: Generate detailed technical design proposals for high-scoring ideas

**For each high-scoring item** (innovation_score >= min-score):
1. Synthesize analysis results and comments
2. Generate comprehensive design proposal:
   - **Executive Summary**: One-paragraph overview
   - **Problem Statement**: What pain point does this solve?
   - **Proposed Solution**: Detailed approach
   - **Technical Architecture**: System design with diagrams
   - **Implementation Plan**: Step-by-step breakdown
   - **Technology Stack**: Specific tools and frameworks
   - **User Stories**: 3-5 key user scenarios
   - **Success Metrics**: How to measure impact
   - **Risks & Mitigations**: Potential challenges
3. Save as markdown file: `{output_dir}/{platform}_{content_id}_design.md`
4. Update database: `analysis_status = 'design_generated'`

**Design Prompt Template**:
```
Generate a professional technical design proposal based on this vibe coding idea:

## Source Content
- Title: {title}
- Platform: {platform}
- URL: {content_url}
- Engagement: {liked_count} likes, {comment_count} comments

## Analysis Results
- Innovation Score: {innovation_score}
- Feasibility Score: {feasibility_score}
- Impact Score: {impact_score}
- Key Ideas: {key_ideas}
- Technical Stack: {technical_stack}
- Use Cases: {use_cases}

## Top Community Insights
{top_comments_summary}

---

Create a comprehensive design proposal with these sections:

# [Project Name]

## Executive Summary
One-paragraph overview of the idea and its value proposition.

## Problem Statement
What specific pain point or opportunity does this address?

## Proposed Solution
Detailed description of the approach, including:
- Core functionality
- Key features
- User experience flow

## Technical Architecture
System design including:
- Component diagram (use mermaid syntax)
- Data flow
- Integration points
- Technology choices and rationale

## Implementation Plan
Phase-by-phase breakdown:
1. MVP (Week 1-2): Core features
2. Enhancement (Week 3-4): Polish and extend
3. Launch (Week 5): Deploy and iterate

For each phase, list specific tasks.

## Technology Stack
Specific tools, frameworks, and services:
- Frontend: [e.g., Next.js 14, Tailwind CSS, shadcn/ui]
- Backend: [e.g., Supabase, Vercel Functions]
- AI/Automation: [e.g., Claude API, Cursor IDE]
- Deployment: [e.g., Vercel, Railway]

## User Stories
3-5 key scenarios:
- As a [user type], I want to [action] so that [benefit]

## Success Metrics
How to measure impact:
- Quantitative: [e.g., 100 active users in month 1]
- Qualitative: [e.g., positive user feedback on ease of use]

## Risks & Mitigations
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| [Risk 1] | Low/Med/High | Low/Med/High | [Strategy] |

## Next Steps
Immediate actions to start implementation.

---

Make the proposal actionable and ready for a developer to implement using Claude Code or similar AI coding tools.
```

**Success Criteria**: Design proposals generated for all high-scoring items

### Phase 4: Export

**Goal**: Package designs for implementation handoff

**Actions**:
1. Generate summary report: `{output_dir}/SUMMARY.md`
   - Total items analyzed
   - Top 10 ideas by innovation score
   - Category breakdown
   - Recommended implementation priority
2. Create implementation queue: `{output_dir}/QUEUE.json`
   - Sorted by priority (innovation × feasibility × impact)
   - Include design file paths and metadata
3. Generate OpenClaw integration config

**Success Criteria**: All artifacts generated and ready for handoff

## Database Schema Reference

```sql
-- vibe_coding_raw_data table
SELECT
  platform,
  content_id,
  title,
  description,
  content_url,
  vibe_coding_keywords,
  trend_category,
  innovation_score,
  feasibility_score,
  impact_score,
  extracted_ideas,
  top_comments,
  analysis_status,
  design_proposal_id
FROM vibe_coding_raw_data
WHERE analysis_status = 'pending'
ORDER BY publish_time DESC;
```

## Integration with OpenClaw

This skill is designed to be called by OpenClaw for automated idea discovery:

```python
# OpenClaw workflow
openclaw.run_skill("vibe-coding-pipeline", {
    "phase": "all",
    "platform": "xhs,bili",
    "min_score": 0.75,
    "output_dir": "./designs/batch_001"
})

# Then pass designs to implementation project
for design in designs_queue:
    openclaw.run_project("ai-product-builder", {
        "design_file": design.path,
        "target_repo": "./products/{}".format(design.name)
    })
```

## Error Handling

- **Crawl fails**: Retry with exponential backoff, skip platform if persistent
- **Analysis fails**: Log error, mark item as `analysis_status = 'error'`, continue
- **Design generation fails**: Save partial design, mark for manual review
- **Database errors**: Rollback transaction, log details, alert user

## Output Structure

```
vibe_coding_designs/
├── SUMMARY.md                          # Overview report
├── QUEUE.json                          # Implementation queue
├── xhs_123456_design.md               # Individual designs
├── bili_789012_design.md
├── analysis_results.json              # Raw analysis data
└── logs/
    └── pipeline_20260317_143022.log   # Execution log
```

## Best Practices

1. **Run crawl phase daily** to keep data fresh
2. **Batch analyze** pending items weekly
3. **Review designs manually** before implementation
4. **Track implemented ideas** to measure success
5. **Iterate on prompts** based on design quality

## Troubleshooting

### No items collected
- Check `vibe_coding/config.py` keywords
- Verify platform cookies are valid
- Lower `KEYWORD_SCORE_THRESHOLD` temporarily

### Low innovation scores
- Review analysis prompt for bias
- Check if content quality is genuinely low
- Adjust scoring criteria in prompt

### Design proposals too generic
- Provide more context in design prompt
- Include more top comments for community insights
- Add specific examples from source content
