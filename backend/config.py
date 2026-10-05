"""
config.py — Application Settings
═══════════════════════════════════════════════════════════════════════
Centralized configuration with environment variable support.
"""

import os
from typing import List, Optional
from pydantic_settings import BaseSettings


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
