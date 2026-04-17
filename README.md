# Social-Crawler

一个基于 Playwright/CDP 的社交平台采集项目，已升级为“任务中心 + API/WebUI + 兼容旧入口”的统一运行架构。

## 支持平台

- `xhs` 小红书
- `dy` 抖音
- `bili` B 站
- `wb` 微博
- `ks` 快手
- `tieba` 百度贴吧
- `zhihu` 知乎

## 当前可运行任务

- `sentiment_monitor`: 多平台关键词舆情采集
- `creator_outreach`: 创作者发现与外联流程
- `vibe_coding`: 编程趋势采集任务

## 架构总览

```text
run_crawl.sh/.ps1/.cmd (兼容入口)
  -> apps/crawler/run_tasks.py
    -> tasks/runner/run_crawl.py (任务选择/--list/--dry-run)
      -> tasks/*/task.py (构建 TaskSpec)
        -> main.py (兼容单平台入口)
          -> media_platform/*/core.py + client.py
            -> store/* (json/csv/excel/sqlite/db/mongodb/supabase)

api/main.py (FastAPI)
  -> /api/* 路由 + /api/ws/* WebSocket
  -> 静态文件优先 runtime/webui，回退 api/webui

frontend/task_center (Vue3 + Vite)
  -> build 后发布到 runtime/webui (+ api/webui fallback)
```

## 环境要求

- Python `>=3.11`（`.python-version` 为 3.11）
- `uv`（推荐）
- Node.js `>=18`（建议 20）
- Chrome（CDP 模式）

## 安装依赖

```bash
# Python 依赖
uv sync

# 前端依赖（任务中心 WebUI）
cd frontend/task_center
npm ci
```

## 配置 `.env`

复制 `.env.example` 到 `.env`，至少配置以下项：

```env
# Redis（代理池/缓存相关能力需要）
REDIS_DB_HOST=127.0.0.1
REDIS_DB_PWD=123456
REDIS_DB_PORT=6379
REDIS_DB_NUM=0

# Supabase（使用 supabase 存储时必填）
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_service_role_key

# 可选：代理供应商
WANDOU_APP_KEY=
KDL_SECERT_ID=
KDL_SIGNATURE=
KDL_USER_NAME=
KDL_USER_PWD=
jisu_key=
jisu_crypto=
```

说明：
- 配置来源优先级：默认 `config/*` < `.env` < CLI 参数。
- 代理功能依赖 Redis。

## 运行方式

### 1) 任务中心 CLI（推荐）

不带参数时进入交互式菜单。

```bash
# macOS / Linux
./run_crawl.sh
./run_crawl.sh --list
./run_crawl.sh --dry-run sentiment_monitor
./run_crawl.sh sentiment_monitor
./run_crawl.sh creator_outreach
./run_crawl.sh vibe_coding
```

```powershell
# Windows PowerShell
.\run_crawl.ps1
.\run_crawl.ps1 --list
.\run_crawl.ps1 --dry-run sentiment_monitor
.\run_crawl.ps1 sentiment_monitor
```

```cmd
:: Windows CMD
run_crawl.cmd --list
run_crawl.cmd sentiment_monitor
```

### 2) 兼容旧单平台入口

仍可直接调用 `main.py`（兼容模式）：

```bash
uv run main.py --platform xhs --lt qrcode --type search \
  --keywords "人工智能,AI" --save_data_option json
```

常用参数：
- `--platform`: `xhs|dy|bili|wb|ks|tieba|zhihu`
- `--lt`: `qrcode|cookie|phone`
- `--type`: `search|detail|creator`
- `--save_data_option`: `json|csv|excel|sqlite|db|mongodb|supabase`

## 启动 API + WebUI

### 开发模式

```bash
./start_dev_local.sh
```

默认：
- 前端 `http://127.0.0.1:5180`
- 后端 `http://127.0.0.1:18080`

### 生产模式

```bash
./start_prod_server.sh
```

该脚本会先构建前端，再启动 `uvicorn apps.api.serve:app`。

## API 速查

基础：
- `GET /api/health`
- `GET /api/env/check`

任务中心：
- `GET /api/tasks`
- `GET /api/tasks/{slug}`
- `POST /api/tasks/{slug}/preview`
- `GET/POST /api/presets`
- `PUT/DELETE /api/presets/{preset_id}`
- `GET/POST /api/runs`
- `GET /api/runs/active`
- `POST /api/runs/active/stop`
- `GET /api/runs/{run_id}`
- `GET /api/runs/{run_id}/logs`

传统爬虫控制：
- `POST /api/crawler/start`
- `POST /api/crawler/stop`
- `GET /api/crawler/status`
- `GET /api/crawler/logs`

数据浏览：
- `GET /api/data/files`
- `GET /api/data/files/{file_path}`
- `GET /api/data/download/{file_path}`
- `GET /api/data/stats`

WebSocket：
- `WS /api/ws/logs`
- `WS /api/ws/status`
- `WS /api/ws/runs/active`

## 数据与运行目录

默认运行目录在 `runtime/`：
- `runtime/data`: 采集数据
- `runtime/logs/task_runs`: 任务日志
- `runtime/browser_data`: 浏览器登录态
- `runtime/task_center_state`: 任务中心状态（预设/运行记录）
- `runtime/webui`: 前端构建产物

可通过环境变量覆盖：
- `SOCIAL_CRAWLER_RUNTIME_DIR`
- `SOCIAL_CRAWLER_DATA_DIR`
- `SOCIAL_CRAWLER_BROWSER_DATA_DIR`
- `SOCIAL_CRAWLER_WEBUI_DIR`

## 测试与质量

```bash
# 默认执行 tests 下非 external 用例
uv run pytest

# 仅单元测试
uv run pytest tests/unit

# 集成测试
uv run pytest tests/integration
```

仓库还提供：
- `pre-commit`（基础质量钩子）
- `mypy.ini`（类型检查配置）
- `scripts/verification/*`（如 Supabase 连通性校验）

## 兼容性说明

- `run_crawl.sh/.ps1/.cmd` 与 `main.py` 会打印 `[Deprecated Entry]`，表示它们是兼容入口。
- 新功能优先围绕 `tasks/`、`api/`、`frontend/task_center/` 演进。

## 合规与许可

本项目遵循仓库根目录 [LICENSE](LICENSE) 中的条款（`NON-COMMERCIAL LEARNING LICENSE 1.1`）。
请仅用于学习与研究，并遵守目标平台服务条款与相关法律法规。
