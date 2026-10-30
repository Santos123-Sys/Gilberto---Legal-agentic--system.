"""
config.py — Application Settings
═══════════════════════════════════════════════════════════════════════
Centralized configuration with environment variable support.
"""

import os
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # ── LLM Provider ─────────────────────────
    MARITACA_API_KEY: str = os.getenv("MARITACA_API_KEY", "")
    MARITACA_BASE_URL: str = os.getenv(
        "MARITACA_BASE_URL", "https://chat.maritaca.ai/api"
    )
    MARITACA_MODEL: str = os.getenv("MARITACA_MODEL", "sabia-4")
    TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.1"))
    MAX_TOKENS: int = int(os.getenv("MAX_TOKENS", "4096"))

    # Backup provider requires explicit operator allowlist and user consent.
    # No failover or retry after an uncertain Maritaca execution.
    FALLBACK_LLM_API_KEY: str = ""
    FALLBACK_LLM_BASE_URL: str = ""
    FALLBACK_LLM_MODEL: str = ""
    FALLBACK_LLM_REASONING_EFFORT: str = "medium"
    # Reasoning tokens count toward completion tokens for supported chat models.
    FALLBACK_LLM_MAX_COMPLETION_TOKENS: int = Field(default=8192, ge=1024, le=128000)
    FALLBACK_LLM_ALLOWED_HOSTS: str = ""
    FALLBACK_LLM_INPUT_PRICE_USD_PER_1M: float = Field(default=0.0, ge=0, le=1000000)
    FALLBACK_LLM_OUTPUT_PRICE_USD_PER_1M: float = Field(default=0.0, ge=0, le=1000000)

    # Managed OIDC or invite-only local accounts. Never fall back to anonymous.
    AUTH_MODE: str = "oidc"
    LOCAL_AUTH_APP_ORIGIN: str = ""
    LOCAL_AUTH_PROXY_SECRET: str = ""
    LOCAL_AUTH_COOKIE_SECURE: bool = True
    LOCAL_BOOTSTRAP_TOKEN_SHA256: str = ""
    LOCAL_BOOTSTRAP_EXPIRES_AT: int = 0

    # OIDC API verifier (never allow anonymous fallback).
    OIDC_ISSUER: str = ""
    OIDC_AUDIENCE: str = ""
    OIDC_JWKS_URL: str = ""

    # ── Server ───────────────────────────────
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    CORS_ORIGINS: str = os.getenv(
        "CORS_ORIGINS", "http://localhost:5173,http://localhost:3000"
    )

    # ── Debate Engine ────────────────────────
    MAX_ROUNDS: int = int(os.getenv("MAX_ROUNDS", "3"))
    DEFAULT_AGENTS: int = int(os.getenv("DEFAULT_AGENTS", "20"))
    DEFAULT_ROUNDS: int = int(os.getenv("DEFAULT_ROUNDS", "1"))

    # ── Human Feedback Gates ─────────────────
    GATE_1_CONFIDENCE_THRESHOLD: float = float(
        os.getenv("GATE_1_CONFIDENCE_THRESHOLD", "3.0")
    )
    GATE_2_DEVIL_ADVOCATE_THRESHOLD: float = float(
        os.getenv("GATE_2_DEVIL_ADVOCATE_THRESHOLD", "6.0")
    )
    GATE_3_ALWAYS_FOR_CRITICO: bool = os.getenv(
        "GATE_3_ALWAYS_FOR_CRITICO", "true"
    ).lower() == "true"

    # ── Cluster Configuration ────────────────
    ACTIVE_CLUSTERS: str = os.getenv(
        "ACTIVE_CLUSTERS",
        "foundation,financial_risk,mitigation_exit,compliance,strategy",
    )
    EXECUTION_MODE: str = os.getenv("EXECUTION_MODE", "parallel")

    # Pace provider traffic while keeping cluster orchestration parallel.
    LLM_MAX_CONCURRENT_CALLS: int = int(os.getenv("LLM_MAX_CONCURRENT_CALLS", "1"))
    LLM_MIN_REQUEST_INTERVAL_SECONDS: float = float(
        os.getenv("LLM_MIN_REQUEST_INTERVAL_SECONDS", "2.0")
    )
    LLM_INPUT_TOKENS_PER_MINUTE: int = int(
        os.getenv("LLM_INPUT_TOKENS_PER_MINUTE", "10000")
    )

    MAX_CONCURRENT_ANALYSES: int = Field(default=2, ge=1, le=20)
    MAX_MODEL_CALLS: int = Field(default=250, ge=1, le=1000)
    # Explicit US-dollar budget and published/configured rates. Zero means
    # price not configured; do not invent a price or claim cost observability.
    MAX_REVIEW_ESTIMATED_USD: float = Field(default=0.0, ge=0, le=1000000)
    LLM_INPUT_PRICE_USD_PER_1M: float = Field(default=0.0, ge=0, le=1000000)
    LLM_OUTPUT_PRICE_USD_PER_1M: float = Field(default=0.0, ge=0, le=1000000)
    MAX_FEEDBACK_ROUNDS: int = Field(default=2, ge=0, le=5)
    LLM_REQUEST_TIMEOUT_SECONDS: float = Field(default=120.0, gt=0, le=600)
    MAX_UPLOAD_BYTES: int = 10 * 1024 * 1024

    # ── Evidence store (ADR-001, PR-02) ──────
    # Empty = disabled. Not yet read by the request path: the SQLite session
    # checkpoints stay authoritative until the staged migration gates pass.
    EVIDENCE_DATABASE_URL: str = ""
    # Private directory for original documents; never a public bucket.
    EVIDENCE_OBJECT_STORE_PATH: str = ""

    # ── Observability ────────────────────────
    AGENTOPS_API_KEY: Optional[str] = os.getenv("AGENTOPS_API_KEY", None)
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    @property
    def active_clusters_list(self) -> List[str]:
        return [c.strip() for c in self.ACTIVE_CLUSTERS.split(",") if c.strip()]

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()

