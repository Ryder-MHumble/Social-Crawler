#!/usr/bin/env python3
"""
B站自动发送私信脚本（并发版本 - 简化登录 + 数据库记录）
手动确认登录后按回车继续
"""

import csv
import asyncio
from playwright.async_api import async_playwright, BrowserContext
import logging
from typing import List, Dict
from dm_record_store import DMRecordStore

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(message)s'
)
logger = logging.getLogger(__name__)

# 初始化数据库存储
try:
    db_store = DMRecordStore()
    logger.info("✅ 数据库连接成功")
except Exception as e:
    logger.warning(f"⚠️  数据库连接失败: {e}，将不记录到数据库")
    db_store = None

# 并发配置
CONCURRENT_TABS = 5  # 同时打开的标签页数量

# 私信文案（精简版，250字以内）
MESSAGE_TEMPLATE = """hihi你好呀，抱歉打扰啦，我是北京中关村学院的研究员，看到你主页分享了很多Openclaw的落地应用，想邀请你参加我们举办的龙虾大赛

中关村学院"OpenClaw"比赛🎯分学术/生产力/生活龙虾三条赛道，全场最佳奖金20万+100亿Token，每条赛道10个获奖名额，截止3月19日23:59

报名很简单：上传链接讲清楚你的虾能做什么即可，不用交代码，核心看实际应用效果，结合硬件会加分

报名：https://claw.lab.bza.edu.cn
详情：https://mp.weixin.qq.com/s/RfqXfunmEP1NLIln-9YUvQ"""


async def send_dm_to_user(context: BrowserContext, user_id: str, username: str, message: str, tab_id: int) -> bool:
    """给指定用户发送私信"""
    page = None

    # 检查是否已经发送过
    if db_store and db_store.is_already_sent(user_id):
        logger.info(f"[Tab{tab_id}] ⏭️  {username} 已发送过，跳过")
        return True

    try:
        page = await context.new_page()

        # 直接访问私信页面
        dm_url = f"https://message.bilibili.com/#/whisper/mid{user_id}"
        logger.info(f"[Tab{tab_id}] 正在访问 {username} 的私信页面")

        await page.goto(dm_url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)

        # 查找输入框 - 私信页面的选择器
        textarea = None
        textarea_selectors = [
            'textarea.textarea',
            'textarea[placeholder*="消息"]',
            'textarea[placeholder*="发送"]',
            '.input-area textarea',
            '#chat-textarea',
            'div[contenteditable="true"]',
            '.ql-editor'
        ]

        for selector in textarea_selectors:
            try:
                textarea = await page.wait_for_selector(selector, timeout=3000)
                if textarea:
                    logger.info(f"[Tab{tab_id}] ✅ 找到输入框: {selector}")
                    break
            except:
                continue

        if not textarea:
            logger.warning(f"[Tab{tab_id}] ⚠️  {username} 未找到输入框")
            return False

        # 输入消息
        await textarea.click()
        await page.wait_for_timeout(500)

        # 对于 contenteditable，使用 type 而不是 fill
        if 'contenteditable' in str(await textarea.get_attribute('contenteditable')):
            await page.keyboard.type(message)
        else:
            await textarea.fill(message)

        await page.wait_for_timeout(1500)

        # 查找发送按钮 - 扩展选择器列表
        send_btn = None
        send_btn_selectors = [
            'button:has-text("发送")',
            'button:has-text("Send")',
            '.send-btn',
            'button[class*="send"]',
            'button[class*="Send"]',
            '.btn-send',
            'button.button',
            'div[class*="send-btn"]',
            'a[class*="send"]',
            # B站私信页面可能的选择器
            '.chat-input button',
            '.input-wrap button',
            'button[type="button"]',
        ]

        for selector in send_btn_selectors:
            try:
                send_btn = await page.wait_for_selector(selector, timeout=2000)
                if send_btn:
                    # 检查按钮是否可见
                    is_visible = await send_btn.is_visible()
                    if is_visible:
                        logger.info(f"[Tab{tab_id}] ✅ 找到发送按钮: {selector}")
                        break
            except:
                continue

        if not send_btn:
            # 尝试使用回车键发送
            logger.info(f"[Tab{tab_id}] ⚠️  未找到发送按钮，尝试使用回车键发送")
            await page.keyboard.press('Enter')
            await page.wait_for_timeout(2000)
            logger.info(f"[Tab{tab_id}] ✅ 已按回车键发送")
        else:
            await send_btn.click()
            await page.wait_for_timeout(2000)

        logger.info(f"[Tab{tab_id}] ✅ 成功向 {username} 发送私信")

        # 保存到数据库
        if db_store:
            db_store.save_dm_record(user_id, username, message, "success")

        return True

    except Exception as e:
        error_msg = str(e)
        logger.error(f"[Tab{tab_id}] ❌ {username} 发送失败: {error_msg}")

        # 保存失败记录到数据库
        if db_store:
            db_store.save_dm_record(user_id, username, message, "failed", error_msg)

        return False
    finally:
        if page:
            try:
                await page.close()
            except:
                pass


async def send_dm_batch(context: BrowserContext, creators_batch: List[Dict], batch_num: int) -> tuple:
    """并发发送一批私信"""
    tasks = []
    for i, creator in enumerate(creators_batch):
        task = send_dm_to_user(
            context,
            creator['user_id'],
            creator['username'],
            MESSAGE_TEMPLATE,
            tab_id=i + 1
        )
        tasks.append(task)

    results = await asyncio.gather(*tasks)
    success_count = sum(1 for r in results if r)
    fail_count = len(results) - success_count

    logger.info(f"\n{'='*50}")
    logger.info(f"批次 {batch_num} 完成: ✅ {success_count}/{len(creators_batch)}, ❌ {fail_count}/{len(creators_batch)}")
    logger.info(f"{'='*50}\n")

    return success_count, fail_count


async def main():
    """主函数"""
    csv_file = "../openclaw_creators.csv"
    creators = []

    try:
        with open(csv_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                creators.append({
                    'user_id': row['博主ID'],
                    'username': row['博主名称']
                })
    except Exception as e:
        logger.error(f"读取 CSV 文件失败: {str(e)}")
        return

    logger.info(f"共读取到 {len(creators)} 位博主")
    logger.info(f"并发配置: 每批 {CONCURRENT_TABS} 个标签页同时发送\n")

    async with async_playwright() as p:
        # 使用更隐蔽的浏览器配置，绕过自动化检测
        browser = await p.chromium.launch(
            headless=False,
            args=[
                '--start-maximized',
                '--disable-blink-features=AutomationControlled',  # 禁用自动化控制特征
            ]
        )

        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            # 添加额外的浏览器特征
            extra_http_headers={
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            }
        )

        # 注入脚本隐藏 webdriver 特征
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });

            // 覆盖 Chrome 对象
            window.chrome = {
                runtime: {}
            };

            // 覆盖 permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        """)

        login_page = await context.new_page()

        logger.info("🌐 正在打开 B站...")
        await login_page.goto("https://www.bilibili.com", wait_until="domcontentloaded")

        logger.info("\n" + "="*60)
        logger.info("⚠️  请在浏览器中完成登录")
        logger.info("登录完成后，回到终端按回车键继续...")
        logger.info("="*60 + "\n")

        # 等待用户按回车
        input("按回车键继续...")

        logger.info("✅ 开始发送私信！\n")
        await login_page.close()

        total_success = 0
        total_fail = 0
        total_batches = (len(creators) + CONCURRENT_TABS - 1) // CONCURRENT_TABS

        for batch_idx in range(0, len(creators), CONCURRENT_TABS):
            batch_num = batch_idx // CONCURRENT_TABS + 1
            creators_batch = creators[batch_idx:batch_idx + CONCURRENT_TABS]

            logger.info(f"\n{'='*50}")
            logger.info(f"📦 批次 {batch_num}/{total_batches}")
            logger.info(f"本批次: {', '.join([c['username'] for c in creators_batch])}")
            logger.info(f"{'='*50}\n")

            success, fail = await send_dm_batch(context, creators_batch, batch_num)
            total_success += success
            total_fail += fail

            if batch_idx + CONCURRENT_TABS < len(creators):
                delay = 10
                logger.info(f"⏳ 等待 {delay} 秒后继续下一批次...\n")
                await asyncio.sleep(delay)

        logger.info(f"\n{'='*60}")
        logger.info(f"🎉 全部发送完成！")
        logger.info(f"{'='*60}")
        logger.info(f"✅ 成功: {total_success} 位")
        logger.info(f"❌ 失败: {total_fail} 位")
        logger.info(f"📊 总计: {len(creators)} 位")
        logger.info(f"📈 成功率: {total_success/len(creators)*100:.1f}%")
        logger.info(f"{'='*60}\n")

        logger.info("浏览器将保持打开30秒，方便查看结果...")
        await asyncio.sleep(30)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
