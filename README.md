# MediaCrawler — 社交媒体舆情采集系统

基于 Playwright + CDP 的多平台社交媒体内容爬取框架，当前配置用于监测**中关村人工智能研究院**和**北京中关村学院**的相关舆情，数据统一存储至 Supabase（PostgreSQL）。

---

## 支持平台

| 平台 | 代码 | 内容 | 一级评论 | 二级评论 | 创作者 |
| ---- | ---- | ---- | -------- | -------- | ------ |
| 小红书 | `xhs` | ✅ 笔记 | ✅ | ✅ | ✅ |
| 抖音 | `dy` | ✅ 视频 | ✅ | ✅ | ✅ |
| B 站 | `bili` | ✅ 视频 | ✅ | ✅ | ✅（含动态/粉丝关系） |
| 微博 | `wb` | ✅ 帖子 | ✅ | ✅ | ✅ |
| 快手 | `ks` | ✅ 视频 | ✅ | ✅ | ✅ |
| 贴吧 | `tieba` | ✅ 帖子 | ✅ | ✅ | ✅ |
| 知乎 | `zhihu` | ✅ 回答/文章 | ✅ | ✅ | ✅ |

当前默认爬取：小红书、抖音、B站、微博（见 [run.py](run.py#L33)）。

---

## 核心能力

### 1. 真实浏览器驱动（反检测）

通过 **CDP（Chrome DevTools Protocol）** 直接接管用户本机已安装的 Chrome，而非模拟浏览器：

- 使用用户真实的浏览器指纹、扩展、历史记录
- 登录状态持久保存（`browser_data/` 目录），Cookie 长期有效
- `AUTO_CLOSE_BROWSER = False`：爬完不关浏览器，Cookie 不失效

### 2. 关键词搜索 + 相关性过滤

爬取流程：平台关键词搜索 → 相关性过滤 → 保存至 Supabase

当前关键词（[run.py:30](run.py#L30)）：

```text
中关村人工智能研究院, 北京中关村学院, 中关村学院
```

相关性过滤（[base_config.py:34](config/base_config.py#L34)）：只保存内容中实际出现以下词语之一的结果，避免平台模糊搜索带来的无关数据：

```python
RELEVANCE_MUST_CONTAIN = [
    "中关村人工智能研究院",
    "中关村学院",
    "北京中关村学院",
    "中关村AI研究院",
]
```

### 3. 数据去重

- **跨次运行去重**：每次启动时从 Supabase 预加载已存在的 content_id，跳过重复内容
- **单次运行内去重**：同一 content 被多个关键词搜索到时，只处理一次
- **数据库层去重**：Supabase upsert + `UNIQUE(platform, content_id)` 约束保底

### 4. 统一数据库结构

所有平台数据写入同一套表，便于后端跨平台查询分析：

```text
contents          — 内容主表 (platform + content_id 唯一)
comments          — 评论表   (platform + comment_id 唯一，含二级回复)
creators          — 创作者表 (platform + user_id 唯一)
bilibili_contacts — B站粉丝关系
bilibili_dynamics — B站动态
```

平台专有字段存入 `platform_data JSONB` 列，不影响主表结构。

---

## 当前爬取参数

| 参数 | 值 | 说明 |
| ---- | -- | ---- |
| `CRAWLER_MAX_NOTES_COUNT` | 30 | 每关键词最多获取 30 条搜索结果 |
| `CRAWLER_MAX_COMMENTS_COUNT_SINGLENOTES` | 20 | 每条内容最多爬 20 条一级评论 |
| `ENABLE_GET_SUB_COMMENTS` | True | 开启二级评论（回复链） |
| `CRAWLER_MAX_SLEEP_SEC` | 5 | 请求间隔最大 5 秒（防封号） |
| `MAX_CONCURRENCY_NUM` | 1 | 单线程顺序爬取 |

---

## 快速开始

### 环境要求

- Python 3.11+
- [uv](https://github.com/astral-sh/uv)（包管理）
- 本机已安装 Google Chrome

### 安装依赖

```bash
uv sync
```

### 配置 Supabase

在项目根目录创建 `.env`（参考 `.env.example`）：

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-service-role-key
```

首次使用需在 Supabase SQL Editor 执行 [schema/supabase_migration.sql](schema/supabase_migration.sql) 建表。

### 运行

```bash
# 正常模式：检查登录 → 串行爬取所有配置的平台
python run.py

# 仅登录（首次使用或 Cookie 失效时）
python run.py --login-only

# 跳过登录检查直接爬取
python run.py --crawl-only

# 单平台爬取（直接调用底层入口）
uv run main.py --platform xhs --lt qrcode --type search \
  --keywords "中关村学院" --save_data_option supabase
```

### 登录方式

- **扫码登录**（默认）：首次运行浏览器会弹出二维码，扫码后登录状态自动保存
- **Cookie 登录**：在 `cookies_config.py` 中填入各平台 Cookie，参考 `COOKIE_GUIDE.md`

---

## 项目结构

```text
MediaCrawler/
├── run.py                       # 统一运行入口（配置关键词/平台）
├── main.py                      # 底层爬取入口（单平台）
├── config/
│   ├── base_config.py           # 全局配置（爬取参数、过滤规则等）
│   └── {platform}_config.py    # 各平台专属配置
├── media_platform/
│   └── {xhs,dy,bili,wb,...}/   # 各平台爬取逻辑
│       ├── core.py              # 主爬取流程
│       └── client.py            # API 客户端
├── store/
│   ├── {platform}/__init__.py  # 各平台 StoreFactory
│   └── supabase_store_impl.py  # 各平台字段映射实现
├── database/
│   ├── supabase_client.py       # Supabase 单例客户端
│   └── supabase_store_base.py  # 统一存储基类（去重 + 过滤逻辑）
├── tools/
│   ├── cdp_browser.py           # CDP 浏览器管理器
│   └── browser_launcher.py      # Chrome 进程启动器
├── schema/
│   └── supabase_migration.sql   # Supabase 建表 SQL
└── browser_data/                # 浏览器登录状态缓存（本地）
```

---

## 数据流

```text
run.py
  └─ main.py (per platform)
       └─ core.py
            ├─ launch_browser_with_cdp()   # 启动真实 Chrome
            ├─ search_posts(keyword)        # 关键词搜索
            ├─ store.store_content()        # 相关性过滤 → Supabase upsert
            ├─ fetch_comments(content_id)   # 爬取评论
            └─ store.store_comment()        # 去重 → Supabase upsert
```

---

## 注意事项

- 本项目仅供学习和内部研究使用，请遵守目标平台的服务条款
- 建议控制爬取频率，避免账号风险
- Cookie 有效期因平台而异，定期检查登录状态
