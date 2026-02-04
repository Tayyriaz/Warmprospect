"""
Knowledge Base Builder: Core logic for scraping websites and building RAG indexes.
"""

import gzip
import hashlib
import json
import os
import queue
import re
import time
import warnings
from dataclasses import dataclass
from typing import List, Dict, Set, Iterable, Optional, Tuple
from urllib.parse import urlparse
from pathlib import Path

import faiss
import numpy as np
import requests
import urllib3
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from google import genai
import yaml

from core.database import BusinessConfigDB

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)


@dataclass
class Page:
    url: str
    title: str
    text: str
    checksum: str
    fetched_at: float
    category: Optional[str] = None


def _load_config() -> dict:
    """Load config from config.yaml."""
    root_dir = Path(__file__).resolve().parent.parent.parent
    config_file = root_dir / "config.yaml"
    if config_file.exists():
        with open(config_file, 'r') as f:
            return yaml.safe_load(f) or {}
    return {}


# Load config
_config = _load_config()
_scraping_config = _config.get("scraping", {})
_rag_config = _config.get("rag", {})
# Suppress InsecureRequestWarning when verify_ssl is off, so stderr shows real errors
if not _scraping_config.get("verify_ssl", True):
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
_models_config = _config.get("models", {})

# Config values (read from config.yaml only, not from environment variables)
MAX_DEPTH = int(_scraping_config.get("max_depth", 5))
MAX_PAGES = int(_scraping_config.get("max_pages", 500))
MAX_SECONDS = int(_scraping_config.get("max_seconds", 600))
MAX_LINKS_PER_PAGE = int(_scraping_config.get("max_links_per_page", 30))
MAX_QUEUE_SIZE = int(_scraping_config.get("max_queue_size", 1000))
REQUEST_DELAY = float(_scraping_config.get("request_delay", 2))
CHUNK_SIZE = int(_rag_config.get("chunk_size", 800))
CHUNK_OVERLAP = int(_rag_config.get("chunk_overlap", 100))
EMBED_MODEL = os.getenv("GEMINI_EMBED_MODEL", _models_config.get("embed_model", "text-embedding-004"))
CATEGORIZATION_MODEL = os.getenv("GEMINI_CATEGORIZATION_MODEL", _models_config.get("categorization_model", "gemini-2.5-flash"))


def normalize_url(url: str, root_url: str) -> str:
    """Normalize URL relative to root and remove non-content query params."""
    # Handle protocol-relative URLs
    if url.startswith("//"):
        url = "https:" + url
    elif url.startswith("/"):
        url = root_url.rstrip("/") + url
    
    # Remove fragment
    url = url.split("#", 1)[0].strip()
    
    # Parse and clean query parameters
    parsed = urlparse(url)
    if parsed.query:
        # Filter out non-content query params
        skip_params = {"preview", "elementor-preview", "ver", "cache", "nocache", 
                      "utm_source", "utm_medium", "utm_campaign"}
        query_params = [p for p in parsed.query.split("&") 
                       if p.split("=", 1)[0].lower() not in skip_params]
        url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if query_params:
            url += "?" + "&".join(query_params)
    
    # Normalize trailing slash (remove for consistency, except root)
    if url.endswith("/") and len(url) > len(root_url):
        url = url.rstrip("/")
    
    return url


def is_allowed(url: str, base_domain: str) -> bool:
    """Check if URL is allowed (same domain)."""
    if not url.startswith("http"):
        return False
    parsed = urlparse(url)
    if parsed.hostname is None:
        return False
    return parsed.hostname == base_domain or parsed.hostname.endswith("." + base_domain)


def _fetch_requests(url: str, retry_count: int = 0) -> str:
    """Fetch HTML using requests with rate limit retry logic."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
    verify_ssl = _scraping_config.get("verify_ssl", True)
    resp = requests.get(url, timeout=(10, 30), headers=headers, allow_redirects=True, verify=verify_ssl)
    
    # Handle rate limiting (429) with exponential backoff retry
    if resp.status_code == 429:
        if retry_count < 3:
            wait_time = (2 ** retry_count) * 5  # 5s, 10s, 20s
            print(f"  ⚠ Rate limited (429) for {url}, retrying in {wait_time}s...")
            time.sleep(wait_time)
            return _fetch_requests(url, retry_count + 1)
        raise ValueError(f"Rate limited (429) after {retry_count} retries for {url}")
    
    resp.raise_for_status()
    
    # Handle gzip-compressed content
    text = resp.text
    if _looks_like_binary(text):
        try:
            text = gzip.decompress(resp.content).decode("utf-8", errors="replace")
        except Exception:
            pass
    
    # Validate HTML content
    if _looks_like_binary(text) or "<" not in text or ">" not in text:
        raise ValueError(
            f"Response from {url} does not look like HTML (possibly binary or wrong encoding). "
            "Refusing to store to avoid gibberish in knowledge base."
        )
    return text


def _fetch_playwright(browser, url: str) -> str:
    """Fetch HTML using Playwright browser. Handles JS-heavy pages and validates content."""
    ignore_https = not _scraping_config.get("verify_ssl", True)
    context = browser.new_context(ignore_https_errors=ignore_https)
    try:
        page = context.new_page()
        try:
            # Wait for network idle + extra time for lazy-loaded content
            page.goto(url, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(2000)  # Wait for lazy-loaded content
            text = page.content()
        finally:
            page.close()
    finally:
        context.close()
    
    # Validate HTML content
    if not text or "<" not in text or ">" not in text:
        raise ValueError(f"Response from {url} does not look like HTML.")
    
    # Check for error/loading pages
    text_lower = text.lower()
    if "429 too many requests" in text_lower or "too many requests" in text_lower:
        raise ValueError(f"Rate limited (429) for {url}")
    # If page is small and has many "loading" mentions, it's probably not loaded
    if "loading" in text_lower and text_lower.count("loading") > 3 and len(text) < 5000:
        raise ValueError(f"Page appears to still be loading for {url}")
    
    return text


def fetch(url: str, fetcher=None) -> str:
    """Fetch HTML from URL. Uses fetcher if provided, else requests (or Playwright when configured)."""
    if fetcher is not None:
        return fetcher(url)
    if _scraping_config.get("use_playwright", False):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return _fetch_requests(url)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                return _fetch_playwright(browser, url)
            finally:
                browser.close()
    return _fetch_requests(url)


def _looks_like_binary(s: str) -> bool:
    """True if string looks like binary data decoded as text (e.g. gzip as UTF-8)."""
    if "\x00" in s:
        return True
    control = sum(1 for c in s if ord(c) < 32 and c not in "\n\r\t")
    return control > max(3, len(s) // 100)


def extract(url: str, html: str) -> Page:
    """Extract text content from HTML with fallback strategies."""
    soup = BeautifulSoup(html, "html.parser")
    title = (soup.title.string or "").strip() if soup.title else ""

    # Remove non-content elements
    for tag in soup(["script", "style", "noscript", "iframe", "nav", "footer", "header"]):
        tag.decompose()
    
    # Try to find main content area
    main_content = None
    for selector in ["main", "article", "[role='main']", ".content", "#content", ".main-content"]:
        main_content = soup.select_one(selector)
        if main_content:
            break
    
    source = main_content or soup.find("body") or soup
    text = " ".join(source.get_text(separator=" ", strip=True).split())
    
    # Fallback strategies if text is too short
    if len(text) < 100:
        # Try paragraphs
        para_text = " ".join(p.get_text(strip=True) for p in soup.find_all("p") if p.get_text(strip=True))
        if len(para_text) > len(text):
            text = para_text
        
        # Try headings
        if len(text) < 100:
            heading_text = " ".join(h.get_text(strip=True) for h in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]) if h.get_text(strip=True))
            if len(heading_text) > len(text):
                text = heading_text
        
        # Try content divs
        if len(text) < 100:
            div_text = " ".join(d.get_text(strip=True) for d in soup.find_all("div", class_=re.compile(r"content|text|description|body|main", re.I)) if d.get_text(strip=True))
            if len(div_text) > len(text):
                text = div_text
    
    # Final fallback: entire body
    if len(text) < 50:
        body = soup.find("body")
        if body:
            text = " ".join(body.get_text(separator=" ", strip=True).split())
    
    checksum = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return Page(url=url, title=title, text=text, checksum=checksum, fetched_at=time.time())


def fetch_sitemap_urls(sitemap_url: str, base_domain: str, fetcher=None, max_depth: int = 2) -> List[str]:
    """
    Fetch URLs from sitemap.xml. Handles sitemap index files and nested sitemaps.
    Returns deduplicated list of URLs.
    """
    seen_sitemaps: Set[str] = set()
    all_urls: List[str] = []
    
    def _fetch_sitemap(url: str, depth: int) -> List[str]:
        """Recursively fetch sitemap URLs."""
        if depth > max_depth or url in seen_sitemaps:
            return []
        seen_sitemaps.add(url)
        
        try:
            xml = fetch(url, fetcher)
        except Exception as e:
            print(f"  ⚠ Could not fetch sitemap {url}: {e}")
            return []
        
        # Check if this is a sitemap index
        sitemap_refs = re.findall(r"<sitemap>.*?<loc>(.*?)</loc>.*?</sitemap>", xml, re.DOTALL)
        if sitemap_refs:
            print(f"  Found sitemap index with {len(sitemap_refs)} nested sitemaps")
            urls = []
            for nested_sitemap in sitemap_refs:
                nested_sitemap = nested_sitemap.strip()
                if nested_sitemap and is_allowed(nested_sitemap, base_domain):
                    urls.extend(_fetch_sitemap(nested_sitemap, depth + 1))
            return urls
        
        # Regular sitemap - extract URLs (handle with/without XML namespaces)
        urls = []
        for match in re.finditer(r"<loc[^>]*>(.*?)</loc>", xml):
            loc = match.group(1).strip()
            if loc and is_allowed(loc, base_domain):
                urls.append(loc)
        return urls
    
    all_urls = _fetch_sitemap(sitemap_url, 0)
    # Remove duplicates while preserving order
    seen = set()
    return [url for url in all_urls if url not in seen and not seen.add(url)]


def update_status(business_id: str, status: str, message: str = "", progress: int = 0):
    """Update status file for frontend polling."""
    try:
        status_file = os.path.join("data", business_id, "scraping_status.json")
        os.makedirs(os.path.dirname(status_file), exist_ok=True)
        with open(status_file, "w", encoding="utf-8") as f:
            json.dump({
                "status": status,
                "message": message,
                "progress": progress,
                "updated_at": time.time()
            }, f)
    except Exception:
        pass  # Don't fail scraping if status update fails


def _calculate_progress(started: float, pages_count: int, queue_size: int) -> int:
    """Calculate scraping progress percentage (20-40% range)."""
    elapsed = time.time() - started
    time_progress = min(int((elapsed / MAX_SECONDS) * 15), 15)
    pages_progress = min(int((pages_count / MAX_PAGES) * 20), 20)
    queue_progress = min(int((queue_size / MAX_QUEUE_SIZE) * 5), 5)
    return min(20 + time_progress + pages_progress + queue_progress, 40)


def crawl(seed_urls: Iterable[str], base_domain: str, root_url: str, business_id: Optional[str] = None, fetcher=None) -> Tuple[List[Page], List[str]]:
    """Crawl website starting from seed URLs. Returns (pages, fetch_errors). Optional fetcher uses e.g. Playwright."""
    seen: Set[str] = set()
    q: queue.Queue = queue.Queue()
    retry_queue: queue.Queue = queue.Queue()  # Queue for rate-limited pages to retry later
    started = time.time()
    last_status_update = started
    fetch_errors = []
    rate_limited_count = 0
    skipped_loading = 0
    skipped_too_little = 0
    skipped_duplicate = 0
    
    for s in seed_urls:
        q.put((s, 0))
    pages: List[Page] = []

    while (not q.empty() or not retry_queue.empty()) and len(pages) < MAX_PAGES:
        elapsed = time.time() - started
        if elapsed > MAX_SECONDS:
            print(f"\n[WARN] Timeout reached ({MAX_SECONDS}s). Processed {len(pages)} pages.")
            print(f"  - Main queue: {q.qsize()}, Retry queue: {retry_queue.qsize()}, Rate-limited: {rate_limited_count}")
            # Give extra time for retry queue if we have retries
            if retry_queue.qsize() > 0 and elapsed < MAX_SECONDS + 60:
                print(f"  - Processing retry queue (extra 60s)...")
                moved = min(retry_queue.qsize(), 100, MAX_QUEUE_SIZE - q.qsize())
                for _ in range(moved):
                    q.put(retry_queue.get())
                if moved > 0:
                    print(f"  - Moved {moved} URLs from retry queue, continuing...")
                    continue
            break
        
        if q.qsize() > MAX_QUEUE_SIZE:
            break
        
        # Process retry queue when main queue is empty
        if q.empty() and not retry_queue.empty():
            retry_size = retry_queue.qsize()
            print(f"  ↻ Moving {retry_size} rate-limited URLs back to queue for retry...")
            moved = min(retry_size, MAX_QUEUE_SIZE - q.qsize())
            for _ in range(moved):
                q.put(retry_queue.get())
            # Brief delay before retrying (max 10s)
            if retry_queue.qsize() > 0:
                wait_time = min(10, retry_queue.qsize())
                print(f"  ⏳ Waiting {wait_time}s before retrying remaining {retry_queue.qsize()} pages...")
                time.sleep(wait_time)
            if moved > 0:
                print(f"  ✓ Moved {moved} URLs back to main queue")
                continue
        
        # Update status periodically
        if business_id and (time.time() - last_status_update) > 3:
            progress = _calculate_progress(started, len(pages), q.qsize())
            
            # Build status message
            msg_parts = [f"Scraping... Fetched {len(pages)} pages. Queue: {q.qsize()}"]
            if retry_queue.qsize() > 0:
                msg_parts.append(f"Retry queue: {retry_queue.qsize()}")
            if rate_limited_count > 0:
                msg_parts.append(f"Rate limited: {rate_limited_count}")
            if fetch_errors:
                msg_parts.append(f"Errors: {len(fetch_errors)}")
            
            update_status(business_id, "scraping", ". ".join(msg_parts), progress)
            last_status_update = time.time()
        
        # Prefer main queue, but use retry queue if main is empty
        if not q.empty():
            url, depth = q.get()
        else:
            url, depth = retry_queue.get()
        
        if url in seen:
            skipped_duplicate += 1
            continue
        if depth > MAX_DEPTH:
            continue
        seen.add(url)
        
        html = None
        try:
            html = fetch(url, fetcher)
            page = extract(url, html)
            
            # Filter out error pages and loading pages
            if page.text:
                page_text_lower = page.text.lower()
                # Check for rate limit errors
                if "429 too many requests" in page_text_lower or "too many requests" in page_text_lower:
                    rate_limited_count += 1
                    print(f"  ⚠ Rate limited (429): {url} - adding to retry queue")
                    if retry_queue.qsize() < MAX_QUEUE_SIZE:
                        retry_queue.put((url, depth))
                    # Brief delay every 20 rate limits
                    if rate_limited_count % 20 == 0:
                        print(f"  ⚠ {rate_limited_count} rate-limited pages. Adding brief delay...")
                        time.sleep(3)
                    continue
                # Check for loading pages (small pages with many "loading" mentions)
                if "loading" in page_text_lower and page_text_lower.count("loading") > 3 and len(page.text) < 5000:
                    skipped_loading += 1
                    print(f"  ⚠ Skipped (page still loading): {url}")
                    continue
            
            if page.text and len(page.text.strip()) >= 50:  # Require at least 50 chars
                pages.append(page)
                print(f"  ✓ Fetched: {url} ({len(page.text)} chars)")
                
                # Update progress after each successful page fetch (throttled)
                if business_id and (time.time() - last_status_update) > 2:
                    progress = _calculate_progress(started, len(pages), q.qsize())
                    
                    msg_parts = [f"Scraping... Fetched {len(pages)} pages. Queue: {q.qsize()}"]
                    if retry_queue.qsize() > 0:
                        msg_parts.append(f"Retry queue: {retry_queue.qsize()}")
                    if rate_limited_count > 0:
                        msg_parts.append(f"Rate limited: {rate_limited_count}")
                    if fetch_errors:
                        msg_parts.append(f"Errors: {len(fetch_errors)}")
                    
                    update_status(business_id, "scraping", ". ".join(msg_parts), progress)
                    last_status_update = time.time()
            else:
                skipped_too_little += 1
                print(f"  ⚠ Skipped (too little text): {url} ({len(page.text)} chars)")
            
            # Adaptive delay: increase if actively getting rate limited
            delay = REQUEST_DELAY
            if rate_limited_count > 0 and (rate_limited_count % 20) >= 5:
                delay = min(REQUEST_DELAY * 1.5, 3)  # Increase by 50%, max 3s
            time.sleep(delay)
        except Exception as e:
            error_msg = f"{url}: {str(e)[:100]}"
            fetch_errors.append(error_msg)
            if len(fetch_errors) <= 5:  # Only log first 5 errors
                print(f"  ✗ Error fetching {url}: {e}")
            continue

        # Extract links from HTML if queue has space
        if html and q.qsize() < MAX_QUEUE_SIZE:
            try:
                soup = BeautifulSoup(html, "html.parser")
                links_queued = 0
                for a in soup.find_all("a", href=True):
                    if q.qsize() >= MAX_QUEUE_SIZE or links_queued >= MAX_LINKS_PER_PAGE:
                        break
                    nxt = normalize_url(a["href"], root_url)
                    if is_allowed(nxt, base_domain) and nxt not in seen:
                        q.put((nxt, depth + 1))
                        links_queued += 1
            except Exception:
                pass
    
    if business_id:
        remaining_in_queue = q.qsize()
        remaining_in_retry = retry_queue.qsize()
        
        # Build status message
        status_msg = f"Finished scraping. Fetched {len(pages)} pages."
        if rate_limited_count > 0 or remaining_in_queue > 0 or remaining_in_retry > 0:
            status_msg += f" (Rate-limited: {rate_limited_count}, Queue: {remaining_in_queue}, Retry queue: {remaining_in_retry})"
        if fetch_errors and len(pages) == 0:
            status_msg += f" Errors encountered: {fetch_errors[0] if fetch_errors else 'Unknown error'}"
        update_status(business_id, "scraping", status_msg, 40)
        
        # Log detailed summary
        print(f"\n[SUMMARY] Scraping completed:")
        print(f"  - Pages fetched: {len(pages)}")
        print(f"  - Rate-limited: {rate_limited_count}")
        print(f"  - Skipped (loading): {skipped_loading}")
        print(f"  - Skipped (too little text): {skipped_too_little}")
        print(f"  - Skipped (duplicate URLs): {skipped_duplicate}")
        print(f"  - Remaining in queue: {remaining_in_queue}")
        print(f"  - Remaining in retry queue: {remaining_in_retry}")
        print(f"  - Errors: {len(fetch_errors)}")
        print(f"  - Total URLs processed: {len(seen)}")
    
    if len(pages) == 0 and fetch_errors:
        print(f"\n[ERROR] Failed to fetch any pages. Sample errors:")
        for err in fetch_errors[:5]:
            print(f"  - {err}")
    
    return pages, fetch_errors


def _sanitize_text_for_meta(s: str) -> str:
    """Remove control characters that cause gibberish in JSON/text storage."""
    return "".join(c for c in s if ord(c) >= 32 or c in "\n\r\t")


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """Split text into chunks."""
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk_words = words[i : i + size]
        if chunk_words:
            chunks.append(" ".join(chunk_words))
        i += size - overlap
    return chunks


def categorize_page(client: genai.Client, page: Page) -> str:
    """Categorize a page using Gemini API."""
    try:
        url_path = urlparse(page.url).path.lower()
        
        # URL pattern matching
        if any(term in url_path for term in ['/product', '/item', '/shop', '/catalog', '/store']):
            return "Products"
        elif any(term in url_path for term in ['/service', '/solution', '/offer']):
            return "Services"
        elif any(term in url_path for term in ['/about', '/team', '/company']):
            return "About"
        elif any(term in url_path for term in ['/contact', '/reach']):
            return "Contact"
        elif any(term in url_path for term in ['/support', '/help', '/faq']):
            return "Support"
        elif any(term in url_path for term in ['/pricing', '/price', '/plan']):
            return "Pricing"
        elif any(term in url_path for term in ['/blog', '/article', '/post']):
            return "Blog"
        elif any(term in url_path for term in ['/privacy', '/terms', '/legal']):
            return "Legal"
        
        # AI categorization
        content_preview = page.text[:1000] if len(page.text) > 1000 else page.text
        prompt = f"""Categorize this webpage into EXACTLY ONE category:
Categories: Products, Services, About, Contact, Support, Pricing, Blog, Legal, General, Other
Title: {page.title}
URL: {page.url}
Content: {content_preview}
Respond with ONLY the category name."""

        model = client.models.get(CATEGORIZATION_MODEL)
        response = model.generate_content(prompt, config={"temperature": 0.1, "max_output_tokens": 10})
        category = response.text.strip().strip('"\'.,;:!?').split('\n')[0].split('.')[0].split()[0]
        
        category_mapping = {
            "product": "Products", "service": "Services", "contact-us": "Contact",
            "about-us": "About", "pricing": "Pricing", "blog": "Blog",
            "legal": "Legal", "support": "Support", "general": "General", "other": "Other"
        }
        category = category_mapping.get(category.lower(), category)
        
        valid_categories = ["Products", "Services", "About", "Contact", "Support", "Pricing", "Blog", "Legal", "General", "Other"]
        if category not in valid_categories:
            category = "General"
        
        time.sleep(0.2)
        return category
    except Exception:
        return "General"


def embed_chunks(client: genai.Client, chunks: List[str]) -> np.ndarray:
    """Embed text chunks using Gemini."""
    vectors = []
    for ch in chunks:
        try:
            emb = client.models.embed_content(model=EMBED_MODEL, content=ch)
        except TypeError:
            emb = client.models.embed_content(model=EMBED_MODEL, contents=ch)
        vectors.append(np.array(emb.embeddings[0].values, dtype="float32"))
        time.sleep(0.3)
    return np.stack(vectors)


def build_kb_for_business(business_id: str, website_url: str):
    """
    Build knowledge base for a specific business.
    Saves index and metadata to data/{business_id}/
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is required.")
    
    update_status(business_id, "pending", "Preparing to scrape website...", 5)
    
    parsed = urlparse(website_url)
    base_domain = parsed.hostname or ""
    root_url = f"{parsed.scheme}://{parsed.hostname}"
    if parsed.path:
        root_url = website_url.rstrip("/")
    
    output_dir = os.path.join("data", business_id)
    os.makedirs(output_dir, exist_ok=True)
    
    meta_path = os.path.join(output_dir, "meta.jsonl")
    index_path = os.path.join(output_dir, "index.faiss")
    meta_path_tmp = os.path.join(output_dir, "meta.jsonl.tmp")
    index_path_tmp = os.path.join(output_dir, "index.faiss.tmp")
    
    update_status(business_id, "scraping", "Finding website pages...", 10)
    # Try multiple sitemap locations
    sitemap_urls = [
        f"{root_url}/sitemap.xml",
        f"{root_url}/sitemap_index.xml",
        f"{root_url}/sitemaps/sitemap.xml",
    ]
    use_playwright = _scraping_config.get("use_playwright", False)
    pw_ctx = None
    if use_playwright:
        try:
            from playwright.sync_api import sync_playwright
            pw_ctx = sync_playwright()
        except ImportError:
            print(f"[WARN] use_playwright is true but playwright not installed. Using requests.")
            use_playwright = False

    def _do_crawl(fetcher):
        # Try sitemap locations until we find one that works
        seeds = []
        for sitemap_url in sitemap_urls:
            found = fetch_sitemap_urls(sitemap_url, base_domain, fetcher)
            if found:
                seeds = found
                print(f"Found sitemap at {sitemap_url} with {len(found)} URLs")
                break
        
        if not seeds:
            seeds = [root_url]
            print(f"No sitemap found, crawling from root: {root_url}")
        else:
            print(f"Using sitemap URLs ({len(seeds)} total) as seeds.")
        
        print(f"Building KB for business: {business_id}")
        print(f"Website: {website_url}")
        print(f"Crawling (max {MAX_PAGES} pages, {MAX_SECONDS}s timeout)...")
        update_status(business_id, "scraping", "Scraping website content...", 20)
        return crawl(seeds, base_domain, root_url, business_id, fetcher)

    if use_playwright and pw_ctx is not None:
        with pw_ctx as p:
            browser = p.chromium.launch(headless=True)
            fetcher = lambda url: _fetch_playwright(browser, url)
            print(f"Using Playwright (browser) to scrape.")
            pages, fetch_errors = _do_crawl(fetcher)
    else:
        pages, fetch_errors = _do_crawl(None)
    print(f"\n[SUCCESS] Fetched {len(pages)} pages")
    
    if not pages:
        reason = fetch_errors[0] if fetch_errors else "No URLs could be fetched."
        update_status(business_id, "failed", f"No pages fetched. {reason}", 0)
        raise RuntimeError(f"No pages fetched. {reason}")
    
    total_text = sum(len(p.text) for p in pages)
    print(f"   Total text: {total_text:,} characters")
    print(f"   Average per page: {total_text // len(pages) if pages else 0:,} characters")
    
    update_status(business_id, "categorizing", "Categorizing pages...", 40)
    client = genai.Client(api_key=api_key)
    
    print(f"\n[Categorizing] Categorizing {len(pages)} pages...")
    for i, page in enumerate(pages):
        page.category = categorize_page(client, page)
        if (i + 1) % 10 == 0:
            print(f"  Categorized {i + 1}/{len(pages)} pages...")
    
    category_counts: Dict[str, int] = {}
    for page in pages:
        category = page.category or "General"
        category_counts[category] = category_counts.get(category, 0) + 1
    
    print(f"\n[Categories] Found {len(category_counts)} categories:")
    for cat, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {cat}: {count} pages")
    
    categories_data = {
        "categories": [
            {"name": cat, "page_count": count, "enabled": True}
            for cat, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True)
        ],
        "total_pages": len(pages),
        "updated_at": time.time()
    }
    
    try:
        db_manager = BusinessConfigDB()
        current_config = db_manager.get_business(business_id)
        if current_config:
            db_manager.create_or_update_business(
                business_id=current_config["business_id"],
                business_name=current_config["business_name"],
                system_prompt=current_config["system_prompt"],
                greeting_message=current_config.get("greeting_message"),
                primary_goal=current_config.get("primary_goal"),
                personality=current_config.get("personality"),
                privacy_statement=current_config.get("privacy_statement"),
                theme_color=current_config.get("theme_color"),
                widget_position=current_config.get("widget_position"),
                website_url=current_config.get("website_url"),
                contact_email=current_config.get("contact_email"),
                contact_phone=current_config.get("contact_phone"),
                cta_tree=current_config.get("cta_tree"),
                voice_enabled=current_config.get("voice_enabled", False),
                chatbot_button_text=current_config.get("chatbot_button_text"),
                business_logo=current_config.get("business_logo"),
                enabled_categories=current_config.get("enabled_categories", []),
                categories=categories_data
            )
            print(f"[SUCCESS] Categories saved to database for {business_id}")
    except Exception as e:
        print(f"[WARN] Failed to save categories to database: {e}")
    
    update_status(business_id, "indexing", "Building knowledge base...", 50)
    
    previous_checksums: Dict[str, str] = {}
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                for line in f:
                    rec = json.loads(line)
                    previous_checksums[rec.get("url", "")] = rec.get("checksum", "")
        except Exception:
            pass
    
    meta_records = []
    all_vectors = []
    seen_urls = set()  # Track URLs to avoid duplicates
    
    # Filter pages: deduplicate and skip unchanged content
    pages_to_process = []
    for page in pages:
        if page.url in seen_urls:
            continue
        seen_urls.add(page.url)
        if previous_checksums.get(page.url) != page.checksum:
            pages_to_process.append(page)
    
    total_pages = len(pages_to_process)
    processed = 0
    
    for page in pages_to_process:
        chunks = chunk_text(page.text)
        if not chunks:
            continue
        
        vectors = embed_chunks(client, chunks)
        clean_title = _sanitize_text_for_meta(page.title)
        category = page.category or "General"
        
        # Create meta records for all chunks
        for i, ch in enumerate(chunks):
            clean_chunk = _sanitize_text_for_meta(ch).strip() or " "
            meta_records.append({
                "url": page.url,
                "title": clean_title,
                "text": clean_chunk,
                "checksum": page.checksum,
                "fetched_at": page.fetched_at,
                "chunk_id": f"{page.url}#chunk-{i}",
                "category": category,
            })
        all_vectors.append(vectors)
        
        processed += 1
        if business_id and processed % 5 == 0:  # Update every 5 pages instead of every page
            progress = 50 + int((processed / total_pages) * 40)
            update_status(business_id, "indexing", f"Processing page {processed}/{total_pages}...", progress)
    
    if not meta_records and os.path.exists(index_path) and os.path.exists(meta_path):
        update_status(business_id, "completed", "Knowledge base is up to date!", 100)
        return
    
    if not meta_records:
        update_status(business_id, "failed", "No content chunks to index.", 0)
        raise RuntimeError("No chunks to index.")
    
    update_status(business_id, "indexing", "Creating search index...", 90)
    embeddings = np.vstack(all_vectors)
    index = faiss.IndexFlatL2(embeddings.shape[1])
    index.add(embeddings)
    
    faiss.write_index(index, index_path_tmp)
    with open(meta_path_tmp, "w", encoding="utf-8") as f:
        for rec in meta_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    
    os.replace(index_path_tmp, index_path)
    os.replace(meta_path_tmp, meta_path)
    
    print(f"[SUCCESS] Index written to {index_path}")
    print(f"[SUCCESS] Metadata written to {meta_path}")
    print(f"[SUCCESS] Knowledge base ready for business: {business_id}")
    
    try:
        db_manager = BusinessConfigDB()
        config = db_manager.get_business(business_id)
        if config and config.get("categories"):
            categories_data = config["categories"]
            status_file = os.path.join(output_dir, "scraping_status.json")
            status_data = {
                "status": "completed",
                "message": f"Knowledge base built! {len(pages)} pages, {len(meta_records)} chunks.",
                "progress": 100,
                "updated_at": time.time(),
                "categories": categories_data.get("categories", []),
                "total_pages": categories_data.get("total_pages", len(pages))
            }
            with open(status_file, "w", encoding="utf-8") as f:
                json.dump(status_data, f, indent=2)
    except Exception:
        update_status(business_id, "completed", f"Knowledge base built! {len(pages)} pages, {len(meta_records)} chunks.", 100)
