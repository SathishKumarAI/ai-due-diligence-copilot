"""Application settings, loaded from environment / .env.

A single PROVIDER switch picks the model backend:
  - "ollama" (default): free, local — llama3.1 + HuggingFace embeddings
  - "claude": Anthropic Claude + Voyage embeddings (needs API keys)
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- provider selection ---
    provider: Literal["ollama", "claude"] = "ollama"

    # --- open-source (Ollama + HuggingFace) ---
    ollama_base_url: str = "http://localhost:11434"
    ollama_llm_model: str = "llama3.1:8b"
    hf_embed_model: str = "BAAI/bge-small-en-v1.5"

    # --- compute device for embeddings / reranker (local path) ---
    # "auto" (cuda -> mps -> cpu), or force "cpu" | "cuda" | "mps". See app/device.py.
    embed_device: str = "auto"
    rerank_device: str = "auto"

    # --- Claude + Voyage ---
    anthropic_api_key: str = ""
    voyage_api_key: str = ""
    anthropic_model: str = "claude-opus-4-8"
    voyage_model: str = "voyage-3.5"

    # --- retrieval / generation ---
    chunk_size: int = 1000
    chunk_overlap: int = 150
    top_k: int = 5
    max_tokens: int = 2000

    # --- hybrid retrieval (F16) ---
    retrieval_mode: Literal["dense", "hybrid"] = "hybrid"
    retrieve_fetch_k: int = 20  # candidates each arm fetches before fusion / rerank
    rrf_k: int = 60  # Reciprocal Rank Fusion constant

    # --- re-ranking (F17) ---
    rerank_enabled: bool = False
    rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # --- upload (F18) ---
    max_upload_mb: int = 25

    # --- conversation memory (F19) ---
    history_max_turns: int = 6  # most recent turns kept when condensing follow-ups
    feedback_path: Path = PROJECT_ROOT / "data" / "feedback.jsonl"

    # --- OCR ingestion (F20; local Tesseract, no keys) ---
    ocr_enabled: bool = True  # OCR images + scanned PDFs during ingest
    ocr_lang: str = "eng"  # tesseract language pack(s), e.g. "eng+deu"
    ocr_dpi: int = 200  # rasterization DPI for scanned PDF pages
    ocr_min_chars_per_page: int = 40  # below this avg -> PDF treated as scanned

    # --- cleaning pipeline (F21) ---
    clean_enabled: bool = True  # normalize/strip noise between load and split
    dedupe_enabled: bool = True  # drop near-duplicate chunks after splitting
    dedupe_threshold: float = 0.9  # Jaccard(shingles) >= this => duplicate

    # --- storage ---
    data_dir: Path = PROJECT_ROOT / "data"
    chroma_dir: Path = PROJECT_ROOT / "chroma_db"
    collection_name: str = "due_diligence"

    # --- API / security ---
    api_key: str = ""  # if set, /v1/* requires matching X-API-Key header
    rate_limit_per_min: int = 60  # per API key (or client IP if no key)
    cors_origins: list[str] = ["*"]

    # --- caching ---
    cache_enabled: bool = True
    cache_dir: Path = PROJECT_ROOT / ".cache"
    cache_ttl_seconds: int = 3600

    # --- app meta ---
    app_name: str = "AI Due Diligence Copilot"
    app_version: str = "0.1.0"

    @property
    def auth_required(self) -> bool:
        return bool(self.api_key)


settings = Settings()
