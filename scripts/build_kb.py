"""
Builds a local RAG corpus and FAISS index for warmprospect.com.

Steps:
1) Crawl warmprospect.com up to depth 5.
2) Extract main text and metadata.
3) Chunk content.
4) Embed with Gemini text-embedding-004.
5) Persist FAISS index + metadata JSONL under data/.
"""

import hashlib
import json
import os
import queue
import re
import time
from dataclasses import dataclass
from typing import List, Dict, Set, Iterable

import faiss
import numpy as np
import requests
from bs4 import BeautifulSoup
from google import genai
from dotenv import load_dotenv
from urllib.parse import urlparse


BASE_DOMAIN = "warmprospect.com"
ROOT_URL = "https://warmprospect.com/"
MAX_DEPTH = 5
MAX_PAGES = 200  # safety cap
MAX_SECONDS = 120  # fail-safe wall clock limit
OUTPUT_DIR = "data"
META_PATH = os.path.join(OUTPUT_DIR, "meta.jsonl")
INDEX_PATH = os.path.join(OUTPUT_DIR, "index.faiss")
META_PATH_TMP = os.path.join(OUTPUT_DIR, "meta.jsonl.tmp")
INDEX_PATH_TMP = os.path.join(OUTPUT_DIR, "index.faiss.tmp")
CHUNK_SIZE = 800  # tokens (approx by words)
CHUNK_OVERLAP = 100
EMBED_MODEL = "text-embedding-004"
SEED_URLS = [
    ROOT_URL,  # start at home and follow discovered links
]
SITEMAP_URL = "https://warmprospect.com/wp-sitemap.xml"


@dataclass
class Page:
    url: str
    title: str
    text: str
    checksum: str
    fetched_at: float


def normalize_url(url: str) -> str:
    if url.startswith("//"):
        url = "https:" + url
    if url.startswith("/"):
        url = ROOT_URL.rstrip("/") + url
    return url.split("#")[0].strip()


def is_allowed(url: str) -> bool:
    if not url.startswith("http"):
        return False
    parsed = urlparse(url)
    if parsed.hostname is None:
        return False
    # allow only main domain, block app subdomain
    if parsed.hostname == BASE_DOMAIN:
        return True
    return False


def fetch(url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; WarmProspectBot/1.0; +https://warmprospect.com/)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    resp = requests.get(url, timeout=(3, 10), headers=headers, allow_redirects=True)
    resp.raise_for_status()
    return resp.text


def extract(url: str, html: str) -> Page:
    soup = BeautifulSoup(html, "html.parser")
    title = (soup.title.string or "").strip() if soup.title else ""

    for tag in soup(["script", "style", "noscript", "iframe"]):
        tag.decompose()
    text = " ".join(soup.get_text(separator=" ", strip=True).split())
    checksum = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return Page(url=url, title=title, text=text, checksum=checksum, fetched_at=time.time())


def fetch_sitemap_urls() -> List[str]:
    urls: List[str] = []
    try:
        xml = fetch(SITEMAP_URL)
    except Exception as e:
        print(f"Skip sitemap ({SITEMAP_URL}): {e}")
        return urls
    # simple regex parse for <loc>...</loc>
    for loc in re.findall(r"<loc>(.*?)</loc>", xml):
        loc = loc.strip()
        if is_allowed(loc):
            urls.append(loc)
    return urls


def crawl(seed_urls: Iterable[str]) -> List[Page]:
    seen: Set[str] = set()
    q: queue.Queue = queue.Queue()
    started = time.time()
    # seed queue
    for s in seed_urls:
        q.put((s, 0))
    pages: List[Page] = []

    while not q.empty() and len(pages) < MAX_PAGES:
        if time.time() - started > MAX_SECONDS:
            print("Stopping crawl due to time limit.")
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
            time.sleep(0.3)  # polite delay
        except Exception as e:
            print(f"Skip {url}: {e}")
            continue

        # enqueue links
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            nxt = normalize_url(a["href"])
            if is_allowed(nxt) and nxt not in seen:
                q.put((nxt, depth + 1))
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
        time.sleep(0.3)  # simple throttle
    return np.stack(vectors)


def build():
    # Load .env if present so GEMINI_API_KEY is available in local dev
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is required.")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Prefer sitemap URLs; fallback to crawl from root
    seeds = fetch_sitemap_urls()
    if seeds:
        print(f"Using sitemap URLs ({len(seeds)}) as seeds.")
    else:
        print("Sitemap unavailable; crawling from root.")
        seeds = SEED_URLS

    print("Crawling...")
    pages = crawl(seeds)
    print(f"Fetched {len(pages)} pages")

    if not pages:
        raise RuntimeError("No pages fetched (possible 403). Try again or check site access.")

    client = genai.Client(api_key=api_key)

    meta_records = []
    all_vectors = []

    # Load previous checksums to skip unchanged pages
    previous_checksums: Dict[str, str] = {}
    if os.path.exists(META_PATH):
        try:
            with open(META_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    rec = json.loads(line)
                    # store by page url checksum (page-level)
                    previous_checksums[rec.get("url", "")] = rec.get("checksum", "")
        except Exception:
            pass

    for page in pages:
        # skip unchanged pages
        if previous_checksums.get(page.url) == page.checksum:
            # reuse previous metadata and skip embedding to save quota
            continue

        chunks = chunk_text(page.text)
        if not chunks:
            continue
        vectors = embed_chunks(client, chunks)
        for i, ch in enumerate(chunks):
            meta_records.append(
                {
                    "url": page.url,
                    "title": page.title,
                    "text": ch,
                    "checksum": page.checksum,
                    "fetched_at": page.fetched_at,
                    "chunk_id": f"{page.url}#chunk-{i}",
                }
            )
        all_vectors.append(vectors)

    # If no new/changed pages, reuse old index/meta
    if not meta_records and os.path.exists(INDEX_PATH) and os.path.exists(META_PATH):
        print("No new/changed pages. Keeping existing index.")
        return

    if not meta_records:
        raise RuntimeError("No chunks to index.")

    embeddings = np.vstack(all_vectors)
    index = faiss.IndexFlatL2(embeddings.shape[1])
    index.add(embeddings)

    faiss.write_index(index, INDEX_PATH_TMP)
    with open(META_PATH_TMP, "w", encoding="utf-8") as f:
        for rec in meta_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # atomic swap
    os.replace(INDEX_PATH_TMP, INDEX_PATH)
    os.replace(META_PATH_TMP, META_PATH)

    print(f"Index written to {INDEX_PATH}, meta to {META_PATH}")


if __name__ == "__main__":
    build()

