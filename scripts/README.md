# Scripts Layout

This repository keeps non-core entrypoints under `scripts/`:

- `scripts/integrations/`: small standalone services such as SMS webhooks.
- `scripts/manual/`: operator-driven tools that require prompts, browsers, or manual checks.
- `scripts/verification/`: verification and smoke scripts for live systems.

Task-owned workflow helpers live with their owning task package instead of under a generic script bucket.
