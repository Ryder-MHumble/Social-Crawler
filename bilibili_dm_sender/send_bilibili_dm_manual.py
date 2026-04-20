#!/usr/bin/env python3
"""
B站自动发送私信脚本（并发版本 - 简化登录 + 数据库记录）
手动确认登录后按回车继续
"""

import argparse
import csv
import asyncio
import os
import sys
from pathlib import Path
from playwright.async_api import async_playwright, BrowserContext
import logging
from typing import List, Dict

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools import runtime_paths

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(message)s'
)
logger = logging.getLogger(__name__)

# 初始化数据库存储
try:
    from dm_record_store import DMRecordStore

    db_store = DMRecordStore()
    logger.info("✅ 数据库连接成功")
except Exception as e:
    logger.warning(f"⚠️  数据库连接失败: {e}，将不记录到数据库")
    db_store = None

# 并发配置
CONCURRENT_TABS = 5  # 同时打开的标签页数量
DEFAULT_BATCH_DELAY_SECONDS = 10
DEFAULT_CAMPAIGN_ID = "openclaw_2026"

# 私信文案（精简版，250字以内）
MESSAGE_TEMPLATE = """hihi你好呀，抱歉打扰啦，我是北京中关村学院的研究员，看到你主页分享了很多Openclaw的落地应用，想邀请你参加我们举办的龙虾大赛

中关村学院"OpenClaw"比赛🎯分学术/生产力/生活龙虾三条赛道，全场最佳奖金20万+100亿Token，每条赛道10个获奖名额，截止3月19日23:59

报名很简单：上传链接讲清楚你的虾能做什么即可，不用交代码，核心看实际应用效果，结合硬件会加分

报名：https://claw.lab.bza.edu.cn
详情：https://mp.weixin.qq.com/s/RfqXfunmEP1NLIln-9YUvQ"""


def _parse_bool(raw: str | None, default: bool = False) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _parse_int(raw: str | None, default: int, *, minimum: int | None = None) -> int:
    try:
        value = int(raw) if raw is not None else default
    except (TypeError, ValueError):
        value = default
    if minimum is not None:
        return max(minimum, value)
    return value


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bilibili outreach DM sender")
    parser.add_argument("--csv-file", default=os.getenv("BILI_DM_CSV_FILE", "").strip())
    parser.add_argument("--message", default=os.getenv("BILI_DM_MESSAGE", "").strip())
    parser.add_argument("--message-file", default=os.getenv("BILI_DM_MESSAGE_FILE", "").strip())
    parser.add_argument("--campaign-id", default=os.getenv("BILI_DM_CAMPAIGN_ID", DEFAULT_CAMPAIGN_ID))
    parser.add_argument(
        "--message-template-id",
        default=os.getenv("BILI_DM_MESSAGE_TEMPLATE_ID", "").strip(),
    )
    parser.add_argument(
        "--concurrent-tabs",
        type=int,
        default=_parse_int(os.getenv("BILI_DM_CONCURRENT_TABS"), CONCURRENT_TABS, minimum=1),
    )
    parser.add_argument(
        "--batch-delay-seconds",
        type=int,
        default=_parse_int(
            os.getenv("BILI_DM_BATCH_DELAY_SECONDS"),
            DEFAULT_BATCH_DELAY_SECONDS,
            minimum=0,
        ),
    )
    parser.add_argument(
        "--max-targets",
        type=int,
        default=_parse_int(os.getenv("BILI_DM_MAX_TARGETS"), 0, minimum=0),
        help="Limit the number of creators loaded from CSV. 0 means unlimited.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=_parse_bool(os.getenv("BILI_DM_DRY_RUN"), default=False),
        help="Do not send messages. Only print the resolved campaign plan.",
    )
    return parser.parse_args()


def _resolve_message(args: argparse.Namespace) -> str:
    if args.message_file:
        path = Path(args.message_file).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"Message file not found: {path}")
        return path.read_text(encoding="utf-8").strip()
    if args.message:
        return args.message.strip()
    return MESSAGE_TEMPLATE.strip()


def _resolve_csv_file(args: argparse.Namespace) -> Path | None:
    if args.csv_file:
        candidate = Path(args.csv_file).expanduser()
        return candidate if candidate.exists() else None
    runtime_paths.ensure_runtime_layout()
    runtime_paths.seed_openclaw_csv_from_legacy()
    csv_candidates = [
        runtime_paths.get_openclaw_csv_path(),
        runtime_paths.get_legacy_openclaw_csv_path(),
    ]
    return next((path for path in csv_candidates if path.exists()), None)


async def send_dm_to_user(
    context: BrowserContext,
    user_id: str,
    username: str,
    message: str,
    tab_id: int,
    *,
    campaign_id: str,
    message_template_id: str,
    dry_run: bool,
) -> bool:
    """给指定用户发送私信"""
    page = None

    # 检查是否已经发送过
    if db_store and db_store.is_already_sent(user_id, campaign=campaign_id):
        logger.info(f"[Tab{tab_id}] ⏭️  {username} 已发送过，跳过")
        return True

    if dry_run:
        logger.info(f"[Tab{tab_id}] [DRY-RUN] 将向 {username}({user_id}) 发送私信")
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
            db_store.save_dm_record(
                user_id,
                username,
                message,
                "success",
                campaign=campaign_id,
                message_template_id=message_template_id,
            )

        return True

    except Exception as e:
        error_msg = str(e)
        logger.error(f"[Tab{tab_id}] ❌ {username} 发送失败: {error_msg}")

        # 保存失败记录到数据库
        if db_store:
            db_store.save_dm_record(
                user_id,
                username,
                message,
                "failed",
                error_msg,
                campaign=campaign_id,
                message_template_id=message_template_id,
            )

        return False
    finally:
        if page:
            try:
                await page.close()
            except:
                pass


async def send_dm_batch(
    context: BrowserContext,
    creators_batch: List[Dict],
    batch_num: int,
    *,
    message: str,
    campaign_id: str,
    message_template_id: str,
    dry_run: bool,
) -> tuple:
    """并发发送一批私信"""
    tasks = []
    for i, creator in enumerate(creators_batch):
        task = send_dm_to_user(
            context,
            creator['user_id'],
            creator['username'],
            message,
            tab_id=i + 1,
            campaign_id=campaign_id,
            message_template_id=message_template_id,
            dry_run=dry_run,
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
    args = _parse_args()
    csv_file = _resolve_csv_file(args)
    if not csv_file:
        logger.error("CSV file not found in runtime/input or repository root.")
        return
    try:
        message_template = _resolve_message(args)
    except Exception as exc:
        logger.error(f"读取私信模板失败: {exc}")
        return
    campaign_id = (args.campaign_id or DEFAULT_CAMPAIGN_ID).strip() or DEFAULT_CAMPAIGN_ID
    concurrent_tabs = max(1, args.concurrent_tabs)
    batch_delay_seconds = max(0, args.batch_delay_seconds)
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

    if args.max_targets > 0:
        creators = creators[:args.max_targets]

    logger.info(f"共读取到 {len(creators)} 位博主")
    logger.info(f"Campaign: {campaign_id}")
    logger.info(f"并发配置: 每批 {concurrent_tabs} 个标签页同时发送")
    logger.info(f"批次间隔: {batch_delay_seconds} 秒")
    logger.info(f"Dry-run: {'是' if args.dry_run else '否'}\n")

    if not creators:
        logger.warning("没有可发送的博主数据")
        return

    async with async_playwright() as p:
        # 使用更隐蔽的浏览器配置，绕过自动化检测
        browser = await p.chromium.launch(
            headless=bool(args.dry_run),
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

        if not args.dry_run:
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
        else:
            logger.info("🧪 Dry-run 模式，不要求人工登录。")
            await login_page.close()

        total_success = 0
        total_fail = 0
        total_batches = (len(creators) + concurrent_tabs - 1) // concurrent_tabs

        for batch_idx in range(0, len(creators), concurrent_tabs):
            batch_num = batch_idx // concurrent_tabs + 1
            creators_batch = creators[batch_idx:batch_idx + concurrent_tabs]

            logger.info(f"\n{'='*50}")
            logger.info(f"📦 批次 {batch_num}/{total_batches}")
            logger.info(f"本批次: {', '.join([c['username'] for c in creators_batch])}")
            logger.info(f"{'='*50}\n")

            success, fail = await send_dm_batch(
                context,
                creators_batch,
                batch_num,
                message=message_template,
                campaign_id=campaign_id,
                message_template_id=args.message_template_id,
                dry_run=args.dry_run,
            )
            total_success += success
            total_fail += fail

            if batch_idx + concurrent_tabs < len(creators):
                logger.info(f"⏳ 等待 {batch_delay_seconds} 秒后继续下一批次...\n")
                await asyncio.sleep(batch_delay_seconds)

        logger.info(f"\n{'='*60}")
        logger.info(f"🎉 全部发送完成！")
        logger.info(f"{'='*60}")
        logger.info(f"✅ 成功: {total_success} 位")
        logger.info(f"❌ 失败: {total_fail} 位")
        logger.info(f"📊 总计: {len(creators)} 位")
        logger.info(f"📈 成功率: {total_success/len(creators)*100:.1f}%")
        logger.info(f"{'='*60}\n")

        if not args.dry_run:
            logger.info("浏览器将保持打开30秒，方便查看结果...")
            await asyncio.sleep(30)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
