"""
Semantic product search using gemini-embedding-2-preview (Vertex AI backend).

Products are embedded at startup using ADC credentials + GOOGLE_CLOUD_PROJECT.
Embeddings are cached to disk so there is no re-computation on restart.
At query time the user's text query is embedded and compared to the
catalogue via cosine similarity to find the best matching product.
"""

import os
import json
import pickle
import numpy as np
from pathlib import Path
from typing import Optional

from google import genai
from google.genai import types as genai_types

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).parent.parent.parent  # geminAIse/
_DATA_DIR = _ROOT / "data"
_PRODUCTS_JSON = _DATA_DIR / "products.json"
_CACHE_FILE = _DATA_DIR / "product_embeddings.pkl"

_EMBEDDING_MODEL = "gemini-embedding-2-preview"

# ---------------------------------------------------------------------------
# Global in-memory store
# ---------------------------------------------------------------------------
_product_embeddings: list[dict] = []   # [{product, embedding}, ...]
_client: Optional[genai.Client] = None


def _get_client() -> genai.Client:
    """Lazily initialise the Vertex AI client."""
    global _client
    if _client is None:
        # main.py renames these to GEMINAISE_GCP_* to avoid ADK routing them to Vertex AI Live.
        # When running standalone (e.g. precompute script), the standard names are used.
        project = os.getenv("GEMINAISE_GCP_PROJECT") or os.getenv("GOOGLE_CLOUD_PROJECT")
        location = os.getenv("GEMINAISE_GCP_LOCATION") or os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        if not project:
            raise RuntimeError("GOOGLE_CLOUD_PROJECT environment variable is not set.")
        _client = genai.Client(vertexai=True, project=project, location=location)
        print(f"[SemanticSearch] Vertex AI client initialised. project={project}, location={location}")
    return _client


def _embed_text(text: str) -> np.ndarray:
    """Return a normalised embedding vector for a text string."""
    client = _get_client()
    result = client.models.embed_content(
        model=_EMBEDDING_MODEL,
        contents=text,
        config=genai_types.EmbedContentConfig(task_type="SEMANTIC_SIMILARITY"),
    )
    vec = np.array(result.embeddings[0].values, dtype=np.float32)
    return vec / (np.linalg.norm(vec) + 1e-10)


def precompute_product_embeddings(force: bool = False) -> None:
    """
    Compute and cache embeddings for all products.
    Each product text: "name — category (brand)"
    Skips computation if a valid cache already exists (unless force=True).
    """
    global _product_embeddings

    if not force and _CACHE_FILE.exists():
        print("[SemanticSearch] Loading embeddings from cache…")
        with open(_CACHE_FILE, "rb") as f:
            _product_embeddings = pickle.load(f)
        print(f"[SemanticSearch] Loaded {len(_product_embeddings)} product embeddings.")
        return

    with open(_PRODUCTS_JSON) as f:
        products = json.load(f)

    print(f"[SemanticSearch] Embedding {len(products)} products with {_EMBEDDING_MODEL}…")
    _product_embeddings = []
    for p in products:
        text = f"{p['name']} — category: {p.get('category', '')} — brand: {p.get('brand', '')}"
        print(f"  → {p['name']}")
        vec = _embed_text(text)
        _product_embeddings.append({"product": p, "embedding": vec})

    _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_CACHE_FILE, "wb") as f:
        pickle.dump(_product_embeddings, f)
    print(f"[SemanticSearch] Done. Cache saved to {_CACHE_FILE}")


def find_best_product(query_text: str) -> dict:
    """
    Embed a free-text query and return the most similar product dict.

    Args:
        query_text:  Natural language description, e.g. "something sporty and casual".

    Returns:
        The matching product dict from products.json, with an extra 'score' key.
    """
    global _product_embeddings

    if not _product_embeddings:
        precompute_product_embeddings()

    query_vec = _embed_text(query_text)

    scores = [
        float(np.dot(query_vec, entry["embedding"]))
        for entry in _product_embeddings
    ]
    best_idx = int(np.argmax(scores))
    best = dict(_product_embeddings[best_idx]["product"])
    best["score"] = scores[best_idx]
    print(f"[SemanticSearch] '{query_text}' → '{best['name']}' (score={best['score']:.3f})")
    return best
