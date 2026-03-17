#!/usr/bin/env python3
"""
实时监控 B站私信发送进度
"""
import time
import os

output_file = "/private/tmp/claude-501/-Users-sunminghao-Desktop-MediaCrawler/d0218260-a33d-4cea-975d-d8f1f330b4ac/tasks/bcuz5dhh0.output"

print("🔍 实时监控 B站私信发送进度")
print("按 Ctrl+C 退出\n")

last_size = 0
while True:
    try:
        if os.path.exists(output_file):
            current_size = os.path.getsize(output_file)
            if current_size != last_size:
                os.system('clear')
                print("=" * 60)
                print("📊 B站私信发送进度监控")
                print("=" * 60)
                print()

                with open(output_file, 'r') as f:
                    lines = f.readlines()
                    # 显示最后30行
                    for line in lines[-30:]:
                        print(line.rstrip())

                print()
                print("=" * 60)
                print(f"⏰ {time.strftime('%Y-%m-%d %H:%M:%S')}")
                print("=" * 60)

                last_size = current_size

        time.sleep(2)
    except KeyboardInterrupt:
        print("\n\n👋 监控已停止")
        break
