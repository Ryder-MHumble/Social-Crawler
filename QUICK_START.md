# 快速开始指南

## 🔑 第一步：配置 Cookie（推荐）

为了避免每次都要扫码登录，建议配置 Cookie 登录：

### 1. 获取各平台的 Cookie

详细步骤请查看：[COOKIE_GUIDE.md](COOKIE_GUIDE.md)

简要步骤：
1. 用浏览器登录对应平台的网页版
2. 按 `F12` 打开开发者工具
3. 切换到 `Network` 标签，刷新页面
4. 找到请求，复制 `Cookie` 字段

### 2. 填写到配置文件

编辑 [cookies_config.py](cookies_config.py)：

```python
# 小红书 Cookie
XHS_COOKIE = "这里填写你复制的完整 Cookie"

# 抖音 Cookie
DOUYIN_COOKIE = "这里填写你复制的完整 Cookie"

# Bilibili Cookie
BILIBILI_COOKIE = "这里填写你复制的完整 Cookie"

# 微博 Cookie
WEIBO_COOKIE = "这里填写你复制的完整 Cookie"
```

---

## 🚀 第二步：一键运行

```bash
cd /Users/sunminghao/Desktop/MediaCrawler
python run.py
```

**就这么简单！** 脚本会自动：
1. 检查 Cookie 配置（或登录状态）
2. 如果未配置，引导完成登录
3. 自动开始串行爬取（逐个平台执行，稳定可靠）

## 📋 第三步：配置定时任务

### 第一步：首次运行

```bash
cd /Users/sunminghao/Desktop/MediaCrawler
python run.py
```

完成所有平台的 Cookie 配置或登录

### 第二步：验证正常

确认爬取成功，检查数据文件

### 第三步：配置 Cron

```bash
crontab -e
```

添加（每天早上9点自动爬取）：
```
0 9 * * * cd /Users/sunminghao/Desktop/MediaCrawler && /usr/bin/python /Users/sunminghao/Desktop/MediaCrawler/run.py --crawl-only >> /tmp/mediacrawler.log 2>&1
```

完成！🎉

---

## 📝 常用命令

### 自动模式（推荐）
```bash
cd /Users/sunminghao/Desktop/MediaCrawler
python run.py
```
自动检查登录 → 引导登录 → 串行爬取（逐个平台，稳定可靠）

### 仅登录模式
```bash
python run.py --login-only
```
只完成登录，不爬取

### 仅爬取模式
```bash
python run.py --crawl-only
```
跳过登录检查，直接爬取（用于定时任务）

### 单平台爬取
```bash
# 小红书
python crawl_platform.py xhs

# 抖音
python crawl_platform.py dy

# B站
python crawl_platform.py bili

# 微博
python crawl_platform.py wb
```

### 查看日志
```bash
# 特定平台日志
tail -f /Users/sunminghao/Desktop/MediaCrawler/logs/xhs_crawl.log

# 所有平台日志
tail -f /Users/sunminghao/Desktop/MediaCrawler/logs/*.log

# 定时任务日志
tail -f /tmp/mediacrawler.log
```

### 重新登录
```bash
cd /Users/sunminghao/Desktop/MediaCrawler

# 清除特定平台登录缓存
rm -rf xhs_user_data_dir

# 重新登录
python run.py --login-only
```

---

## 📂 数据位置

### 爬取的数据
```
/Users/sunminghao/Desktop/MediaCrawler/data/
├── xhs/json/      # 小红书数据
├── douyin/json/   # 抖音数据
├── bili/json/     # B站数据
└── weibo/json/    # 微博数据
```

### 日志文件
```
/tmp/mediacrawler_parallel.log           # 并行爬取总日志
/Users/sunminghao/Desktop/MediaCrawler/logs/  # 各平台详细日志
```

---

## ⚙️ 配置修改

### 修改关键词
编辑 [run.py](run.py) 配置区域：
```python
KEYWORDS = "你的关键词1,你的关键词2"
```

### 修改爬取平台
编辑 [run.py](run.py) 配置区域：
```python
PLATFORMS = ["xhs", "dy"]  # 只爬取小红书和抖音
```

### 修改登录方式
编辑 [run.py](run.py) 配置区域：
```python
LOGIN_TYPE = "cookie"  # cookie 或 qrcode
```
- `cookie`: 使用 Cookie 登录（推荐，无需扫码）
- `qrcode`: 使用扫码登录

### 修改定时时间
```bash
crontab -e
```

时间格式：`分 时 日 月 星期`
- 每6小时：`0 */6 * * *`
- 每天9点：`0 9 * * *`
- 每天9点和21点：`0 9,21 * * *`

---

## 🔧 问题排查

### 某个平台爬取失败
```bash
# 1. 查看日志
tail -n 100 /Users/sunminghao/Desktop/MediaCrawler/logs/xhs_crawl.log

# 2. 重新登录
rm -rf /Users/sunminghao/Desktop/MediaCrawler/xhs_user_data_dir
python first_time_login.py
```

### 定时任务不执行
```bash
# 查看cron配置
crontab -l

# 查看日志
tail -f /tmp/mediacrawler_parallel.log

# 手动测试
cd /Users/sunminghao/Desktop/MediaCrawler && python auto_crawl_parallel.py
```

---

## 📚 详细文档

- [并行爬取详细说明](PARALLEL_CRAWL_README.md)
- [Nanobot配置指南](NANOBOT_GUIDE.md)
- [完整使用手册](AUTO_CRAWL_README.md)

---

## ⚠️ 重要提醒

1. **首次使用必须先登录**：运行 `python first_time_login.py`
2. **定时任务前先测试**：确保手动运行正常后再配置cron
3. **控制爬取频率**：建议间隔1-2小时以上
4. **仅供学习研究**：遵守平台规则，勿用于商业用途

---

需要帮助？查看 [PARALLEL_CRAWL_README.md](PARALLEL_CRAWL_README.md)
