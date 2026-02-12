# DeanAgent Social Crawler

🚀 基于 [MediaCrawler](https://github.com/NanmiCoder/MediaCrawler) 的自动化社交媒体爬虫系统

## ✨ 本项目特性

- 🔑 **Cookie 登录** - 无需扫码，一次配置永久使用
- 🚀 **全自动运行** - 无需任何确认，失败自动跳过
- 📊 **串行爬取** - 逐个平台执行，稳定可靠
- 📝 **详细文档** - 完整的中英文使用指南
- ⏰ **定时任务支持** - 配合 cron 实现全自动化
- 🛡️ **安全防护** - Cookie 配置自动加入 .gitignore

## 🎯 支持平台

- ✅ 小红书 (XiaoHongShu)
- ✅ 抖音 (Douyin)
- ✅ Bilibili
- ✅ 微博 (Weibo)
- ⚪ 快手 (Kuaishou) - 需配置

## 🚀 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/Ryder-MHumble/DeanAgent-Social-Crawler.git
cd DeanAgent-Social-Crawler
```

### 2. 安装依赖

```bash
# 使用 uv (推荐)
uv sync

# 或使用 pip
pip install -r requirements.txt

# 安装 Playwright 浏览器
uv run playwright install
```

### 3. 配置 Cookie

复制配置模板并填写各平台 Cookie：

```bash
cp cookies_config.py.example cookies_config.py
vim cookies_config.py  # 编辑填写 Cookie
```

如何获取 Cookie？查看 → [COOKIE_GUIDE.md](COOKIE_GUIDE.md)

### 4. 运行爬虫

```bash
python run.py
```

就这么简单！🎉

## 📚 完整文档

| 文档 | 说明 |
|------|------|
| [使用说明.md](使用说明.md) | 📘 中文快速上手指南 |
| [COOKIE_GUIDE.md](COOKIE_GUIDE.md) | 🔑 Cookie 获取详细教程 |
| [QUICK_START.md](QUICK_START.md) | ⚡ 快速开始指南 |
| [README_CRAWLER.md](README_CRAWLER.md) | 📖 完整使用手册 |
| [COOKIE_LOGIN_SETUP.md](COOKIE_LOGIN_SETUP.md) | ⚙️ Cookie 登录配置 |
| [NANOBOT_GUIDE.md](NANOBOT_GUIDE.md) | 🤖 定时任务配置 |

## ⚙️ 配置说明

### 修改爬取关键词

编辑 `run.py` 第 29 行：

```python
KEYWORDS = "中关村人工智能研究院,北京中关村学院"
```

### 修改爬取平台

编辑 `run.py` 第 32 行：

```python
PLATFORMS = ["xhs", "dy", "bili", "wb"]  # 可自由组合
```

### 切换登录方式

编辑 `run.py` 第 35 行：

```python
LOGIN_TYPE = "cookie"  # cookie（推荐）或 qrcode（扫码）
```

## 🤖 配置定时任务

使用 cron 设置每天自动爬取：

```bash
crontab -e
```

添加定时任务（每天早上 9 点）：

```cron
0 9 * * * cd /path/to/DeanAgent-Social-Crawler && /usr/bin/python run.py --crawl-only >> /tmp/mediacrawler.log 2>&1
```

更多时间配置：

```cron
# 每 6 小时执行一次
0 */6 * * * cd /path/to/DeanAgent-Social-Crawler && /usr/bin/python run.py --crawl-only >> /tmp/mediacrawler.log 2>&1

# 每天早晚各执行一次
0 9,21 * * * cd /path/to/DeanAgent-Social-Crawler && /usr/bin/python run.py --crawl-only >> /tmp/mediacrawler.log 2>&1
```

## 📂 数据输出结构

```
data/
├── xhs/json/      # 小红书数据（JSON 格式）
├── douyin/json/   # 抖音数据
├── bili/json/     # B站数据
└── weibo/json/    # 微博数据

logs/
├── xhs_crawl.log  # 小红书爬取日志
├── dy_crawl.log   # 抖音爬取日志
├── bili_crawl.log # B站爬取日志
└── wb_crawl.log   # 微博爬取日志
```

## 🔧 运行模式

### 自动模式（推荐）

```bash
python run.py
```

自动检查 Cookie 配置 → 串行爬取所有平台

### 仅爬取模式（适合定时任务）

```bash
python run.py --crawl-only
```

跳过检查，直接开始爬取

### 仅登录模式

```bash
python run.py --login-only
```

只检查 Cookie 配置，不爬取

### 单平台爬取

```bash
python crawl_platform.py xhs   # 爬取小红书
python crawl_platform.py dy    # 爬取抖音
python crawl_platform.py bili  # 爬取 B 站
python crawl_platform.py wb    # 爬取微博
```

## 💡 常见问题

### Q: Cookie 多久会过期？

A: 通常 15-30 天。过期后重新获取并更新 `cookies_config.py` 即可。

### Q: 如何知道 Cookie 是否有效？

A: 运行 `python run.py`，如果爬取成功就有效。失败会提示 "Cookie 可能已失效"。

### Q: 某个平台失败了会影响其他平台吗？

A: 不会！失败的平台会自动跳过，继续爬取其他平台。每个平台的状态会在总结报告中显示。

### Q: 运行时需要确认吗？

A: 不需要！直接运行 `python run.py`，全自动执行，**没有任何 y/n 确认提示**。

### Q: 数据保存在哪里？

A: 数据保存在 `data/` 目录，日志保存在 `logs/` 目录。

### Q: 如何查看爬取日志？

```bash
# 查看特定平台日志
tail -f logs/xhs_crawl.log

# 查看所有平台日志
tail -f logs/*.log

# 查看定时任务日志
tail -f /tmp/mediacrawler.log
```

## 🔒 安全说明

### Cookie 安全

- ⚠️ Cookie 等同于登录密码，**不要分享给他人**
- ✅ `cookies_config.py` 已添加到 `.gitignore`，不会被 git 提交
- ✅ 不要将包含 Cookie 的文件上传到公开平台
- 💡 建议使用小号进行爬取操作

### 文件说明

```
cookies_config.py        # Cookie 配置文件（已加入 .gitignore）
cookies_config.py.example  # 配置模板（可以提交）
```

## ⚠️ 免责声明

1. **仅供学习研究**
   - 本项目仅供学习和研究目的使用
   - 禁止用于任何商业用途
   - 禁止用于任何非法用途或侵犯他人合法权益

2. **遵守平台规则**
   - 遵守目标平台的使用条款和 robots.txt 规则
   - 不得进行大规模爬取或对平台造成运营干扰
   - 合理控制请求频率（建议间隔 1-2 小时以上）

3. **法律责任**
   - 对于因使用本项目内容而引起的任何法律责任，本项目不承担任何责任
   - 使用本项目即表示您同意本免责声明的所有条款和条件

4. **数据安全**
   - 定期备份 `data/` 目录中的数据
   - Cookie 过期后及时更新

## 🙏 致谢

本项目基于 [MediaCrawler](https://github.com/NanmiCoder/MediaCrawler) 开发，感谢原作者 [@NanmiCoder](https://github.com/NanmiCoder) 的优秀工作。

## 📄 许可证

本项目遵循原项目的 [NON-COMMERCIAL LEARNING LICENSE 1.1](LICENSE) 协议。

**声明：本代码仅供学习和研究目的使用，使用者应遵守相关法律法规和平台规则。**

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📞 联系方式

如有问题或建议，请在 GitHub 提交 Issue。

---

**立即开始：** `python run.py` 🚀

**完全自动化，无需任何操作！**
