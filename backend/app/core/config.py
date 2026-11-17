"""Runtime configuration (PRD §6.2). Every value can be set via environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", protected_namespaces=("settings_",)
    )

    app_name: str = "Fashion Visual Search API"
    environment: str = "development"

    # Model & artifacts
    model_name: str = "ViT-B-32-quickgelu"
    model_pretrained: str = "openai"
    artifacts_dir: Path = BACKEND_DIR / "artifacts"
    index_path: Path | None = None
    metadata_path: Path | None = None
    image_dir: Path | None = None
    evaluation_path: Path | None = None
    compatibility_path: Path = BACKEND_DIR / "app" / "data" / "compatibility.json"

    # API behaviour
    allowed_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173"]
    )
    max_upload_mb: float = 8.0
    max_query_chars: int = 200
    top_k_default: int = 24
    top_k_max: int = 100
    candidate_multiplier: int = 4

    # Ranking: final = alpha * cosine + beta * attribute_match (PRD §9.4)
    rank_alpha: float = 0.85
    rank_beta: float = 0.15

    # Security
    rate_limit: str = "60/minute"
    rate_limit_enabled: bool = True
    auth_enabled: bool = False
    demo_username: str = "demo"
    demo_password: str = ""
    session_secret: str = "change-me-in-production"
    session_max_age_s: int = 60 * 60 * 8
    cookie_secure: bool = False

    # Startup
    load_model_on_startup: bool = True

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def _split_origins(cls, v):
        if isinstance(v, str) and not v.strip().startswith("["):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @property
    def resolved_index_path(self) -> Path:
        return self.index_path or self.artifacts_dir / "index.faiss"

    @property
    def resolved_metadata_path(self) -> Path:
        return self.metadata_path or self.artifacts_dir / "metadata.json"

    @property
    def resolved_image_dir(self) -> Path:
        return self.image_dir or self.artifacts_dir / "images"

    @property
    def resolved_evaluation_path(self) -> Path:
        return self.evaluation_path or self.artifacts_dir / "evaluation.json"

    @property
    def max_upload_bytes(self) -> int:
        return int(self.max_upload_mb * 1024 * 1024)


@lru_cache
def get_settings() -> Settings:
    return Settings()
