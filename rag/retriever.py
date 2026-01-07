import json
import os
from typing import List, Dict, Any, Optional

import faiss
import numpy as np
from google import genai


class GoAccelRetriever:
    """
    Lightweight retriever that loads a FAISS index and associated metadata.
    """

    def __init__(
        self,
        api_key: str,
        index_path: str = "data/index.faiss",
        meta_path: str = "data/meta.jsonl",
        model: str = "text-embedding-004",
        top_k: int = 8,
    ) -> None:
        self.index_path = index_path
        self.meta_path = meta_path
        self.top_k = top_k
        self.client = genai.Client(api_key=api_key)
        self.model = model

        if not os.path.exists(self.index_path) or not os.path.exists(self.meta_path):
            raise FileNotFoundError("RAG index not found. Please run the index build script.")

        self.index = faiss.read_index(self.index_path)
        self.metadata = self._load_metadata()

    def _load_metadata(self) -> List[Dict[str, Any]]:
        records = []
        with open(self.meta_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return records

    def embed(self, text: str) -> np.ndarray:
        try:
            emb = self.client.models.embed_content(
                model=self.model,
                content=text,
            )
        except TypeError:
            emb = self.client.models.embed_content(
                model=self.model,
                contents=text,
            )
        return np.array(emb.embeddings[0].values, dtype="float32")

    def search(self, query: str) -> List[Dict[str, Any]]:
        if not query.strip():
            return []
        vector = self.embed(query)
        scores, idxs = self.index.search(np.expand_dims(vector, axis=0), self.top_k)
        hits = []
        for score, idx in zip(scores[0], idxs[0]):
            if idx < 0 or idx >= len(self.metadata):
                continue
            hit = dict(self.metadata[idx])
            hit["score"] = float(score)
            hits.append(hit)
        return hits


def format_context(hits: List[Dict[str, Any]]) -> Optional[str]:
    """
    Builds a concise context block with citations.
    """
    if not hits:
        return None
    lines = []
    for h in hits:
        snippet = h.get("text", "").strip()
        url = h.get("url", "")
        title = h.get("title", "")
        if len(snippet) > 500:
            snippet = snippet[:500] + "..."
        cite = url or title
        lines.append(f"- {snippet} (source: {cite})")
    return "Context:\n" + "\n".join(lines)

