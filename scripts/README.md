# Scripts Layout

Non-core entrypoints are grouped under `scripts/`:

- `scripts/integrations/`: small standalone services such as SMS webhooks
- `scripts/manual/`: operator-facing tools that need prompts, browsers, or manual checks
- `scripts/verification/`: verification and smoke scripts for live systems

Helpers that belong to one task should stay with that task package instead of being dumped into a generic scripts directory.
