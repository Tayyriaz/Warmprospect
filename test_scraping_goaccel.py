#!/usr/bin/env python3
"""
Test script to scrape goaccel.ai website and verify scraping improvements.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.rag.builder import build_kb_for_business

if __name__ == "__main__":
    business_id = "test-goaccel"
    website_url = "https://goaccel.ai/"
    
    print("=" * 60)
    print("🧪 Testing Scraping for: https://goaccel.ai/")
    print("=" * 60)
    print(f"Business ID: {business_id}")
    print(f"Website URL: {website_url}")
    print("\n🚀 Starting scraping with improvements:")
    print("  ✅ Retry mechanism with exponential backoff")
    print("  ✅ Playwright context reuse")
    print("  ✅ Improved text extraction")
    print("  ✅ Configurable delays")
    print("\n" + "=" * 60 + "\n")
    
    try:
        build_kb_for_business(business_id, website_url)
        print("\n" + "=" * 60)
        print("✅ Scraping completed successfully!")
        print("=" * 60)
    except Exception as e:
        print("\n" + "=" * 60)
        print(f"❌ Scraping failed: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        sys.exit(1)
