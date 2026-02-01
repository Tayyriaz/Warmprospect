#!/usr/bin/env python3
"""
CLI script to build knowledge base for a business.
Calls core.rag.builder.build_kb_for_business().
"""

import sys
import argparse
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from core.rag.builder import build_kb_for_business


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build knowledge base for a business website")
    parser.add_argument("--business_id", required=True, help="Business ID")
    parser.add_argument("--url", required=True, help="Website URL to scrape")
    
    args = parser.parse_args()
    try:
        build_kb_for_business(args.business_id, args.url)
        print(f"✅ Knowledge base built successfully for {args.business_id}")
    except Exception as e:
        print(f"❌ Failed to build knowledge base: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
