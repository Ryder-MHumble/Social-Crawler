# Nanobot 自动爬取配置指南

## 🎯 快速配置

### 项目路径
```
项目根目录: /Users/sunminghao/Desktop/MediaCrawler
运行脚本: /Users/sunminghao/Desktop/MediaCrawler/run.py
数据存储: /Users/sunminghao/Desktop/MediaCrawler/data/
```

### 执行命令

**推荐命令（用于定时任务）：**
```bash
cd /Users/sunminghao/Desktop/MediaCrawler && /usr/bin/python /Users/sunminghao/Desktop/MediaCrawler/run.py --crawl-only >> /tmp/mediacrawler.log 2>&1
```

**说明：** 使用 `--crawl-only` 参数跳过登录检查，直接开始串行爬取（逐个平台执行，稳定可靠）

## ⏰ Cron 定时任务配置

### 推荐配置（每天早上 9 点执行）
```bash
0 9 * * * cd /Users/sunminghao/Desktop/MediaCrawler && /usr/bin/python /Users/sunminghao/Desktop/MediaCrawler/run.py --crawl-only >> /tmp/mediacrawler.log 2>&1
```

### 其他时间选项
```bash
# 每 6 小时执行（0:00, 6:00, 12:00, 18:00）
0 */6 * * * cd /Users/sunminghao/Desktop/MediaCrawler && /usr/bin/python /Users/sunminghao/Desktop/MediaCrawler/run.py --crawl-only >> /tmp/mediacrawler.log 2>&1

# 每 12 小时执行（0:00, 12:00）
0 */12 * * * cd /Users/sunminghao/Desktop/MediaCrawler && /usr/bin/python /Users/sunminghao/Desktop/MediaCrawler/run.py --crawl-only >> /tmp/mediacrawler.log 2>&1

# 每天早上 9 点和晚上 9 点执行
0 9,21 * * * cd /Users/sunminghao/Desktop/MediaCrawler && /usr/bin/python /Users/sunminghao/Desktop/MediaCrawler/run.py --crawl-only >> /tmp/mediacrawler.log 2>&1
```

## 📊 爬取配置

### 目标关键词
```
中关村人工智能研究院
北京中关村学院
```

### 爬取平台
```
小红书 (xhs)
抖音 (dy)
Bilibili (bili)
微博 (wb)
```

### 数据保存位置
```
小红书数据: /Users/sunminghao/Desktop/MediaCrawler/data/xhs/json/
抖音数据:   /Users/sunminghao/Desktop/MediaCrawler/data/douyin/json/
Bilibili数据: /Users/sunminghao/Desktop/MediaCrawler/data/bili/json/
微博数据:   /Users/sunminghao/Desktop/MediaCrawler/data/weibo/json/
```

## 📝 执行日志

### 日志文件位置

#### 并行爬取日志
```
主日志: /tmp/mediacrawler_parallel.log
各平台日志: /Users/sunminghao/Desktop/MediaCrawler/logs/
  ├── xhs_crawl.log      # 小红书
  ├── dy_crawl.log       # 抖音
  ├── bili_crawl.log     # B站
  └── wb_crawl.log       # 微博
```

#### 串行爬取日志
```
/tmp/mediacrawler.log
```

### 查看日志命令
```bash
# 查看并行爬取总日志
tail -f /tmp/mediacrawler_parallel.log

# 查看特定平台日志
tail -f /Users/sunminghao/Desktop/MediaCrawler/logs/xhs_crawl.log

# 查看所有平台最新日志
tail -n 50 /Users/sunminghao/Desktop/MediaCrawler/logs/*.log

# 搜索错误信息
grep "错误\|失败\|Error" /Users/sunminghao/Desktop/MediaCrawler/logs/*.log
```

## 🔐 登录状态

### 登录缓存目录
```
小红书: /Users/sunminghao/Desktop/MediaCrawler/xhs_user_data_dir/
抖音:   /Users/sunminghao/Desktop/MediaCrawler/dy_user_data_dir/
B站:    /Users/sunminghao/Desktop/MediaCrawler/bili_user_data_dir/
微博:   /Users/sunminghao/Desktop/MediaCrawler/wb_user_data_dir/
```

### ⚠️ 首次运行必看

**重要：** 在配置 cron 定时任务前，必须先完成首次登录！

#### 使用自动化脚本（推荐）
```bash
cd /Users/sunminghao/Desktop/MediaCrawler
python run.py
```

脚本会自动：
- 检查哪些平台已登录
- 逐个引导你完成扫码登录
- 自动保存登录状态
- 登录完成后自动开始串行爬取（逐个平台，避免登录冲突）

#### 仅登录（不爬取）
```bash
cd /Users/sunminghao/Desktop/MediaCrawler
python run.py --login-only
```

#### 单个平台登录
```bash
# 登录小红书
python crawl_platform.py xhs

# 登录抖音
python crawl_platform.py dy
```

### 登录状态说明
- 第一次运行需要手动扫码登录
- 登录状态会自动保存
- 后续运行会自动使用已保存的登录状态
- 如登录过期，删除对应缓存目录后重新运行

## 🔧 故障处理

### 问题 1: 某个平台登录失败
```bash
# 查看该平台的日志
tail -n 100 /Users/sunminghao/Desktop/MediaCrawler/logs/xhs_crawl.log

# 清除该平台的登录缓存
rm -rf /Users/sunminghao/Desktop/MediaCrawler/xhs_user_data_dir

# 重新登录该平台
cd /Users/sunminghao/Desktop/MediaCrawler
python crawl_platform.py xhs
```

### 问题 2: 并行爬取某个平台失败
```bash
# 1. 查看日志找出失败原因
tail -f /Users/sunminghao/Desktop/MediaCrawler/logs/dy_crawl.log

# 2. 单独测试该平台
cd /Users/sunminghao/Desktop/MediaCrawler
python crawl_platform.py dy

# 3. 如果是登录问题，重新登录
rm -rf /Users/sunminghao/Desktop/MediaCrawler/dy_user_data_dir
python first_time_login.py
```

### 问题 3: 系统资源不足
```bash
# 方案 1: 减少并行平台数量
# 编辑 auto_crawl_parallel.py，只保留部分平台
nano /Users/sunminghao/Desktop/MediaCrawler/auto_crawl_parallel.py
# 修改: PLATFORMS = ["xhs", "dy"]  # 只爬取2个平台

# 方案 2: 改用串行脚本
cd /Users/sunminghao/Desktop/MediaCrawler
python auto_crawl.py
```

### 问题 4: 定时任务不执行
```bash
# 1. 检查 crontab 配置
crontab -l

# 2. 查看执行日志
tail -f /tmp/mediacrawler_parallel.log

# 3. 手动测试脚本
cd /Users/sunminghao/Desktop/MediaCrawler && python auto_crawl_parallel.py

# 4. 检查 cron 权限（macOS）
# 系统偏好设置 -> 安全性与隐私 -> 完全磁盘访问权限 -> 添加 cron
```

### 问题 5: 清理日志文件
```bash
# 清空所有日志
> /tmp/mediacrawler_parallel.log
> /Users/sunminghao/Desktop/MediaCrawler/logs/*.log

# 或删除旧日志
rm /Users/sunminghao/Desktop/MediaCrawler/logs/*.log
```

### 检查脚本状态
```bash
# 手动运行并行脚本测试
cd /Users/sunminghao/Desktop/MediaCrawler && python auto_crawl_parallel.py

# 手动运行串行脚本测试
cd /Users/sunminghao/Desktop/MediaCrawler && python auto_crawl.py

# 查看 cron 任务列表
crontab -l

# 检查 Python 路径
which python

# 检查所有平台登录状态
ls -ld /Users/sunminghao/Desktop/MediaCrawler/*_user_data_dir/
```

## ⚙️ 自定义配置

### 修改关键词
编辑文件: `/Users/sunminghao/Desktop/MediaCrawler/auto_crawl.py`
```python
KEYWORDS = "关键词1,关键词2,关键词3"
```

### 修改爬取平台
编辑文件: `/Users/sunminghao/Desktop/MediaCrawler/auto_crawl.py`
```python
PLATFORMS = ["xhs", "dy", "bili", "wb"]
```

### 修改爬取数量
编辑文件: `/Users/sunminghao/Desktop/MediaCrawler/auto_crawl.py`
```python
MAX_NOTES_COUNT = 20  # 每个关键词爬取的帖子数量
```

## 🔄 并行 vs 串行对比

### 并行爬取（推荐）
✅ **优点：**
- ⏱️ 速度快：多个平台同时运行，总耗时约等于单个平台的时间
- 🚀 效率高：4个平台并行约10分钟，串行需要40分钟
- 📊 资源利用率高

⚠️ **注意：**
- 💻 需要较多系统资源（内存、CPU）
- 🌐 需要稳定的网络连接
- 🔋 笔记本建议连接电源

**适合场景：** 定时任务、批量爬取、系统资源充足

### 串行爬取（备选）
✅ **优点：**
- 💻 占用资源少：一次只运行一个平台
- 🔒 更稳定：减少资源冲突
- 🛡️ 安全：适合资源受限的环境

⚠️ **注意：**
- ⏱️ 速度慢：需要逐个等待
- ⏳ 总时间长：4个平台约需40分钟

**适合场景：** 首次登录、资源受限、测试调试

## 📋 执行清单

### 初次设置
- [ ] 确认项目已安装依赖 (`uv sync`)
- [ ] 确认浏览器驱动已安装 (`uv run playwright install`)
- [ ] **运行统一脚本** (`python run.py`)
- [ ] 按提示完成所有平台的扫码登录
- [ ] 验证爬取成功，检查数据文件
- [ ] 配置 crontab 定时任务（使用 `run.py --crawl-only`）
- [ ] 验证定时任务正常执行

### 日常维护
- [ ] 定期查看执行日志 (`tail -f /tmp/mediacrawler.log`)
- [ ] 检查数据文件是否正常生成
- [ ] 确认登录状态有效（如失效需重新扫码）
- [ ] 控制爬取频率，避免过于频繁

## ⚠️ 重要提示

1. **首次运行必须手动执行**，完成扫码登录后，才能配置定时任务
2. **建议爬取间隔至少 1 小时以上**，避免对平台造成压力
3. **仅供学习研究使用**，请勿用于商业用途
4. **遵守平台规则**，尊重 robots.txt 和使用条款
5. **定期检查日志**，确保爬取任务正常执行
