# Cookie 获取指南

本指南详细说明如何从各个平台获取 Cookie，用于免扫码登录。

## 🔑 通用步骤

所有平台获取 Cookie 的基本步骤：

1. 使用浏览器（推荐 Chrome）访问平台网页版
2. 登录你的账号
3. 按 `F12` 打开开发者工具
4. 切换到 `Network`（网络）标签
5. 刷新页面（`F5`）
6. 在请求列表中找到任意请求
7. 查看 `Request Headers`（请求头）
8. 找到 `Cookie` 字段并复制完整内容

---

## 📱 小红书 (XiaoHongShu)

### 获取步骤

1. 访问 https://www.xiaohongshu.com
2. 点击右上角登录
3. 使用手机 APP 扫码登录或手机号登录
4. 登录成功后，按 `F12` 打开开发者工具
5. 切换到 `Network` 标签
6. 刷新页面
7. 在请求列表中点击任意以 `xiaohongshu.com` 为域名的请求
8. 在右侧面板中找到 `Request Headers`
9. 找到 `Cookie:` 开头的一行
10. 复制整行内容（不包括 `Cookie:` 前缀）

### Cookie 示例格式
```
a1=...; webId=...; web_session=...; xsecappid=...
```

### 重要字段
- `web_session`: 会话令牌（必需）
- `a1`: 用户标识（必需）

### 有效期
约 30 天，过期后需要重新获取

---

## 🎵 抖音 (Douyin)

### 获取步骤

1. 访问 https://www.douyin.com
2. 点击右上角登录
3. 使用手机 APP 扫码登录
4. 登录成功后，按 `F12` 打开开发者工具
5. 切换到 `Network` 标签
6. 刷新页面
7. 在请求列表中点击任意以 `douyin.com` 为域名的请求
8. 在右侧面板中找到 `Request Headers`
9. 找到 `Cookie:` 开头的一行
10. 复制整行内容（不包括 `Cookie:` 前缀）

### Cookie 示例格式
```
sessionid=...; sessionid_ss=...; sid_guard=...; uid_tt=...; uid_tt_ss=...
```

### 重要字段
- `sessionid`: 会话令牌（必需）
- `sid_guard`: 安全标识（必需）

### 有效期
约 30 天，过期后需要重新获取

---

## 📺 Bilibili

### 获取步骤

1. 访问 https://www.bilibili.com
2. 点击右上角登录
3. 使用手机 APP 扫码登录或账号密码登录
4. 登录成功后，按 `F12` 打开开发者工具
5. 切换到 `Network` 标签
6. 刷新页面
7. 在请求列表中点击任意以 `bilibili.com` 为域名的请求
8. 在右侧面板中找到 `Request Headers`
9. 找到 `Cookie:` 开头的一行
10. 复制整行内容（不包括 `Cookie:` 前缀）

### Cookie 示例格式
```
SESSDATA=...; bili_jct=...; DedeUserID=...; DedeUserID__ckMd5=...
```

### 重要字段
- `SESSDATA`: 会话令牌（必需）
- `bili_jct`: CSRF Token（必需）
- `DedeUserID`: 用户 ID（必需）

### 有效期
约 30 天，过期后需要重新获取

---

## 🐦 微博 (Weibo)

### 获取步骤

1. 访问 https://weibo.com
2. 点击右上角登录
3. 使用账号密码登录或手机验证码登录
4. 登录成功后，按 `F12` 打开开发者工具
5. 切换到 `Network` 标签
6. 刷新页面
7. 在请求列表中点击任意以 `weibo.com` 为域名的请求
8. 在右侧面板中找到 `Request Headers`
9. 找到 `Cookie:` 开头的一行
10. 复制整行内容（不包括 `Cookie:` 前缀）

### Cookie 示例格式
```
SUB=...; SUBP=...; XSRF-TOKEN=...; ALF=...
```

### 重要字段
- `SUB`: 用户凭证（必需）
- `SUBP`: 用户权限（必需）
- `XSRF-TOKEN`: CSRF Token（必需）

### 有效期
约 15-30 天，过期后需要重新获取

---

## 🎬 快手 (Kuaishou)

### 获取步骤

1. 访问 https://www.kuaishou.com
2. 点击右上角登录
3. 使用手机 APP 扫码登录
4. 登录成功后，按 `F12` 打开开发者工具
5. 切换到 `Network` 标签
6. 刷新页面
7. 在请求列表中点击任意以 `kuaishou.com` 为域名的请求
8. 在右侧面板中找到 `Request Headers`
9. 找到 `Cookie:` 开头的一行
10. 复制整行内容（不包括 `Cookie:` 前缀）

### Cookie 示例格式
```
userId=...; kuaishou.server.web_st=...; kuaishou.server.web_ph=...
```

### 重要字段
- `userId`: 用户 ID（必需）
- `kuaishou.server.web_st`: 会话令牌（必需）

### 有效期
约 30 天，过期后需要重新获取

---

## 📝 如何使用 Cookie

### 1. 获取 Cookie 后填写到配置文件

编辑 `cookies_config.py` 文件：

```python
# 小红书 Cookie
XHS_COOKIE = "这里填写你复制的完整 Cookie"

# 抖音 Cookie
DOUYIN_COOKIE = "这里填写你复制的完整 Cookie"

# Bilibili Cookie
BILIBILI_COOKIE = "这里填写你复制的完整 Cookie"

# 微博 Cookie
WEIBO_COOKIE = "这里填写你复制的完整 Cookie"

# 快手 Cookie
KUAISHOU_COOKIE = "这里填写你复制的完整 Cookie"
```

### 2. 运行爬虫

配置完成后，直接运行：

```bash
python run.py --crawl-only
```

无需再次登录，直接开始爬取！

---

## ⚠️ 注意事项

### 安全建议

1. **不要分享你的 Cookie**
   - Cookie 等同于登录凭证，泄露后他人可以登录你的账号
   - 不要将 Cookie 上传到 GitHub 等公开平台
   - 建议将 `cookies_config.py` 添加到 `.gitignore`

2. **定期更新 Cookie**
   - Cookie 有有效期，过期后需要重新获取
   - 如果爬虫显示"未登录"或"登录失败"，请更新 Cookie

3. **账号安全**
   - 使用 Cookie 登录不会影响你的账号安全
   - 建议使用小号进行爬取操作
   - 不要频繁爬取，避免被平台检测为异常行为

### Cookie 失效情况

以下情况会导致 Cookie 失效：

1. 在其他设备登录了相同账号
2. 修改了账号密码
3. Cookie 过期（通常 15-30 天）
4. 手动退出登录
5. 清除了浏览器缓存

### 检查 Cookie 是否有效

你可以使用以下方式检查 Cookie 是否有效：

```bash
# 运行测试爬取（只爬取少量数据）
python crawl_platform.py xhs
```

如果显示"登录成功"并成功爬取数据，说明 Cookie 有效。

---

## 🔧 问题排查

### Cookie 无效怎么办？

1. 检查是否完整复制了 Cookie（不要漏掉任何字符）
2. 检查 Cookie 是否包含必需字段（见各平台的"重要字段"部分）
3. 尝试重新获取 Cookie
4. 确认账号是否在网页版正常登录

### 爬取时显示"未登录"？

1. 检查 `cookies_config.py` 中对应平台的 Cookie 是否正确填写
2. 检查 Cookie 是否过期（重新获取）
3. 检查是否在其他设备登录导致当前 Cookie 失效

### 特殊字符问题？

如果 Cookie 中包含特殊字符，请确保：
1. 使用双引号包裹 Cookie 字符串
2. 完整复制，不要遗漏任何符号
3. 不要手动添加或删除任何空格

---

## 💡 提示

1. **推荐使用 Chrome 浏览器**
   - 开发者工具更友好
   - Cookie 格式更标准

2. **复制技巧**
   - 在开发者工具中，Cookie 行可以右键 → `Copy Value` 直接复制
   - 确保复制的是完整的一行，包括所有分号和等号

3. **多账号管理**
   - 如果你有多个账号，可以创建多个配置文件
   - 例如：`cookies_config_account1.py`、`cookies_config_account2.py`

---

需要帮助？查看项目 README 或提交 Issue。
