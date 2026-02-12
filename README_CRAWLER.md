# MediaCrawler 自动爬取使用指南

## 🔑 Cookie 登录（推荐）

**无需扫码，一次配置，永久使用！**

### 快速配置

1. **获取 Cookie**：参考 [COOKIE_GUIDE.md](COOKIE_GUIDE.md) 获取各平台的 Cookie
2. **填写配置**：编辑 [cookies_config.py](cookies_config.py) 填写 Cookie
3. **开始爬取**：运行 `python run.py`

详细步骤请查看：[COOKIE_GUIDE.md](COOKIE_GUIDE.md)

---

## ✅ 一键运行

```bash
cd /Users/sunminghao/Desktop/MediaCrawler
python run.py
```

自动完成：
1. 检查 Cookie 配置（或登录状态）
2. 如果未配置，引导完成登录
3. 自动开始串行爬取所有平台（逐个执行，稳定可靠）

**就这么简单！** 🎉

## 📝 使用模式

### 模式1: 自动模式（推荐）
```bash
python run.py
```
自动检查登录 → 引导登录 → 串行爬取（逐个平台）

### 模式2: 仅登录
```bash
python run.py --login-only
```
只检查和完成登录，不爬取

### 模式3: 仅爬取
```bash
python run.py --crawl-only
```
跳过登录检查，直接开始爬取（逐个平台，适合定时任务）

### 单平台爬取
```bash
python crawl_platform.py xhs   # 小红书
python crawl_platform.py dy    # 抖音
python crawl_platform.py bili  # B站
python crawl_platform.py wb    # 微博
```

## ⚙️ 配置

### 1. Cookie 配置（推荐）

编辑 [cookies_config.py](cookies_config.py)：

```python
# 小红书 Cookie
XHS_COOKIE = "你的完整 Cookie"

# 抖音 Cookie
DOUYIN_COOKIE = "你的完整 Cookie"

# Bilibili Cookie
BILIBILI_COOKIE = "你的完整 Cookie"

# 微博 Cookie
WEIBO_COOKIE = "你的完整 Cookie"
```

**如何获取 Cookie？** 查看 [COOKIE_GUIDE.md](COOKIE_GUIDE.md)

### 2. 爬虫配置

编辑 [run.py](run.py) 配置区域：

```python
# 关键词配置
KEYWORDS = "中关村人工智能研究院,北京中关村学院"

# 平台配置
PLATFORMS = ["xhs", "dy", "bili", "wb"]

# 登录方式
LOGIN_TYPE = "cookie"  # cookie（推荐）或 qrcode（扫码）

# 可选平台: xhs, dy, bili, wb, ks, tieba, zhihu
```

## 🤖 配置 Nanobot 定时任务

```bash
crontab -e
```

添加（每天早上9点自动爬取）：
```
0 9 * * * cd /Users/sunminghao/Desktop/MediaCrawler && /usr/bin/python /Users/sunminghao/Desktop/MediaCrawler/run.py --crawl-only >> /tmp/mediacrawler.log 2>&1
```

**注意：** 定时任务使用 `--crawl-only` 跳过登录检查

## 📂 数据位置

```
数据: /Users/sunminghao/Desktop/MediaCrawler/data/
  ├── xhs/json/      # 小红书
  ├── douyin/json/   # 抖音
  ├── bili/json/     # B站
  └── weibo/json/    # 微博

日志: /Users/sunminghao/Desktop/MediaCrawler/logs/
  ├── xhs_crawl.log
  ├── dy_crawl.log
  ├── bili_crawl.log
  └── wb_crawl.log
```

## 🔧 常见问题

### Q: 第一次运行需要做什么？
A: 推荐配置 Cookie 登录（参考 [COOKIE_GUIDE.md](COOKIE_GUIDE.md)），或直接运行 `python run.py` 使用扫码登录

### Q: Cookie 登录和扫码登录有什么区别？
A:
- **Cookie 登录**（推荐）：一次配置，无需每次扫码，适合定时任务
- **扫码登录**：每次需要扫码，首次使用更方便

### Q: 如何切换登录方式？
A: 编辑 [run.py](run.py)，修改 `LOGIN_TYPE`：
```python
LOGIN_TYPE = "cookie"   # Cookie 登录
# 或
LOGIN_TYPE = "qrcode"  # 扫码登录
```

### Q: Cookie 过期了怎么办？
A: 重新获取 Cookie（参考 [COOKIE_GUIDE.md](COOKIE_GUIDE.md)），更新 [cookies_config.py](cookies_config.py)

### Q: 如何重新登录某个平台（扫码模式）？
A: 删除登录缓存后重新运行
```bash
rm -rf xhs_user_data_dir
python run.py --login-only
```

### Q: 如何查看爬取日志？
A:
```bash
# 查看特定平台
tail -f logs/xhs_crawl.log

# 查看所有平台
tail -f logs/*.log
```

### Q: 为什么使用串行爬取？
A:
- 串行更稳定：避免多平台同时登录导致的冲突
- 登录状态保持：确保每个平台登录状态正确保存
- 资源占用小：一次只运行一个平台，系统负担小
- 时间：约 40 分钟（逐个平台，但更可靠）

## 📚 更多文档

- [QUICK_START.md](QUICK_START.md) - 详细使用指南
- [NANOBOT_GUIDE.md](NANOBOT_GUIDE.md) - 定时任务配置

## ⚠️ 重要提醒

1. **首次运行**：直接 `python run.py`，脚本会引导登录
2. **定时任务**：首次手动运行完成登录后，再配置 cron
3. **爬取频率**：建议间隔 1-2 小时以上
4. **仅供学习**：遵守平台规则和相关法律

---

**立即开始：** `python run.py` 🚀
