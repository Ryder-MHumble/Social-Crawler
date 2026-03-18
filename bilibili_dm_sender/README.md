# B站私信批量发送工具

自动化批量发送B站私信，支持并发发送、数据库记录、去重等功能。

## 📁 文件结构

```
bilibili_dm_sender/
├── openclaw_creators.csv          # 博主数据（201位）
├── send_bilibili_dm_manual.py     # 主发送脚本（带数据库记录）⭐
├── dm_record_store.py             # 数据库存储模块
├── schema.sql                     # 数据库表结构
├── check_dm_status.py             # 检查发送状态
├── monitor_realtime.py            # 实时监控脚本
├── start_dm_sender.sh             # 启动脚本
└── README.md                      # 本文档
```

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install playwright supabase
playwright install chromium
```

### 2. 配置数据库

在 Supabase SQL Editor 中执行 `schema.sql` 创建表：

```sql
-- 执行 schema.sql 中的所有SQL语句
```

### 3. 配置环境变量

确保 `config/base_config.py` 中配置了：

```python
SUPABASE_URL = "your_supabase_url"
SUPABASE_KEY = "your_supabase_key"
```

### 4. 运行发送脚本

```bash
cd /Users/sunminghao/Desktop/MediaCrawler/bilibili_dm_sender
./start_dm_sender.sh
```

或直接运行：

```bash
python3 send_bilibili_dm_manual.py
```

## 📊 数据库表结构

### `bilibili_dm_records` 表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGSERIAL | 主键 |
| user_id | TEXT | B站用户ID |
| username | TEXT | 用户名 |
| message | TEXT | 发送的消息内容 |
| status | TEXT | 发送状态 (success/failed) |
| error_msg | TEXT | 错误信息（失败时） |
| sent_at | TIMESTAMP | 发送时间 |
| campaign | TEXT | 活动标识 (openclaw_2026) |
| created_at | TIMESTAMP | 创建时间 |

**唯一约束**: `(user_id, campaign, status)` - 同一活动中每个用户只能有一条成功记录

## 🔍 查询统计

### 查看成功发送数量

```sql
SELECT campaign, COUNT(*) as success_count
FROM bilibili_dm_records
WHERE status = 'success'
GROUP BY campaign;
```

### 查看失败记录

```sql
SELECT username, error_msg, sent_at
FROM bilibili_dm_records
WHERE status = 'failed'
ORDER BY sent_at DESC;
```

### 查看今天发送的记录

```sql
SELECT username, status, sent_at
FROM bilibili_dm_records
WHERE DATE(sent_at) = CURRENT_DATE
ORDER BY sent_at DESC;
```

## 🛠️ 功能特性

### ✅ 已实现

1. **并发发送**: 5个标签页同时发送，效率提升5倍
2. **数据库记录**: 自动记录每条私信的发送状态
3. **去重机制**: 自动跳过已成功发送的用户
4. **反自动化检测**: 隐藏webdriver特征
5. **实时进度**: 显示发送进度和统计信息
6. **错误处理**: 记录失败原因，便于排查
7. **批次延迟**: 避免触发平台限制

### 📝 私信文案

```
hihi你好呀，抱歉打扰啦，我是北京中关村学院的研究员，看到你主页分享了很多Openclaw的落地应用，想邀请你参加我们举办的龙虾大赛，基本信息如下：

中关村学院正在办的"OpenClaw"比赛🎯，分学术龙虾、生产力龙虾和生活龙虾三条赛道，核心是看谁的"虾"解决实际问题能力更强。全场最佳奖金20万+100亿Token，每条赛道还各有10个获奖名额，截止日期3月19日23：59，还有最后两天时间

报名也很简单：上传个链接讲清楚你的虾能做什么就行，不用交代码，核心看实际应用效果，如果结合硬件会额外加分

报名链接：https://claw.lab.bza.edu.cn

详细信息可以看这条连接：https://mp.weixin.qq.com/s/RfqXfunmEP1NLIln-9YUvQ
```

## 📈 使用流程

1. **启动脚本** → 浏览器自动打开
2. **手动登录** → 在浏览器中登录B站
3. **按回车继续** → 脚本开始自动发送
4. **并发发送** → 5个标签页同时工作
5. **自动记录** → 每条消息都记录到数据库
6. **完成统计** → 显示成功/失败数量

## 🔧 工具脚本

### 检查发送状态

```bash
python3 check_dm_status.py
```

从浏览器会话中统计今天发送的私信数量。

### 实时监控

```bash
python3 monitor_realtime.py
```

实时显示发送进度和统计信息。

### 查询数据库

```bash
python3 dm_record_store.py
```

查询数据库中的发送记录和统计信息。

## ⚠️ 注意事项

1. **登录状态**: 首次运行需要手动登录，之后会保持登录状态
2. **发送限制**: B站可能有私信频率限制，脚本已添加延迟避免触发
3. **数据库配置**: 确保Supabase配置正确，否则无法记录数据
4. **去重功能**: 重复运行脚本会自动跳过已发送的用户
5. **错误处理**: 失败的消息会记录到数据库，可以后续重试

## 📊 性能指标

- **总用户数**: 201位博主
- **并发数**: 5个标签页
- **预计时间**: 6-8分钟
- **成功率**: 取决于网络和平台限制

## 🐛 故障排查

### 问题1: 找不到输入框

**原因**: B站页面结构变化
**解决**: 检查页面元素，更新选择器

### 问题2: 数据库连接失败

**原因**: Supabase配置错误
**解决**: 检查 `config/base_config.py` 中的配置

### 问题3: 发送失败

**原因**: 网络问题或平台限制
**解决**: 查看数据库中的 `error_msg` 字段

## 📝 更新日志

### v3.0 (2026-03-17)

- ✅ 添加数据库记录功能
- ✅ 实现去重机制
- ✅ 优化错误处理
- ✅ 更新私信文案
- ✅ 创建完整文档

### v2.0 (2026-03-17)
- ✅ 添加并发发送功能（5个标签页）
- ✅ 添加反自动化检测
- ✅ 改为直接访问私信页面
- ✅ 优化选择器匹配
- ✅ 添加手动确认登录

### v1.0 (2026-03-17)
- ✅ 基础串行发送功能
- ✅ 自动登录检测

## 📞 联系方式

如有问题，请联系项目维护者。

## 📄 许可说明

本工具仅供学习和研究使用，使用者需遵守B站用户协议和相关法律法规。
