#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Quick test to verify vibe_coding_raw_data table exists in Supabase.
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from database.supabase_client import get_supabase
from tools import utils

def test_table_exists():
    """Test if vibe_coding_raw_data table exists."""
    try:
        sb = get_supabase()

        # Try to query the table (will fail if table doesn't exist)
        result = sb.table("vibe_coding_raw_data").select("id").limit(1).execute()

        utils.logger.info("✅ vibe_coding_raw_data table exists!")
        utils.logger.info(f"   Table has {len(result.data)} rows (showing first 1)")
        return True

    except Exception as e:
        error_msg = str(e).lower()
        if "does not exist" in error_msg or "relation" in error_msg:
            utils.logger.error("❌ vibe_coding_raw_data table does NOT exist!")
            utils.logger.error("   Please create it in Supabase SQL Editor:")
            utils.logger.error("   1. Go to Supabase Dashboard → SQL Editor")
            utils.logger.error("   2. Copy and paste: schema/vibe_coding_schema.sql")
            utils.logger.error("   3. Click 'Run'")
        else:
            utils.logger.error(f"❌ Error checking table: {e}")
        return False

if __name__ == "__main__":
    if test_table_exists():
        print("\n✅ Ready to run vibe coding crawler!")
        sys.exit(0)
    else:
        print("\n❌ Please create the table first.")
        sys.exit(1)
