# Frontend Layout

- `frontend/task_center/`: Vue 3 + TypeScript source code for the task board.
- `runtime/webui/`: primary built static assets served by FastAPI.
- `api/webui/`: legacy fallback static assets for compatibility.

Source code lives outside `api/` so the frontend can evolve independently.
The backend keeps only the compiled output it needs to serve.
