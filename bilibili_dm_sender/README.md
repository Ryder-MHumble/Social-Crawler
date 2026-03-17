# B站私信自动发送工具

## 📁 文件说明

### 主要脚本

1. **send_bilibili_dm_manual.py** ⭐ 推荐使用
   - 并发版本（5个标签页同时发送）
   - 手动确认登录（按回车继续）
   - 反自动化检测
   - 直接访问私信页面

2. **send_bilibili_dm.py**
   - 旧版本（自动登录检测）
   - 仅供参考

3. **start_dm_sender.sh** ⭐ 快速启动
   - 一键启动脚本
   - 显示配置信息

### 辅助工具

4. **monitor_progress.sh**
   - Shell版本的进度监控

5. **monitor_realtime.py**
   - Python版本的实时监控
   - 更智能的日志显示

6. **test_bilibili_structure.py**
   - 测试工具，用于检查B站页面结构
   - 帮助调试选择器问题

### 文档

7. **BILIBILI_DM_README.md**
   - 详细使用说明
   - 注意事项和故障排查

## 🚀 快速开始

### 方式1：使用启动脚本（推荐）

```bash
cd /Users/sunminghao/Desktop/MediaCrawler/bilibili_dm_sender
./start_dm_sender.sh
```

### 方式2：直接运行Python脚本

```bash
cd /Users/sunminghao/Desktop/MediaCrawler/bilibili_dm_sender
python3 send_bilibili_dm_manual.py
```

## 📊 使用流程

1. **运行脚本** → 浏览器自动打开
2. **手动登录** → 在浏览器中完成B站登录
3. **按回车键** → 回到终端按回车继续
4. **自动发送** → 脚本开始并发发送私信
5. **查看结果** → 显示成功率统计

## ⚙️ 配置说明

### 数据源

脚本读取上级目录的CSV文件：
```
../openclaw_creators.csv
```

### 并发配置

在 `send_bilibili_dm_manual.py` 中修改：
```python
CONCURRENT_TABS = 5  # 同时打开的标签页数量
```

### 私信文案

在 `send_bilibili_dm_manual.py` 中修改：
```python
MESSAGE_TEMPLATE = """你的私信内容..."""
```

## 📈 性能指标

- **博主数量**: 201 位
- **并发数量**: 5 个标签页
- **预计时间**: 6-8 分钟
- **预计成功率**: 80-90%

## ⚠️ 注意事项

1. **反检测**: 已配置反自动化检测，避免"浏览器版本太低"提示
2. **频率控制**: 批次间自动延迟10秒
3. **账号安全**: 建议分时段发送，避免触发限制
4. **私信限制**: 部分博主可能关闭私信功能

## 🔧 故障排查

### 问题1: 找不到输入框

**原因**: B站页面结构变化

**解决**: 运行测试脚本检查页面结构
```bash
python3 test_bilibili_structure.py
```

### 问题2: 登录检测失败

**原因**: 登录选择器不匹配

**解决**: 使用手动确认版本（send_bilibili_dm_manual.py）

### 问题3: 浏览器显示"版本太低"

**原因**: B站检测到自动化浏览器

**解决**: 已在脚本中添加反检测代码

## 📝 更新日志

### v2.0 (2026-03-17)
- ✅ 添加并发发送功能（5个标签页）
- ✅ 添加反自动化检测
- ✅ 改为直接访问私信页面
- ✅ 优化选择器匹配
- ✅ 添加手动确认登录

### v1.0 (2026-03-17)
- ✅ 基础串行发送功能
- ✅ 自动登录检测

## 📞 技术支持

如遇问题，请检查：
1. Python 版本 >= 3.7
2. Playwright 是否正确安装
3. 网络连接是否正常
4. B站账号是否正常

## 📄 许可说明

本工具仅供学习和研究使用，使用者需遵守B站用户协议和相关法律法规。
