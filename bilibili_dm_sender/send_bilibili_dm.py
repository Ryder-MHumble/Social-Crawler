#!/usr/bin/env python3
"""
B站自动发送私信脚本（并发版本）
使用 Playwright 浏览器自动化给 openclaw_creators.csv 中的博主发送私信
支持多标签页并发发送，提高效率
"""

import csv
import time
import asyncio
from playwright.async_api import async_playwright, Page, BrowserContext
import logging
from typing import List, Dict

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(message)s'
)
logger = logging.getLogger(__name__)

# 并发配置
CONCURRENT_TABS = 5  # 同时打开的标签页数量（建议3-5个）

# 私信文案
MESSAGE_TEMPLATE = """hihi你好呀，抱歉打扰啦，我是北京中关村学院的研究员，看到你主页分享了很多Openclaw的落地应用，想邀请你参加我们举办的龙虾大赛，基本信息如下：
中关村学院正在办的"OpenClaw"比赛🎯，分学术龙虾、生产力龙虾和生活龙虾三条赛道，核心是看谁的"虾"解决实际问题能力更强。全场最佳奖金20万+100亿Token，每条赛道还各有10个获奖名额

报名也很简单：上传个链接讲清楚你的虾能做什么就行，不用交代码，核心看实际应用效果，如果结合硬件会额外加分
报名链接：https://claw.lab.bza.edu.cn
报名截止时间为：3月19日
详细信息可以看这条连接：https://mp.weixin.qq.com/s/RfqXfunmEP1NLIln-9YUvQ"""


async def send_dm_to_user(context: BrowserContext, user_id: str, username: str, message: str, tab_id: int) -> bool:
    """
    给指定用户发送私信（使用独立标签页）

    Args:
        context: Playwright BrowserContext 对象
        user_id: B站用户ID
        username: 用户名（用于日志）
        message: 私信内容
        tab_id: 标签页ID（用于日志标识）

    Returns:
        bool: 是否发送成功
    """
    page = None
    try:
        # 创建新标签页
        page = await context.new_page()

        # 访问用户主页
        user_url = f"https://space.bilibili.com/{user_id}"
        logger.info(f"[Tab{tab_id}] 正在访问 {username} 的主页: {user_url}")
        await page.goto(user_url, wait_until="domcontentloaded", timeout=30000)

        # 等待页面加载
        await page.wait_for_timeout(2000)

        # 查找并点击"发消息"按钮
        send_msg_selectors = [
            'button:has-text("发消息")',
            'a:has-text("发消息")',
            '.send-msg',
            'a.n-btn:has-text("发消息")'
        ]

        send_button = None
        for selector in send_msg_selectors:
            try:
                send_button = await page.wait_for_selector(selector, timeout=3000)
                if send_button:
                    break
            except:
                continue

        if not send_button:
            logger.warning(f"[Tab{tab_id}] ⚠️  未找到 {username} 的发消息按钮，可能该用户关闭了私信功能")
            return False

        # 点击发消息按钮
        await send_button.click()
        await page.wait_for_timeout(2000)

        # 查找消息输入框
        textarea_selectors = [
            'textarea[placeholder*="消息"]',
            'textarea[placeholder*="发送"]',
            '.chat-input textarea',
            'textarea.textarea',
            '[contenteditable="true"]'
        ]

        textarea = None
        for selector in textarea_selectors:
            try:
                textarea = await page.wait_for_selector(selector, timeout=3000)
                if textarea:
                    break
            except:
                continue

        if not textarea:
            logger.warning(f"[Tab{tab_id}] ⚠️  未找到 {username} 的消息输入框")
            return False

        # 输入消息
        await textarea.fill(message)
        await page.wait_for_timeout(1000)

        # 查找并点击发送按钮
        send_btn_selectors = [
            'button:has-text("发送")',
            '.send-btn',
            'button[class*="send"]',
            '.btn-send'
        ]

        send_btn = None
        for selector in send_btn_selectors:
            try:
                send_btn = await page.wait_for_selector(selector, timeout=3000)
                if send_btn:
                    break
            except:
                continue

        if not send_btn:
            logger.warning(f"[Tab{tab_id}] ⚠️  未找到 {username} 的发送按钮")
            return False

        # 点击发送
        await send_btn.click()
        await page.wait_for_timeout(2000)

        logger.info(f"[Tab{tab_id}] ✅ 成功向 {username} (ID: {user_id}) 发送私信")
        return True

    except Exception as e:
        logger.error(f"[Tab{tab_id}] ❌ 向 {username} (ID: {user_id}) 发送私信失败: {str(e)}")
        return False

    finally:
        # 关闭标签页
        if page:
            try:
                await page.close()
            except:
                pass


async def send_dm_batch(context: BrowserContext, creators_batch: List[Dict], batch_num: int) -> tuple:
    """
    并发发送一批私信

    Args:
        context: BrowserContext 对象
        creators_batch: 博主列表
        batch_num: 批次编号

    Returns:
        tuple: (成功数量, 失败数量)
    """
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

    # 并发执行所有任务
    results = await asyncio.gather(*tasks)

    success_count = sum(1 for r in results if r)
    fail_count = len(results) - success_count

    logger.info(f"\n{'='*50}")
    logger.info(f"批次 {batch_num} 完成: 成功 {success_count}/{len(creators_batch)}, 失败 {fail_count}/{len(creators_batch)}")
    logger.info(f"{'='*50}\n")

    return success_count, fail_count


async def main():
    """主函数"""
    # 读取 CSV 文件
    csv_file = "/Users/sunminghao/Desktop/MediaCrawler/openclaw_creators.csv"
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
    logger.info(f"并发配置: 每批 {CONCURRENT_TABS} 个标签页同时发送")

    # 启动浏览器
    async with async_playwright() as p:
        # 使用有头模式，方便手动登录
        browser = await p.chromium.launch(
            headless=False,
            args=['--start-maximized']
        )

        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        )

        # 创建一个页面用于登录
        login_page = await context.new_page()

        # 先访问 B站首页，等待用户登录
        logger.info("正在打开 B站，请手动登录...")
        await login_page.goto("https://www.bilibili.com", wait_until="domcontentloaded")

        # 等待用户登录（检查是否有用户头像或用户信息）
        logger.info("等待登录完成，请在浏览器中完成登录操作...")
        logger.info("⏰ 登录超时时间: 5 分钟")

        login_success = False
        login_selectors = [
            '.header-avatar-wrap',  # 头像
            '.header-entry-mini',   # 用户信息
            '.bili-avatar-img',     # 头像图片
            'img[class*="avatar"]', # 任何头像
            '.user-con'             # 用户容器
        ]

        for selector in login_selectors:
            try:
                await login_page.wait_for_selector(selector, timeout=300000)  # 5分钟
                login_success = True
                logger.info(f"✅ 登录成功！（检测到: {selector}）")
                break
            except:
                continue

        if not login_success:
            logger.error("❌ 登录超时（5分钟），请重新运行脚本")
            await browser.close()
            return

        # 关闭登录页面
        await login_page.close()

        # 统计
        total_success = 0
        total_fail = 0

        # 分批处理
        total_batches = (len(creators) + CONCURRENT_TABS - 1) // CONCURRENT_TABS
        logger.info(f"\n开始发送私信，共 {total_batches} 批次\n")

        for batch_idx in range(0, len(creators), CONCURRENT_TABS):
            batch_num = batch_idx // CONCURRENT_TABS + 1
            creators_batch = creators[batch_idx:batch_idx + CONCURRENT_TABS]

            logger.info(f"\n{'='*50}")
            logger.info(f"开始处理批次 {batch_num}/{total_batches}")
            logger.info(f"本批次博主: {', '.join([c['username'] for c in creators_batch])}")
            logger.info(f"{'='*50}\n")

            # 并发发送本批次
            success, fail = await send_dm_batch(context, creators_batch, batch_num)
            total_success += success
            total_fail += fail

            # 批次间延迟
            if batch_idx + CONCURRENT_TABS < len(creators):
                delay = 10  # 批次间延迟10秒
                logger.info(f"等待 {delay} 秒后继续下一批次...\n")
                await asyncio.sleep(delay)

        # 输出最终统计结果
        logger.info(f"\n{'='*60}")
        logger.info(f"🎉 全部发送完成！")
        logger.info(f"{'='*60}")
        logger.info(f"✅ 成功: {total_success} 位")
        logger.info(f"❌ 失败: {total_fail} 位")
        logger.info(f"📊 总计: {len(creators)} 位")
        logger.info(f"📈 成功率: {total_success/len(creators)*100:.1f}%")
        logger.info(f"{'='*60}\n")

        # 保持浏览器打开，方便查看结果
        logger.info("浏览器将保持打开状态，按 Ctrl+C 退出...")
        try:
            await asyncio.sleep(300)  # 等待5分钟
        except KeyboardInterrupt:
            logger.info("用户中断，正在关闭浏览器...")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
