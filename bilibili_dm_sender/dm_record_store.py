#!/usr/bin/env python3
"""
B站私信发送记录 - Supabase存储
"""

import os
import sys
from datetime import datetime
from supabase import create_client, Client
from typing import Optional

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.base_config import SUPABASE_URL, SUPABASE_KEY


class DMRecordStore:
    """私信发送记录存储"""

    def __init__(self):
        """初始化Supabase客户端"""
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise ValueError("请在 config/base_config.py 中配置 SUPABASE_URL 和 SUPABASE_KEY")

        self.client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        self.table_name = "bilibili_dm_records"

    def save_dm_record(
        self,
        user_id: str,
        username: str,
        message: str,
        status: str,
        error_msg: Optional[str] = None
    ) -> bool:
        """
        保存私信发送记录

        Args:
            user_id: B站用户ID
            username: 用户名
            message: 发送的消息内容
            status: 发送状态 (success/failed)
            error_msg: 错误信息（如果失败）

        Returns:
            bool: 是否保存成功
        """
        try:
            data = {
                "user_id": user_id,
                "username": username,
                "message": message,
                "status": status,
                "error_msg": error_msg,
                "sent_at": datetime.now().isoformat(),
                "campaign": "openclaw_2026"  # 活动标识
            }

            result = self.client.table(self.table_name).insert(data).execute()

            if result.data:
                print(f"✅ 已记录到数据库: {username} - {status}")
                return True
            else:
                print(f"⚠️  数据库记录失败: {username}")
                return False

        except Exception as e:
            print(f"❌ 数据库错误: {str(e)}")
            return False

    def get_sent_count(self, campaign: str = "openclaw_2026") -> int:
        """获取已发送数量"""
        try:
            result = self.client.table(self.table_name)\
                .select("*", count="exact")\
                .eq("campaign", campaign)\
                .eq("status", "success")\
                .execute()

            return result.count if hasattr(result, 'count') else 0

        except Exception as e:
            print(f"❌ 查询错误: {str(e)}")
            return 0

    def get_failed_users(self, campaign: str = "openclaw_2026") -> list:
        """获取发送失败的用户列表"""
        try:
            result = self.client.table(self.table_name)\
                .select("user_id, username, error_msg")\
                .eq("campaign", campaign)\
                .eq("status", "failed")\
                .execute()

            return result.data if result.data else []

        except Exception as e:
            print(f"❌ 查询错误: {str(e)}")
            return []

    def is_already_sent(self, user_id: str, campaign: str = "openclaw_2026") -> bool:
        """检查是否已经发送过"""
        try:
            result = self.client.table(self.table_name)\
                .select("user_id")\
                .eq("campaign", campaign)\
                .eq("user_id", user_id)\
                .eq("status", "success")\
                .execute()

            return len(result.data) > 0 if result.data else False

        except Exception as e:
            print(f"❌ 查询错误: {str(e)}")
            return False


if __name__ == "__main__":
    # 测试
    store = DMRecordStore()

    print(f"📊 已成功发送: {store.get_sent_count()} 条")

    failed = store.get_failed_users()
    if failed:
        print(f"\n❌ 发送失败: {len(failed)} 个用户")
        for user in failed[:5]:
            print(f"  - {user['username']}: {user['error_msg']}")
