#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Setup Vibe Coding Table in Supabase

This script creates the vibe_coding_raw_data table and its indexes in your Supabase database.
Run this once before starting vibe coding data collection.

Usage:
    python setup_vibe_coding_table.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from database.supabase_client import get_supabase
from tools import utils


def read_schema_file() -> str:
    """Read the SQL schema file."""
    schema_path = project_root / "schema" / "vibe_coding_schema.sql"
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")

    with open(schema_path, "r", encoding="utf-8") as f:
        return f.read()


def execute_sql(sql: str):
    """Execute SQL statements via Supabase RPC."""
    sb = get_supabase()

    # Split SQL into individual statements
    statements = [s.strip() for s in sql.split(";") if s.strip() and not s.strip().startswith("--")]

    utils.logger.info(f"Executing {len(statements)} SQL statements...")

    for i, statement in enumerate(statements, 1):
        # Skip comments
        if statement.startswith("--") or statement.startswith("/*"):
            continue

        try:
            utils.logger.info(f"[{i}/{len(statements)}] Executing: {statement[:80]}...")

            # Use Supabase's RPC to execute raw SQL
            # Note: This requires a database function to be created first
            # Alternatively, you can run this SQL directly in Supabase SQL Editor
            result = sb.rpc("exec_sql", {"sql": statement}).execute()

            utils.logger.info(f"✅ Statement {i} executed successfully")

        except Exception as e:
            # Some statements might fail if objects already exist - that's OK
            if "already exists" in str(e).lower():
                utils.logger.warning(f"⚠️  Statement {i} skipped (already exists)")
            else:
                utils.logger.error(f"❌ Statement {i} failed: {e}")
                raise


def main():
    """Main setup function."""
    utils.logger.info("=" * 60)
    utils.logger.info("Vibe Coding Table Setup")
    utils.logger.info("=" * 60)

    try:
        # Read schema
        utils.logger.info("Reading schema file...")
        schema_sql = read_schema_file()

        # Print instructions
        print("\n" + "=" * 60)
        print("SETUP INSTRUCTIONS")
        print("=" * 60)
        print("\nOption 1: Run SQL directly in Supabase (RECOMMENDED)")
        print("-" * 60)
        print("1. Go to your Supabase project dashboard")
        print("2. Navigate to: SQL Editor")
        print("3. Create a new query")
        print("4. Copy and paste the SQL from: schema/vibe_coding_schema.sql")
        print("5. Click 'Run' to execute")
        print("\nOption 2: Use this script (requires RPC function)")
        print("-" * 60)
        print("This script requires a custom RPC function in Supabase.")
        print("If you haven't set it up, use Option 1 instead.")
        print("\n" + "=" * 60)

        response = input("\nDo you want to continue with Option 2? (y/N): ").strip().lower()

        if response == "y":
            utils.logger.info("Executing SQL via Supabase RPC...")
            execute_sql(schema_sql)
            utils.logger.info("✅ Vibe coding table setup complete!")
        else:
            utils.logger.info("Setup cancelled. Please use Option 1 (Supabase SQL Editor).")
            print("\n📋 SQL to execute:")
            print("-" * 60)
            print(schema_sql)
            print("-" * 60)

    except Exception as e:
        utils.logger.error(f"❌ Setup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
