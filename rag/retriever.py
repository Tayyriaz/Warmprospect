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
        enabled_categories: Optional[List[str]] = None,
    ) -> None:
        self.index_path = index_path
        self.meta_path = meta_path
        self.top_k = top_k
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.enabled_categories = enabled_categories  # List of enabled category names

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
        scores, idxs = self.index.search(np.expand_dims(vector, axis=0), self.top_k * 2)  # Get more results to filter
        hits = []
        for score, idx in zip(scores[0], idxs[0]):
            if idx < 0 or idx >= len(self.metadata):
                continue
            hit = dict(self.metadata[idx])
            
            # Filter by enabled categories if specified
            if self.enabled_categories is not None and len(self.enabled_categories) > 0:
                hit_category = hit.get("category", "General")
                if hit_category not in self.enabled_categories:
                    continue  # Skip this hit if category is not enabled
            
            hit["score"] = float(score)
            hits.append(hit)
            
            # Stop when we have enough hits
            if len(hits) >= self.top_k:
                break
        
        return hits


def format_context(hits: List[Dict[str, Any]]) -> Optional[str]:
    """
    Builds a concise context block without source citations.
    Sources are not included to prevent the AI from mentioning URLs or sources.
    """
    if not hits:
        return None
    lines = []
    for h in hits:
        snippet = h.get("text", "").strip()
        if len(snippet) > 500:
            snippet = snippet[:500] + "..."
        # Only include the text snippet, no source/URL information
        lines.append(f"- {snippet}")
    return "Context:\n" + "\n".join(lines)

