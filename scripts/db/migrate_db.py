#!/usr/bin/env python3
"""
Auto-sync database schema with SQLAlchemy models.

This script compares the model definitions in core/database.py with the actual
database schema and automatically adds any missing columns. Safe to run multiple times.

Run: python scripts/db/migrate_db.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.database import sync_schema

if __name__ == "__main__":
    print("Syncing database schema with models...")
    try:
        sync_schema()
        print("✅ Migration complete.")
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
