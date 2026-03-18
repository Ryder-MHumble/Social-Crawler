# Vibe Coding Pipeline - Quick Reference

## One-Line Commands

```bash
# Full pipeline
/vibe-coding-pipeline

# Crawl only
/vibe-coding-pipeline --phase crawl --platform xhs

# Analyze pending
/vibe-coding-pipeline --phase analyze --limit 20

# Generate designs
/vibe-coding-pipeline --phase design --min-score 0.8

# Export summary
/vibe-coding-pipeline --phase export
```

## Database Queries

```python
from database.supabase_client import get_supabase
sb = get_supabase()

# Pending items
sb.table("vibe_coding_raw_data").select("*").eq("analysis_status", "pending").execute()

# High-scoring
sb.table("vibe_coding_raw_data").select("*").gte("innovation_score", 0.7).execute()

# By category
sb.table("vibe_coding_raw_data").select("*").eq("trend_category", "AI-assisted coding").execute()
```

## Output Files

```
vibe_coding_designs/
├── SUMMARY.md              # Overview + top 10
├── QUEUE.json              # Prioritized list
├── xhs_*_design.md         # Design proposals
└── logs/*.log              # Execution logs
```

## Workflow States

```
pending → analyzed → design_generated → implemented
```

## Key Parameters

| Flag | Default | Description |
|------|---------|-------------|
| `--phase` | `all` | crawl\|analyze\|design\|export\|all |
| `--platform` | `xhs,bili` | Platforms to crawl |
| `--min-score` | `0.7` | Min innovation score (0-1) |
| `--limit` | `50` | Max items to process |

## Troubleshooting

| Issue | Fix |
|-------|-----|
| No items collected | Check cookies, lower `KEYWORD_SCORE_THRESHOLD` |
| Analysis fails | Check Claude API key, reduce `--limit` |
| Designs too generic | Increase `--min-score`, refine prompts |

## OpenClaw Integration

```python
# Run pipeline
openclaw.run_skill("vibe-coding-pipeline", {"min_score": 0.75})

# Read queue
queue = json.load(open("vibe_coding_designs/QUEUE.json"))

# Implement top items
for item in queue[:5]:
    openclaw.run_project("ai-product-builder", {
        "design_file": f"vibe_coding_designs/{item['design_file']}"
    })
```

## Analysis Output

```json
{
  "innovation_score": 0.85,
  "feasibility_score": 0.80,
  "impact_score": 0.75,
  "key_ideas": ["idea1", "idea2"],
  "technical_stack": ["Cursor", "Next.js"],
  "use_cases": ["use1", "use2"],
  "implementation_complexity": "Medium"
}
```

## Design Sections

1. Executive Summary
2. Problem Statement
3. Proposed Solution
4. Technical Architecture
5. Implementation Plan
6. Technology Stack
7. User Stories
8. Success Metrics
9. Risks & Mitigations
10. Next Steps
