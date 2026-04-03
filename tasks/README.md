# Unified Task Layout

This project now has a unified task directory under `tasks/`:

```text
tasks/
  common/                # shared execution engine (welcome/progress/summary)
  sentiment_monitor/     # public-opinion monitoring task
  creator_outreach/      # keyword creator discovery + DM campaign task
  vibe_coding/           # vibe coding trend collection task
  runner/                # unified task menu / dispatcher
```

## Entry Commands

### macOS / Linux

```bash
./run_crawl.sh
./run_crawl.sh sentiment_monitor
./run_crawl.sh creator_outreach
./run_crawl.sh vibe_coding
```

### Windows PowerShell

```powershell
.\run_crawl.ps1
.\run_crawl.ps1 sentiment_monitor
.\run_crawl.ps1 creator_outreach
.\run_crawl.ps1 vibe_coding
```

### Windows CMD

```cmd
run_crawl.cmd
run_crawl.cmd sentiment_monitor
run_crawl.cmd creator_outreach
run_crawl.cmd vibe_coding
```

## Notes

- Running without parameters opens the interactive menu and numeric selection.
- Every task uses the same runtime framework:
  - task-specific welcome page
  - live progress dashboard
  - unified final result summary
- Logs are written to:
  - `logs/task_runs/<timestamp>_<task>/`

