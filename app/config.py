"""Application settings, loaded from environment / .env.

PROVIDER picks the model backend for both halves of the pipeline:
  - "ollama" (default): free, local — llama3.1 + HuggingFace embeddings
  - "claude": Anthropic Claude + Voyage embeddings (needs API keys)
  - "openai": any OpenAI-compatible endpoint — OpenAI itself by default, or
    Groq / Together / DeepSeek / vLLM / TGI / LM Studio via OPENAI_BASE_URL

The two halves are independent. LLM_PROVIDER and EMBED_PROVIDER each override
PROVIDER for their own half, so a local generator can run against cloud
embeddings or the reverse. Unset (the default), both follow PROVIDER and the
single-switch behaviour is unchanged.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent

ProviderName = Literal["ollama", "claude", "openai"]

# Hosts that are this machine (or the machine hosting the container). An
# OpenAI-compatible server here is vLLM / TGI / LM Studio / Ollama, not a vendor,
# so LOCAL_ONLY must not refuse it. See app/providers.py.
LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "0.0.0.0", "host.docker.internal"})


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- provider selection ---
    provider: ProviderName = "ollama"
    # Per-half overrides. Empty (the default) means "follow PROVIDER", which keeps every
    # existing single-switch .env working untouched. Set either to mix backends, e.g.
    # LLM_PROVIDER=claude with EMBED_PROVIDER=ollama.
    llm_provider: Literal["", "ollama", "claude", "openai"] = ""
    embed_provider: Literal["", "ollama", "claude", "openai"] = ""
    # Fully-local guard: when true (default), any cloud provider is refused for the half
    # that selects it, even if PROVIDER names it. Set LOCAL_ONLY=false to allow cloud.
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

    # --- OpenAI-compatible endpoints ---
    # One adapter, many vendors: everything below speaks the same wire format, so the
    # only thing that changes between OpenAI, Groq, Together, DeepSeek, Mistral, vLLM,
    # TGI and LM Studio is the base URL and the model id.
    openai_api_key: str = ""
    openai_base_url: str = ""  # "" -> the vendor default (api.openai.com)
    openai_llm_model: str = "gpt-4o-mini"
    openai_embed_model: str = "text-embedding-3-small"

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

    # --- the two halves of the provider seam ---

    @property
    def active_llm_provider(self) -> ProviderName:
        return self.llm_provider or self.provider

    @property
    def active_embed_provider(self) -> ProviderName:
        return self.embed_provider or self.provider

    @property
    def active_llm_model(self) -> str:
        return {
            "ollama": self.ollama_llm_model,
            "claude": self.anthropic_model,
            "openai": self.openai_llm_model,
        }[self.active_llm_provider]

    @property
    def active_embed_model(self) -> str:
        return {
            "ollama": self.hf_embed_model,
            "claude": self.voyage_model,
            "openai": self.openai_embed_model,
        }[self.active_embed_provider]

    @property
    def active_collection_name(self) -> str:
        """Chroma collection for the *current embedding model*.

        A vector only means anything to the model that produced it. With a fixed
        collection name, changing HF_EMBED_MODEL re-opened the previous model's
        collection: at a different dimensionality Chroma raises, and — far worse — at
        the same dimensionality it does not, and every subsequent answer is retrieved
        from vectors the new model never made. Keying the collection on the embedding
        provider and model turns that silent corruption into a fresh, empty collection
        that /health reports as needing an ingest.

        A hash, not the model id: HuggingFace ids are unbounded and Chroma caps a
        collection name at 63 characters. The mapping is logged on ingest.
        """
        fingerprint = f"{self.active_embed_provider}:{self.active_embed_model}"
        digest = hashlib.sha256(fingerprint.encode()).hexdigest()[:12]
        # The configured base name is user-supplied; keep it to Chroma's charset and
        # leave room for the suffix.
        base = re.sub(r"[^a-zA-Z0-9_-]", "_", self.collection_name)[:40].strip("._-")
        return f"{base or 'corpus'}_{digest}"


settings = Settings()
