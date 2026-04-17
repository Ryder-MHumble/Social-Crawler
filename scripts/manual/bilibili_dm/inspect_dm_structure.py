#!/usr/bin/env python3
"""
测试脚本 - 检查 B站私信界面的实际结构
"""

import asyncio
from playwright.async_api import async_playwright

async def test_bilibili_dm():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=[
                '--start-maximized',
                '--disable-blink-features=AutomationControlled',
            ]
        )

        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        )

        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            window.chrome = { runtime: {} };
        """)

        page = await context.new_page()

        # 访问一个测试博主的主页
        test_user_id = "4401694"  # 林亦LYi
        print(f"访问测试博主主页: {test_user_id}")
        await page.goto(f"https://space.bilibili.com/{test_user_id}")

        print("\n等待页面加载...")
        await page.wait_for_timeout(3000)

        print("\n请手动点击'发消息'按钮，然后等待...")
        print("我会在30秒后截图并打印页面结构\n")

        await page.wait_for_timeout(30000)

        # 截图
        await page.screenshot(path="bilibili_dm_page.png")
        print("✅ 已保存截图: bilibili_dm_page.png")

        # 打印页面 HTML
        html = await page.content()
        with open("bilibili_dm_page.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("✅ 已保存页面HTML: bilibili_dm_page.html")

        # 尝试查找所有可能的输入框
        print("\n🔍 查找所有输入框...")

        # 查找所有 textarea
        textareas = await page.query_selector_all("textarea")
        print(f"找到 {len(textareas)} 个 textarea 元素")
        for i, ta in enumerate(textareas):
            placeholder = await ta.get_attribute("placeholder")
            class_name = await ta.get_attribute("class")
            print(f"  [{i+1}] placeholder='{placeholder}', class='{class_name}'")

        # 查找所有 input
        inputs = await page.query_selector_all("input[type='text']")
        print(f"\n找到 {len(inputs)} 个 input[type='text'] 元素")
        for i, inp in enumerate(inputs):
            placeholder = await inp.get_attribute("placeholder")
            class_name = await inp.get_attribute("class")
            print(f"  [{i+1}] placeholder='{placeholder}', class='{class_name}'")

        # 查找所有 contenteditable
        editables = await page.query_selector_all("[contenteditable='true']")
        print(f"\n找到 {len(editables)} 个 contenteditable 元素")
        for i, ed in enumerate(editables):
            class_name = await ed.get_attribute("class")
            print(f"  [{i+1}] class='{class_name}'")

        print("\n按 Ctrl+C 退出...")
        await page.wait_for_timeout(300000)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_bilibili_dm())
