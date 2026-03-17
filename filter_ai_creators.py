#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
过滤非AI/非OpenClaw噪音博主
"""

import csv
from datetime import datetime

# 噪音关键词 - 视频标题包含这些词且与AI无关的要过滤
NOISE_VIDEO_KEYWORDS = [
    "小龙虾我先吃", "小龙虾吃", "吃小龙虾", "麻辣小龙虾", "清炒小龙虾",
    "今夏第一顿", "口味虾", "龙虾肉质",  # 美食
    "选股小龙虾版", "Z哥选股", "炒股Python",  # 纯股票
    "原神日常",  # 游戏
    "福特号起火", "中东战事",  # 军事时政
    "Comfyui.*wan2", "SD整合包.*大尺度",  # SD无关内容
]

# 噪音博主ID（手动确认的）
NOISE_CREATOR_IDS = {
    "1244310984",      # 温油辣辣U - 美食（真小龙虾）
    "479503119",       # 欧妹呀 - 美食（真小龙虾）
    "3546977568557453", # 秋枼SD整合包 - SD/ComfyUI非OpenClaw
    "3546851764603794", # z哥直播切片小能手 - 股票直播
    "34528864",        # JeffreyZZ331 - Python选股
    "385941246",       # 川卤宗师 - 无视频
}


def is_noise_by_video(video_title: str) -> bool:
    """根据视频标题判断是否为噪音"""
    import re
    title_lower = video_title.lower()
    for kw in NOISE_VIDEO_KEYWORDS:
        if re.search(kw, video_title):
            return True
    return False


def filter_creators(input_file: str):
    rows = []
    with open(input_file, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            rows.append(row)

    filtered = []
    removed = []

    for row in rows:
        creator_id = row["博主ID"]
        name = row["博主名称"]
        v1 = row.get("代表视频1", "")
        v2 = row.get("代表视频2", "")
        v3 = row.get("代表视频3", "")
        total_play = int(row["总播放量"]) if row["总播放量"] else 0

        # 规则1: 手动确认的噪音博主
        if creator_id in NOISE_CREATOR_IDS:
            removed.append((name, "手动标记噪音", v1[:40]))
            continue

        # 规则2: 无任何视频的博主
        if not v1.strip() and not v2.strip() and not v3.strip():
            removed.append((name, "无视频数据", ""))
            continue

        # 规则3: 视频标题都不含AI/OpenClaw相关内容
        all_videos = " ".join([v1, v2, v3])
        ai_keywords = [
            "openclaw", "openclaws", "小龙虾", "龙虾", "养虾", "clawdbot", "agent",
            "skill", "mcp", "ai", "人工智能", "大模型", "token", "部署",
            "llm", "gpt", "claude", "gemini", "qwen", "qclaw", "workbuddy"
        ]
        has_ai_content = any(kw in all_videos.lower() for kw in ai_keywords)
        if not has_ai_content:
            removed.append((name, "视频内容与AI无关", v1[:40]))
            continue

        filtered.append(row)

    # 输出结果
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"openclaw_creators_filtered_{timestamp}.csv"

    with open(output_file, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(filtered)

    print(f"✅ 过滤完成！")
    print(f"📁 输出文件: {output_file}")
    print(f"👥 保留博主: {len(filtered)} 个")
    print(f"🗑  移除博主: {len(removed)} 个")
    print(f"\n🗑  被移除的博主：")
    for name, reason, video in removed:
        print(f"  - {name:<22} [{reason}]  {video}")


if __name__ == "__main__":
    import sys
    input_file = sys.argv[1] if len(sys.argv) > 1 else \
        "/Users/sunminghao/Desktop/MediaCrawler/openclaw_creators.csv"
    filter_creators(input_file)
