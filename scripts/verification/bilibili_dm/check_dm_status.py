#!/usr/bin/env python3
"""
检查B站私信发送状态
从浏览器的已发送消息中统计
"""

import asyncio
from playwright.async_api import async_playwright
import json
from datetime import datetime

async def check_sent_messages():
    """检查已发送的私信数量"""
    async with async_playwright() as p:
        # 使用持久化上下文（保持登录状态）
        browser = await p.chromium.launch_persistent_context(
            user_data_dir="/tmp/bilibili_dm_profile",
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
            ]
        )

        page = await browser.new_page()

        print("🌐 正在打开B站私信页面...")
        await page.goto("https://message.bilibili.com/#/whisper", wait_until="domcontentloaded")
        await page.wait_for_timeout(5000)

        print("\n📊 正在统计已发送的私信...")

        # 获取所有会话列表
        conversations = await page.query_selector_all('.list-item')

        print(f"\n✅ 找到 {len(conversations)} 个会话")

        # 统计今天发送的消息
        today = datetime.now().strftime("%Y-%m-%d")
        sent_today = []

        for i, conv in enumerate(conversations[:20], 1):  # 只检查前20个
            try:
                # 获取用户名
                username_elem = await conv.query_selector('.name')
                if username_elem:
                    username = await username_elem.inner_text()

                    # 获取最后消息时间
                    time_elem = await conv.query_selector('.time')
                    if time_elem:
                        time_text = await time_elem.inner_text()

                        # 检查是否是今天
                        if "今天" in time_text or datetime.now().strftime("%m-%d") in time_text:
                            sent_today.append({
                                'username': username.strip(),
                                'time': time_text.strip()
                            })
                            print(f"  {i}. {username.strip()} - {time_text.strip()}")

            except Exception as e:
                continue

        print(f"\n📈 统计结果：")
        print(f"  - 今天发送的私信数量: {len(sent_today)}")
        print(f"  - 总会话数量: {len(conversations)}")

        # 保存结果
        result = {
            'check_time': datetime.now().isoformat(),
            'sent_today_count': len(sent_today),
            'total_conversations': len(conversations),
            'sent_today_list': sent_today
        }

        with open('dm_status.json', 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print(f"\n💾 结果已保存到 dm_status.json")

        input("\n按回车键关闭浏览器...")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(check_sent_messages())
