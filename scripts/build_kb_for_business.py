"""
Builds a RAG knowledge base for a specific business website.
Can be called with business_id and website_url as arguments.

Usage:
    python scripts/build_kb_for_business.py --business_id goaccel-website --url https://warmprospect.com/goaccel-website/
"""

import hashlib
import json
import os
import queue
import re
import time
import sys
import argparse
import warnings
from dataclasses import dataclass
from typing import List, Dict, Set, Iterable
from urllib.parse import urlparse

import faiss
import numpy as np
import requests
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from google import genai
from dotenv import load_dotenv

# Suppress XML parsing warnings for HTML (Windows compatibility)
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

load_dotenv()

MAX_DEPTH = 5
MAX_PAGES = 500  # Increased from 200
MAX_SECONDS = 600  # Increased from 120 (10 minutes)
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
EMBED_MODEL = "text-embedding-004"


@dataclass
class Page:
    url: str
    title: str
    text: str
    checksum: str
    fetched_at: float


def normalize_url(url: str, root_url: str) -> str:
    if url.startswith("//"):
        url = "https:" + url
    if url.startswith("/"):
        url = root_url.rstrip("/") + url
    return url.split("#")[0].strip()


def is_allowed(url: str, base_domain: str) -> bool:
    if not url.startswith("http"):
        return False
    parsed = urlparse(url)
    if parsed.hostname is None:
        return False
    # Allow only the specified domain
    if parsed.hostname == base_domain or parsed.hostname.endswith("." + base_domain):
        return True
    return False


def fetch(url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }
    resp = requests.get(url, timeout=(5, 30), headers=headers, allow_redirects=True)  # Increased timeout
    resp.raise_for_status()
    return resp.text


def extract(url: str, html: str) -> Page:
    soup = BeautifulSoup(html, "html.parser")
    title = (soup.title.string or "").strip() if soup.title else ""

    # Remove unwanted tags
    for tag in soup(["script", "style", "noscript", "iframe", "nav", "footer", "header"]):
        tag.decompose()
    
    # Try to get main content first (common content selectors)
    main_content = None
    for selector in ["main", "article", "[role='main']", ".content", "#content", ".main-content"]:
        main_content = soup.select_one(selector)
        if main_content:
            break
    
    # Use main content if found, otherwise use body
    source = main_content if main_content else soup.find("body")
    if not source:
        source = soup
    
    # Extract text with better formatting
    text = " ".join(source.get_text(separator=" ", strip=True).split())
    
    # If text is too short, try multiple strategies
    if len(text) < 100:
        # Strategy 1: Get all paragraphs
        paragraphs = soup.find_all("p")
        para_text = " ".join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
        if len(para_text) > len(text):
            text = para_text
        
        # Strategy 2: Get headings and their following content
        if len(text) < 100:
            headings = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
            heading_text = " ".join([h.get_text(strip=True) for h in headings if h.get_text(strip=True)])
            if len(heading_text) > len(text):
                text = heading_text
        
        # Strategy 3: Get divs with common content classes
        if len(text) < 100:
            content_divs = soup.find_all("div", class_=re.compile(r"content|text|description|body|main", re.I))
            div_text = " ".join([d.get_text(strip=True) for d in content_divs if d.get_text(strip=True)])
            if len(div_text) > len(text):
                text = div_text
    
    # Final fallback: use entire body if still too short
    if len(text) < 50:
        body = soup.find("body")
        if body:
            text = " ".join(body.get_text(separator=" ", strip=True).split())
    
    checksum = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return Page(url=url, title=title, text=text, checksum=checksum, fetched_at=time.time())


def fetch_sitemap_urls(sitemap_url: str, base_domain: str) -> List[str]:
    urls: List[str] = []
    try:
        xml = fetch(sitemap_url)
    except Exception as e:
        print(f"Skip sitemap ({sitemap_url}): {e}")
        return urls
    for loc in re.findall(r"<loc>(.*?)</loc>", xml):
        loc = loc.strip()
        if is_allowed(loc, base_domain):
            urls.append(loc)
    return urls


def crawl(seed_urls: Iterable[str], base_domain: str, root_url: str) -> List[Page]:
    seen: Set[str] = set()
    q: queue.Queue = queue.Queue()
    started = time.time()
    
    for s in seed_urls:
        q.put((s, 0))
    pages: List[Page] = []

    while not q.empty() and len(pages) < MAX_PAGES:
        elapsed = time.time() - started
        if elapsed > MAX_SECONDS:
            print(f"Stopping crawl due to time limit ({MAX_SECONDS}s). Fetched {len(pages)} pages so far.")
            break
        url, depth = q.get()
        if url in seen or depth > MAX_DEPTH:
            continue
        seen.add(url)
        try:
            html = fetch(url)
            page = extract(url, html)
            if page.text:
                pages.append(page)
                print(f"  [OK] Fetched: {url} (depth={depth}, text_len={len(page.text)}, total={len(pages)})")
            else:
                print(f"  [SKIP] Skipped (no text): {url}")
            time.sleep(0.2)  # Reduced delay slightly
        except Exception as e:
            print(f"  [ERROR] Skip {url}: {e}")
            continue

        # enqueue links
        soup = BeautifulSoup(html, "html.parser")
        links_found = 0
        for a in soup.find_all("a", href=True):
            nxt = normalize_url(a["href"], root_url)
            if is_allowed(nxt, base_domain) and nxt not in seen:
                q.put((nxt, depth + 1))
                links_found += 1
        if links_found > 0:
            print(f"    → Queued {links_found} new links (queue size: {q.qsize()})")
    return pages


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk_words = words[i : i + size]
        if chunk_words:
            chunks.append(" ".join(chunk_words))
        i += size - overlap
    return chunks


def embed_chunks(client: genai.Client, chunks: List[str]) -> np.ndarray:
    vectors = []
    for ch in chunks:
        try:
            emb = client.models.embed_content(model=EMBED_MODEL, content=ch)
        except TypeError:
            emb = client.models.embed_content(model=EMBED_MODEL, contents=ch)
        vectors.append(np.array(emb.embeddings[0].values, dtype="float32"))
        time.sleep(0.3)  # throttle
    return np.stack(vectors)


def update_status_file(business_id: str, status: str, message: str = "", progress: int = 0):
    """Update status file for frontend polling. Non-blocking - continues even if write fails."""
    try:
        status_file = os.path.join("data", business_id, "scraping_status.json")
        status_dir = os.path.dirname(status_file)
        
        # Create directory if it doesn't exist
        try:
            os.makedirs(status_dir, exist_ok=True)
        except PermissionError:
            print(f"[WARNING] Cannot create directory {status_dir}: Permission denied. Status updates will be skipped.")
            return
        
        status_data = {
            "status": status,
            "message": message,
            "progress": progress,
            "updated_at": time.time()
        }
        
        # Write status file
        try:
            with open(status_file, "w", encoding="utf-8") as f:
                json.dump(status_data, f)
        except PermissionError:
            print(f"[WARNING] Cannot write status file {status_file}: Permission denied.")
            print(f"[WARNING] Run 'sudo chown -R www-data:www-data data/' to fix permissions.")
            print(f"[WARNING] Scraping will continue, but status updates will be skipped.")
            return
    except Exception as e:
        # Don't fail the entire scraping process if status update fails
        print(f"[WARNING] Failed to update status file: {e}")
        import traceback
        traceback.print_exc()


def build_kb_for_business(business_id: str, website_url: str):
    """
    Build knowledge base for a specific business.
    Saves index and metadata to data/{business_id}/
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is required.")
    
    # Update status: starting
    update_status_file(business_id, "pending", "Preparing to scrape website...", 5)
    
    # Parse URL to get domain
    parsed = urlparse(website_url)
    base_domain = parsed.hostname or ""
    root_url = f"{parsed.scheme}://{parsed.hostname}"
    if parsed.path:
        root_url = website_url.rstrip("/")
    
    # Create business-specific output directory
    output_dir = os.path.join("data", business_id)
    os.makedirs(output_dir, exist_ok=True)
    
    meta_path = os.path.join(output_dir, "meta.jsonl")
    index_path = os.path.join(output_dir, "index.faiss")
    meta_path_tmp = os.path.join(output_dir, "meta.jsonl.tmp")
    index_path_tmp = os.path.join(output_dir, "index.faiss.tmp")
    
    # Try to find sitemap
    update_status_file(business_id, "scraping", "Finding website pages...", 10)
    sitemap_url = f"{root_url}/sitemap.xml"
    seeds = fetch_sitemap_urls(sitemap_url, base_domain)
    if not seeds:
        seeds = [root_url]
        print(f"No sitemap found, crawling from root: {root_url}")
    else:
        print(f"Using sitemap URLs ({len(seeds)}) as seeds.")
    
    print(f"Building KB for business: {business_id}")
    print(f"Website: {website_url}")
    print(f"Crawling (max {MAX_PAGES} pages, {MAX_SECONDS}s timeout)...")
    
    update_status_file(business_id, "scraping", "Scraping website content... This may take a few minutes.", 20)
    pages = crawl(seeds, base_domain, root_url)
    print(f"\n[SUCCESS] Fetched {len(pages)} pages")
    
    # Show summary
    total_text = sum(len(p.text) for p in pages)
    print(f"   Total text: {total_text:,} characters")
    print(f"   Average per page: {total_text // len(pages) if pages else 0:,} characters")
    
    if not pages:
        update_status_file(business_id, "failed", "No pages fetched. Check URL and site access.", 0)
        raise RuntimeError("No pages fetched. Check URL and site access.")
    
    # Update status: indexing
    update_status_file(business_id, "indexing", "Building knowledge base from scraped content...", 60)
    
    client = genai.Client(api_key=api_key)
    meta_records = []
    all_vectors = []
    
    # Load previous checksums
    previous_checksums: Dict[str, str] = {}
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                for line in f:
                    rec = json.loads(line)
                    previous_checksums[rec.get("url", "")] = rec.get("checksum", "")
        except Exception:
            pass
    
    total_pages = len(pages)
    processed = 0
    
    for page in pages:
        if previous_checksums.get(page.url) == page.checksum:
            continue
        
        chunks = chunk_text(page.text)
        if not chunks:
            continue
        vectors = embed_chunks(client, chunks)
        for i, ch in enumerate(chunks):
            meta_records.append({
                "url": page.url,
                "title": page.title,
                "text": ch,
                "checksum": page.checksum,
                "fetched_at": page.fetched_at,
                "chunk_id": f"{page.url}#chunk-{i}",
            })
        all_vectors.append(vectors)
        
        processed += 1
        # Update progress (60-90% for indexing)
        progress = 60 + int((processed / total_pages) * 30)
        update_status_file(business_id, "indexing", f"Processing page {processed}/{total_pages}...", progress)
    
    if not meta_records and os.path.exists(index_path) and os.path.exists(meta_path):
        print("No new/changed pages. Keeping existing index.")
        update_status_file(business_id, "completed", "Knowledge base is up to date!", 100)
        return
    
    if not meta_records:
        update_status_file(business_id, "failed", "No content chunks to index.", 0)
        raise RuntimeError("No chunks to index.")
    
    update_status_file(business_id, "indexing", "Creating search index...", 90)
    embeddings = np.vstack(all_vectors)
    index = faiss.IndexFlatL2(embeddings.shape[1])
    index.add(embeddings)
    
    faiss.write_index(index, index_path_tmp)
    with open(meta_path_tmp, "w", encoding="utf-8") as f:
        for rec in meta_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    
    # atomic swap
    os.replace(index_path_tmp, index_path)
    os.replace(meta_path_tmp, meta_path)
    
    print(f"[SUCCESS] Index written to {index_path}")
    print(f"[SUCCESS] Metadata written to {meta_path}")
    print(f"[SUCCESS] Knowledge base ready for business: {business_id}")
    
    # Update status: completed
    update_status_file(business_id, "completed", f"Knowledge base built successfully! {len(pages)} pages scraped, {len(meta_records)} chunks indexed.", 100)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build knowledge base for a business website")
    parser.add_argument("--business_id", required=True, help="Business ID")
    parser.add_argument("--url", required=True, help="Website URL to scrape")
    
    args = parser.parse_args()
    build_kb_for_business(args.business_id, args.url)
