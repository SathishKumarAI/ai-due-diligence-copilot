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
