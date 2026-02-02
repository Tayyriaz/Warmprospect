"""
Knowledge Base Builder: Core logic for scraping websites and building RAG indexes.
"""

import hashlib
import json
import os
import queue
import re
import time
import warnings
from dataclasses import dataclass
from typing import List, Dict, Set, Iterable, Optional
from urllib.parse import urlparse
from pathlib import Path

import faiss
import numpy as np
import requests
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
_models_config = _config.get("models", {})

# Config values (read from config.yaml only, not from environment variables)
MAX_DEPTH = int(_scraping_config.get("max_depth", 5))
MAX_PAGES = int(_scraping_config.get("max_pages", 500))
MAX_SECONDS = int(_scraping_config.get("max_seconds", 600))
MAX_LINKS_PER_PAGE = int(_scraping_config.get("max_links_per_page", 30))
MAX_QUEUE_SIZE = int(_scraping_config.get("max_queue_size", 1000))
CHUNK_SIZE = int(_rag_config.get("chunk_size", 800))
CHUNK_OVERLAP = int(_rag_config.get("chunk_overlap", 100))
EMBED_MODEL = os.getenv("GEMINI_EMBED_MODEL", _models_config.get("embed_model", "text-embedding-004"))
CATEGORIZATION_MODEL = os.getenv("GEMINI_CATEGORIZATION_MODEL", _models_config.get("categorization_model", "gemini-2.5-flash"))


def normalize_url(url: str, root_url: str) -> str:
    """Normalize URL relative to root."""
    if url.startswith("//"):
        url = "https:" + url
    if url.startswith("/"):
        url = root_url.rstrip("/") + url
    return url.split("#")[0].strip()


def is_allowed(url: str, base_domain: str) -> bool:
    """Check if URL is allowed (same domain)."""
    if not url.startswith("http"):
        return False
    parsed = urlparse(url)
    if parsed.hostname is None:
        return False
    return parsed.hostname == base_domain or parsed.hostname.endswith("." + base_domain)


def fetch(url: str) -> str:
    """Fetch HTML from URL."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
    # SSL verification setting from config.yaml only
    verify_ssl = _scraping_config.get("verify_ssl", True)
    resp = requests.get(url, timeout=(10, 30), headers=headers, allow_redirects=True, verify=verify_ssl)
    resp.raise_for_status()
    return resp.text


def extract(url: str, html: str) -> Page:
    """Extract text content from HTML."""
    soup = BeautifulSoup(html, "html.parser")
    title = (soup.title.string or "").strip() if soup.title else ""

    for tag in soup(["script", "style", "noscript", "iframe", "nav", "footer", "header"]):
        tag.decompose()
    
    main_content = None
    for selector in ["main", "article", "[role='main']", ".content", "#content", ".main-content"]:
        main_content = soup.select_one(selector)
        if main_content:
            break
    
    source = main_content if main_content else soup.find("body")
    if not source:
        source = soup
    
    text = " ".join(source.get_text(separator=" ", strip=True).split())
    
    if len(text) < 100:
        paragraphs = soup.find_all("p")
        para_text = " ".join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
        if len(para_text) > len(text):
            text = para_text
        
        if len(text) < 100:
            headings = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
            heading_text = " ".join([h.get_text(strip=True) for h in headings if h.get_text(strip=True)])
            if len(heading_text) > len(text):
                text = heading_text
        
        if len(text) < 100:
            content_divs = soup.find_all("div", class_=re.compile(r"content|text|description|body|main", re.I))
            div_text = " ".join([d.get_text(strip=True) for d in content_divs if d.get_text(strip=True)])
            if len(div_text) > len(text):
                text = div_text
    
    if len(text) < 50:
        body = soup.find("body")
        if body:
            text = " ".join(body.get_text(separator=" ", strip=True).split())
    
    checksum = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return Page(url=url, title=title, text=text, checksum=checksum, fetched_at=time.time())


def fetch_sitemap_urls(sitemap_url: str, base_domain: str) -> List[str]:
    """Fetch URLs from sitemap.xml."""
    urls: List[str] = []
    try:
        xml = fetch(sitemap_url)
    except Exception:
        return urls
    for loc in re.findall(r"<loc>(.*?)</loc>", xml):
        loc = loc.strip()
        if is_allowed(loc, base_domain):
            urls.append(loc)
    return urls


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


def crawl(seed_urls: Iterable[str], base_domain: str, root_url: str, business_id: Optional[str] = None) -> List[Page]:
    """Crawl website starting from seed URLs."""
    seen: Set[str] = set()
    q: queue.Queue = queue.Queue()
    started = time.time()
    last_status_update = started
    fetch_errors = []
    
    for s in seed_urls:
        q.put((s, 0))
    pages: List[Page] = []

    while not q.empty() and len(pages) < MAX_PAGES:
        elapsed = time.time() - started
        if elapsed > MAX_SECONDS:
            break
        
        if q.qsize() > MAX_QUEUE_SIZE:
            break
        
        if business_id and (time.time() - last_status_update) > 10:
            progress = min(20 + int((len(pages) / MAX_PAGES) * 20), 40)
            error_msg = f"Scraping... Fetched {len(pages)} pages. Queue: {q.qsize()}"
            if fetch_errors:
                error_msg += f". Errors: {len(fetch_errors)}"
            update_status(business_id, "scraping", error_msg, progress)
            last_status_update = time.time()
        
        url, depth = q.get()
        if url in seen or depth > MAX_DEPTH:
            continue
        seen.add(url)
        
        html = None
        try:
            html = fetch(url)
            page = extract(url, html)
            if page.text and len(page.text.strip()) >= 50:  # Require at least 50 chars
                pages.append(page)
                print(f"  ✓ Fetched: {url} ({len(page.text)} chars)")
            else:
                print(f"  ⚠ Skipped (too little text): {url} ({len(page.text)} chars)")
            time.sleep(0.1)
        except Exception as e:
            error_msg = f"{url}: {str(e)[:100]}"
            fetch_errors.append(error_msg)
            if len(fetch_errors) <= 5:  # Only log first 5 errors
                print(f"  ✗ Error fetching {url}: {e}")
            continue

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
        status_msg = f"Finished scraping. Fetched {len(pages)} pages."
        if fetch_errors and len(pages) == 0:
            status_msg += f" Errors encountered: {fetch_errors[0] if fetch_errors else 'Unknown error'}"
        update_status(business_id, "scraping", status_msg, 40)
    
    if len(pages) == 0 and fetch_errors:
        print(f"\n[ERROR] Failed to fetch any pages. Sample errors:")
        for err in fetch_errors[:5]:
            print(f"  - {err}")
    
    return pages


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
    
    update_status(business_id, "scraping", "Scraping website content...", 20)
    pages = crawl(seeds, base_domain, root_url, business_id)
    print(f"\n[SUCCESS] Fetched {len(pages)} pages")
    
    if not pages:
        update_status(business_id, "failed", "No pages fetched.", 0)
        raise RuntimeError("No pages fetched.")
    
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
                "category": page.category or "General",
            })
        all_vectors.append(vectors)
        
        processed += 1
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
