# Task Layout

The task entrypoints now live under `tasks/`:

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
./social_crawler.sh task --list
./social_crawler.sh task sentiment_monitor
./social_crawler.sh task creator_outreach
./social_crawler.sh task vibe_coding
```

### Windows PowerShell

```powershell
.\social_crawler.ps1 task --list
.\social_crawler.ps1 task sentiment_monitor
.\social_crawler.ps1 task creator_outreach
.\social_crawler.ps1 task vibe_coding
```

## Notes

- Running without parameters opens the interactive menu.
- The old `run_crawl.*` wrappers were moved to `scripts/compat/` to keep the project root clean.
- All tasks use the same runtime shell:
  - task-specific welcome page
  - live progress view
  - final summary
- Logs are written to `runtime/logs/task_runs/<timestamp>_<task>/`.
