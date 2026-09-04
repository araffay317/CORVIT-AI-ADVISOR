"""Configuration management for Corvit AI Advisor."""
from pathlib import Path
from typing import List
from pydantic import SecretStr, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Base project directory
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Application settings loaded securely from environment / .env."""
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # API Keys & Models
    GROQ_API_KEY: SecretStr = Field(default=SecretStr(""), description="Groq API key for inference")
    PRIMARY_MODEL: str = Field(default="openai/gpt-oss-120b", description="Primary AI model identifier")
    FALLBACK_MODEL: str = Field(default="llama-3.1-8b-instant", description="Fallback AI model identifier")

    # Server Configuration
    BACKEND_HOST: str = Field(default="0.0.0.0", description="Host address to bind to")
    BACKEND_PORT: int = Field(default=8000, description="Port number to listen on")
    CORS_ORIGINS: str = Field(
        default="http://localhost:5500,http://127.0.0.1:5500,http://localhost:3000,http://localhost:8000",
        description="Comma-separated list of allowed CORS origins"
    )

    # Feature Flags
    ENABLE_ONLINE_RESEARCH: bool = Field(default=True, description="Enable secondary web verification")

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse comma-separated CORS_ORIGINS into a clean list of allowed origins."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def dataset_dir(self) -> Path:
        """Resolve dataset directory path defensively (handles Dataset/ and dataset/)."""
        candidate_upper = BASE_DIR / "Dataset"
        candidate_lower = BASE_DIR / "dataset"
        if candidate_upper.is_dir():
            return candidate_upper
        if candidate_lower.is_dir():
            return candidate_lower
        return candidate_upper

    @property
    def assets_dir(self) -> Path:
        """Resolve assets directory path defensively (handles Assests/ and assets/)."""
        candidate_upper = BASE_DIR / "Assests"
        candidate_lower = BASE_DIR / "assets"
        if candidate_lower.is_dir():
            return candidate_lower
        if candidate_upper.is_dir():
            return candidate_upper
        return candidate_lower


# Global settings singleton
settings = Settings()
