# Cookie 登录配置完成指南

## ✅ 已完成的工作

我已经为你完成了以下配置：

1. ✅ 创建了 [cookies_config.py](cookies_config.py) - Cookie 配置文件
2. ✅ 创建了 [COOKIE_GUIDE.md](COOKIE_GUIDE.md) - 详细的 Cookie 获取指南
3. ✅ 修改了 [run.py](run.py) - 支持 Cookie 登录
4. ✅ 更新了所有文档 - 添加 Cookie 登录说明
5. ✅ 添加了 `.gitignore` - 防止意外提交 Cookie

---

## 🚀 如何使用 Cookie 登录

### 第一步：获取平台 Cookie

打开 [COOKIE_GUIDE.md](COOKIE_GUIDE.md)，按照指南获取各平台的 Cookie。

**快速步骤**（以小红书为例）：

1. 访问 https://www.xiaohongshu.com
2. 登录你的账号
3. 按 `F12` 打开开发者工具
4. 切换到 `Network` 标签
5. 刷新页面（F5）
6. 点击任意请求
7. 在 `Request Headers` 中找到 `Cookie:`
8. 复制完整的 Cookie 值

### 第二步：填写 Cookie 配置

编辑 [cookies_config.py](cookies_config.py)：

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-

# ==================== Cookie 配置 ====================

# 小红书 Cookie
XHS_COOKIE = "这里填写你复制的完整 Cookie"

# 抖音 Cookie
DOUYIN_COOKIE = "这里填写你复制的完整 Cookie"

# Bilibili Cookie
BILIBILI_COOKIE = "这里填写你复制的完整 Cookie"

# 微博 Cookie
WEIBO_COOKIE = "这里填写你复制的完整 Cookie"

# 快手 Cookie（可选）
KUAISHOU_COOKIE = ""
```

**示例**（小红书）：
```python
XHS_COOKIE = "a1=18a1234567890abcdef; webId=abc123def456; web_session=040069b1234567890abcdef; xsecappid=xhs-pc-web"
```

### 第三步：运行爬虫

配置完成后，直接运行：

```bash
cd /Users/sunminghao/Desktop/MediaCrawler
python run.py
```

脚本会自动：
1. 检测到你已配置的 Cookie
2. 使用 Cookie 登录（无需扫码）
3. 开始串行爬取各平台数据
4. **无需任何确认**：直接开始爬取，失败的平台会自动跳过并提示

---

## ⚙️ 配置选项

### 修改登录方式

编辑 [run.py](run.py) 的配置区域：

```python
# 爬取配置
LOGIN_TYPE = "cookie"  # 使用 Cookie 登录
# 或
LOGIN_TYPE = "qrcode"  # 使用扫码登录
```

### 修改爬取平台

```python
# 平台配置
PLATFORMS = ["xhs", "dy", "bili", "wb"]  # 可以添加或删除平台
```

可选平台：
- `xhs` - 小红书
- `dy` - 抖音
- `bili` - Bilibili
- `wb` - 微博
- `ks` - 快手

### 修改关键词

```python
# 关键词配置
KEYWORDS = "中关村人工智能研究院,北京中关村学院"
```

---

## 📝 运行模式

### 模式1: 自动模式（推荐）
```bash
python run.py
```
自动检查 Cookie 配置 → 串行爬取

### 模式2: 仅爬取模式（用于定时任务）
```bash
python run.py --crawl-only
```
跳过检查，直接爬取

### 模式3: 仅登录模式
```bash
python run.py --login-only
```
只检查 Cookie 配置，不爬取

---

## 🤖 配置定时任务

配置 Cookie 后，可以设置 cron 定时任务：

```bash
crontab -e
```

添加（每天早上9点自动爬取）：
```cron
0 9 * * * cd /Users/sunminghao/Desktop/MediaCrawler && /usr/bin/python /Users/sunminghao/Desktop/MediaCrawler/run.py --crawl-only >> /tmp/mediacrawler.log 2>&1
```

**优势**：
- ✅ 无需人工干预
- ✅ 无需扫码登录
- ✅ 全自动运行

---

## 🔧 常见问题

### Q: Cookie 会过期吗？
A: 会的，通常 15-30 天。过期后需要重新获取并更新配置。

### Q: 如何知道 Cookie 是否有效？
A: 运行 `python run.py`，如果显示"登录失败"或"未登录"，说明 Cookie 已过期。

### Q: 可以只配置部分平台的 Cookie 吗？
A: 可以！未配置 Cookie 的平台会尝试使用缓存的登录状态，如果没有缓存则会提示。

### Q: Cookie 安全吗？
A: Cookie 等同于登录凭证，请勿分享给他人。我们已将 `cookies_config.py` 添加到 `.gitignore`，防止意外提交到 GitHub。

### Q: 如何切换回扫码登录？
A: 编辑 [run.py](run.py)，将 `LOGIN_TYPE` 改为 `"qrcode"`。

---

## 📂 文件说明

| 文件 | 说明 |
|------|------|
| [cookies_config.py](cookies_config.py) | Cookie 配置文件（需要你填写） |
| [COOKIE_GUIDE.md](COOKIE_GUIDE.md) | Cookie 获取详细指南 |
| [run.py](run.py) | 主运行脚本 |
| [README_CRAWLER.md](README_CRAWLER.md) | 使用说明 |
| [QUICK_START.md](QUICK_START.md) | 快速开始指南 |

---

## 🎯 下一步

1. 📖 **阅读** [COOKIE_GUIDE.md](COOKIE_GUIDE.md) 了解如何获取 Cookie
2. ✏️ **编辑** [cookies_config.py](cookies_config.py) 填写各平台的 Cookie
3. 🚀 **运行** `python run.py` 开始爬取
4. ⏰ **配置** cron 定时任务实现自动化

---

## ⚠️ 重要提醒

1. **Cookie 安全**
   - Cookie 等同于登录密码，请妥善保管
   - 不要将 `cookies_config.py` 上传到公开平台
   - 已添加到 `.gitignore`，git 不会提交此文件

2. **Cookie 有效期**
   - Cookie 通常 15-30 天过期
   - 建议定期更新（每月一次）
   - 爬取失败时首先检查 Cookie 是否过期

3. **合规使用**
   - 仅供学习研究使用
   - 遵守平台使用规则
   - 控制爬取频率
   - 不得用于商业用途

---

需要帮助？查看 [COOKIE_GUIDE.md](COOKIE_GUIDE.md) 或查阅其他文档。
