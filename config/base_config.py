# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/config/base_config.py
# GitHub: https://github.com/NanmiCoder
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#

# 澹版槑锛氭湰浠ｇ爜浠呬緵瀛︿範鍜岀爺绌剁洰鐨勪娇鐢ㄣ€備娇鐢ㄨ€呭簲閬靛畧浠ヤ笅鍘熷垯锛?
# 1. 涓嶅緱鐢ㄤ簬浠讳綍鍟嗕笟鐢ㄩ€斻€?
# 2. 浣跨敤鏃跺簲閬靛畧鐩爣骞冲彴鐨勪娇鐢ㄦ潯娆惧拰robots.txt瑙勫垯銆?
# 3. 涓嶅緱杩涜澶ц妯＄埇鍙栨垨瀵瑰钩鍙伴€犳垚杩愯惀骞叉壈銆?
# 4. 搴斿悎鐞嗘帶鍒惰姹傞鐜囷紝閬垮厤缁欑洰鏍囧钩鍙板甫鏉ヤ笉蹇呰鐨勮礋鎷呫€?
# 5. 涓嶅緱鐢ㄤ簬浠讳綍闈炴硶鎴栦笉褰撶殑鐢ㄩ€斻€?
#
# 璇︾粏璁稿彲鏉℃璇峰弬闃呴」鐩牴鐩綍涓嬬殑LICENSE鏂囦欢銆?
# 浣跨敤鏈唬鐮佸嵆琛ㄧず鎮ㄥ悓鎰忛伒瀹堜笂杩板師鍒欏拰LICENSE涓殑鎵€鏈夋潯娆俱€?

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_RUNTIME_DIR = os.getenv("SOCIAL_CRAWLER_RUNTIME_DIR", str(_PROJECT_ROOT / "runtime"))
_DEFAULT_DATA_DIR = os.getenv("SOCIAL_CRAWLER_DATA_DIR", str(Path(_DEFAULT_RUNTIME_DIR) / "data"))
# Basic configuration
PLATFORM = "xhs"  # Platform, xhs | dy | ks | bili | wb | tieba | zhihu
KEYWORDS = "缂栫▼鍓笟,缂栫▼鍏艰亴"  # Keyword search configuration, separated by English commas

# ==================== Content Relevance Filter ====================
# Enable to filter out content that doesn't actually mention the target entities.
# Platform search is fuzzy 鈥?"涓叧鏉戜汉宸ユ櫤鑳界爺绌堕櫌" returns lots of generic AI content.
# When enabled, only content containing at least one RELEVANCE_MUST_CONTAIN keyword
# in its title or description will be saved. Comments are saved only if their parent
# content passed the filter.
ENABLE_RELEVANCE_FILTER = True

# Content MUST contain at least one of these strings (case-insensitive for English)
# to be considered relevant. These should be the core entity names you care about.
RELEVANCE_MUST_CONTAIN = [
    "ai_research_institute",
    "zhongguancun",
    "beijing_zhongguancun_college",
    "zhongguancun_ai_research_institute",
    "鏅烘簮",
    "娌冲",
    "鍒涙櫤",
    "sanxiao_ke",
    "sanxiao_zhi",
]

# Content containing ANY of these strings will be excluded, even if it passes the above filter.
# Use this to block obvious spam/ad patterns.
RELEVANCE_EXCLUDE_KEYWORDS: list[str] = [
    # Examples (uncomment or add your own):
    # "鎷涜仒", "骞垮憡", "杞彂鎶藉", "鐐硅禐閫佺鍒?,
]

# Minimum total engagement (liked_count + comment_count) for a post to be saved.
# Posts with fewer combined interactions are treated as low-quality / spam and skipped.
# Set to 0 to disable.
MIN_CONTENT_ENGAGEMENT = 0  # 涓存椂璋冩暣涓?0锛岀敤浜庢帓鏌ラ棶棰?

# Minimum character length for a comment to be saved.
# Comments shorter than this (e.g. "鍝堝搱", "666", single emoji) are skipped.
# Set to 0 to disable.
MIN_COMMENT_LENGTH = 5

# ==================== 瀹樻柟璐﹀彿鐖彇閰嶇疆 ====================
# 鏄惁鍦ㄦ瘡娆＄埇鍙栨椂棰濆鎶撳彇鎸囧畾瀹樻柟璐﹀彿鐨勫唴瀹癸紙鍦ㄥ叧閿瘝鎼滅储涔嬪悗杩愯锛?
# 瀹樻柟璐﹀彿鍐呭浼氱粫杩囩浉鍏虫€ц繃婊わ紝source_keyword 璁板綍涓?"@{璐﹀彿鍚嶇О}" 浠ュ尯鍒嗘潵婧?
ENABLE_OFFICIAL_ACCOUNTS_CRAWL = True

# 灏忕孩涔﹀畼鏂硅处鍙峰垪琛紙鐖彇鍏舵墍鏈夊笘瀛愬拰璇勮锛?
XHS_OFFICIAL_ACCOUNTS = [
    {"user_id": "5bebb72379896c00014f3295", "name": "beijing_zhongguancun_college"},
    {"user_id": "68685a82000000001d009ebb", "name": "涓婃捣鍒涙櫤瀛﹂櫌"},
]

# Bilibili 瀹樻柟璐﹀彿鍒楄〃锛堢埇鍙栧叾鎵€鏈夎棰戝拰璇勮锛?
BILI_OFFICIAL_ACCOUNTS = [
    {"uid": 85843243, "name": "beijing_zhongguancun_college"},
]

LOGIN_TYPE = "qrcode"  # qrcode or phone or cookie
COOKIES = ""
CRAWLER_TYPE = (
    "search"  # Crawling type, search (keyword search) | detail (post details) | creator (creator homepage data)
)
# Whether to enable IP proxy
ENABLE_IP_PROXY = False

# Number of proxy IP pools
IP_PROXY_POOL_COUNT = 2

# Proxy IP provider name
IP_PROXY_PROVIDER_NAME = "kuaidaili"  # kuaidaili | wandouhttp

# Setting to True will not open the browser (headless browser)
# Setting False will open a browser
# If Xiaohongshu keeps scanning the code to log in but fails, open the browser and manually pass the sliding verification code.
# If Douyin keeps prompting failure, open the browser and see if mobile phone number verification appears after scanning the QR code to log in. If it does, manually go through it and try again.
HEADLESS = False

# Whether to save login status
SAVE_LOGIN_STATE = True

# ==================== CDP (Chrome DevTools Protocol) Configuration ====================
# Whether to enable CDP mode - use the user's existing Chrome/Edge browser to crawl, providing better anti-detection capabilities
# Once enabled, the user's Chrome/Edge browser will be automatically detected and started, and controlled through the CDP protocol.
# This method uses the real browser environment, including the user's extensions, cookies and settings, greatly reducing the risk of detection.
CDP_DEBUG_PORT = 9222

# Remote CDP WebSocket URL (optional)
# When set, skip launching a local Chrome and connect directly to a remote browser
# service (e.g. a hosted browserless / browsergrid endpoint). Takes precedence over
# the local CDP launch flow; ENABLE_CDP_MODE is implied.
# Example: wss://browser.example.com/ws/sessions/<id>/cdp/devtools/browser/<browser-id>?token=...
CDP_REMOTE_WS_URL = os.getenv("CDP_REMOTE_WS_URL", "")

# Automatically enable CDP mode when a remote URL is configured
ENABLE_CDP_MODE = bool(CDP_REMOTE_WS_URL)

# Optional HTTP headers sent during the CDP WebSocket handshake (dict).
# Use for remote services that require an Authorization header rather than a query
# string token. Leave empty when the token is embedded in CDP_REMOTE_WS_URL.
CDP_REMOTE_HEADERS: dict[str, str] = {}

# Custom browser path (optional)
# If it is empty, the system will automatically detect the installation path of Chrome/Edge
# Windows example: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
# macOS example: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
CUSTOM_BROWSER_PATH = ""

# Whether to enable headless mode in CDP mode
# NOTE: Even if set to True, some anti-detection features may not work well in headless mode
CDP_HEADLESS = False

# Browser startup timeout (seconds)
BROWSER_LAUNCH_TIMEOUT = 60

# Whether to automatically close the browser when the program ends
# Set to False to keep the browser running, preserving cookies and login state across runs
AUTO_CLOSE_BROWSER = False

# Data saving type option configuration. It is best to save to DB, with deduplication function.
# Supported: json | csv | excel | sqlite | db | postgres | mongodb | supabase
# Default to local JSON storage for safer out-of-box usage.
SAVE_DATA_OPTION = "json"  # json or csv or excel or sqlite or db or postgres or mongodb or supabase

# Data saving path, if not specified by default, it will be saved to the data folder.
SAVE_DATA_PATH = _DEFAULT_DATA_DIR

# Browser file configuration cached by the user's browser
USER_DATA_DIR = "%s_user_data_dir"  # %s will be replaced by platform name

# The number of pages to start crawling starts from the first page by default
START_PAGE = 1

# Control the number of crawled videos/posts per keyword per run
# Note: relevance filter will further reduce this to only matching posts
CRAWLER_MAX_NOTES_COUNT = 30

# Controlling the number of concurrent crawlers (1 = safest, looks most human-like)
MAX_CONCURRENCY_NUM = 1

# Whether to enable crawling media mode (including image or video resources), crawling media is not enabled by default
ENABLE_GET_MEIDAS = False

# Whether to enable comment crawling mode. Comment crawling is enabled by default.
ENABLE_GET_COMMENTS = True

# Control the number of crawled first-level comments (single video/post)
CRAWLER_MAX_COMMENTS_COUNT_SINGLENOTES = 20

# Whether to enable the mode of crawling second-level comments (replies).
# Enabled 鈥?captures full discussion threads for richer opinion mining data.
ENABLE_GET_SUB_COMMENTS = True

# word cloud related
# Whether to enable generating comment word clouds
ENABLE_GET_WORDCLOUD = False
# Custom words and their groups
# Add rule: xx:yy where xx is a custom-added phrase, and yy is the group name to which the phrase xx is assigned.
CUSTOM_WORDS = {
    "闆跺嚑": "骞翠唤",  # Recognize "zero points" as a whole
    "gaopin_ci": "zhuanye_shuyu",  # Example custom words
}

# Deactivate (disabled) word file path
STOP_WORDS_FILE = str(_PROJECT_ROOT / "docs" / "hit_stopwords.txt")

# Chinese font file path
FONT_PATH = str(_PROJECT_ROOT / "docs" / "STZHONGS.TTF")

# Crawl interval (seconds) 鈥?random sleep between requests
# Higher = safer. Recommended: 3-5 for normal use, 5-10 if you've been warned
CRAWLER_MAX_SLEEP_SEC = 5

from .bilibili_config import *
from .xhs_config import *
from .dy_config import *
from .ks_config import *
from .weibo_config import *
from .tieba_config import *
from .zhihu_config import *
from .vibe_coding_config import *

