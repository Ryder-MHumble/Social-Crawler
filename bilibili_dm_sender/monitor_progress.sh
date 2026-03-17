#!/bin/bash
# 实时监控私信发送进度

echo "🔍 监控 B站私信发送进度..."
echo "按 Ctrl+C 退出监控"
echo ""

while true; do
    clear
    echo "======================================"
    echo "📊 B站私信发送进度监控"
    echo "======================================"
    echo ""

    # 显示最新日志
    tail -30 /private/tmp/claude-501/-Users-sunminghao-Desktop-MediaCrawler/d0218260-a33d-4cea-975d-d8f1f330b4ac/tasks/btx3kbfa7.output

    echo ""
    echo "======================================"
    echo "⏰ $(date '+%Y-%m-%d %H:%M:%S')"
    echo "======================================"

    sleep 3
done
