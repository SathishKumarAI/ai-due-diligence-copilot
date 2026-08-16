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
    # Fully-local guard: when true (default), the Claude/Voyage cloud provider is refused
    # even if PROVIDER=claude. Set LOCAL_ONLY=false to allow the cloud path.
    local_only: bool = True

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
    # 400, not 1000. At 1000 every document in data/ fit inside a single chunk, so one
    # chunk was one document and each vector was a document-level average — a single line
    # like "Gross margin: 61%" was averaged into a whole pitch deck and the question
    # about it ranked that chunk 4th of 4. Measured, scoring dense retrieval against the
    # eval ground truth with no LLM in the loop:
    #
    #   chunk_size  chunks  dense hit@1  mean rank of expected
    #         1000       4         8/10                   1.40
    #          400      11         9/10                   1.10
    #          120      38        10/10                   1.00
    #
    # 120 scores best and is the wrong choice: every eval question is a single-fact
    # lookup, which structurally favours tiny chunks, and at top_k=5 it leaves the model
    # ~600 characters of context to answer from. 400 fixes the failure that mattered,
    # keeps ~2000 characters of context, and makes the retrieval hit-rate meaningful for
    # the first time (11 chunks against top_k=5 can actually miss; 4 could not).
    chunk_size: int = 400
    chunk_overlap: int = 80
    top_k: int = 5
    max_tokens: int = 2000

    # --- hybrid retrieval (F16) ---
    retrieval_mode: Literal["dense", "hybrid"] = "hybrid"
    retrieve_fetch_k: int = 20  # candidates each arm fetches before fusion / rerank
    # No single document may occupy more than this many of the top_k slots, when other
    # sources are available. Measured attack: uploading one document that produced 12
    # near-identical chunks filled all 5 retrieved slots and the answer became the
    # attacker's number, with all 5 citations pointing at the hostile file. No prompt
    # injection was needed - volume alone crowded the true document out of top_k.
    # Set to 0 to disable the cap.
    max_chunks_per_source: int = 2
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
