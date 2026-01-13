#!/usr/bin/env python3
"""Quick test script to verify RAG retriever is working for goaccel-website"""

import os
from dotenv import load_dotenv
from rag.retriever import GoAccelRetriever, format_context

load_dotenv()

business_id = "goaccel-website"
index_path = os.path.join("data", business_id, "index.faiss")
meta_path = os.path.join("data", business_id, "meta.jsonl")

print(f"Testing RAG for business: {business_id}")
print(f"Index path: {index_path} (exists: {os.path.exists(index_path)})")
print(f"Meta path: {meta_path} (exists: {os.path.exists(meta_path)})")
print()

try:
    retriever = GoAccelRetriever(
        api_key=os.getenv("GEMINI_API_KEY", ""),
        index_path=index_path,
        meta_path=meta_path,
        model="text-embedding-004",
        top_k=5,
    )
    print("✅ Retriever loaded successfully!")
    print(f"   Metadata records: {len(retriever.metadata)}")
    print(f"   Index dimension: {retriever.index.d}")
    print()

    # Test queries
    test_queries = [
        "What is GoAccel?",
        "What services do you offer?",
        "frequently asked questions",
    ]

    for query in test_queries:
        print(f"Query: '{query}'")
        hits = retriever.search(query)
        print(f"  Found {len(hits)} hits")
        if hits:
            for i, hit in enumerate(hits[:3], 1):
                print(f"  Hit {i}: score={hit.get('score', 'N/A'):.4f}, url={hit.get('url', 'N/A')[:60]}...")
                print(f"    Text preview: {hit.get('text', '')[:100]}...")
        
        ctx = format_context(hits)
        if ctx:
            print(f"  ✅ Context generated ({len(ctx)} chars)")
            print(f"  Context preview: {ctx[:200]}...")
        else:
            print(f"  ⚠️ No context generated")
        print()

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
