"""
ProductMind AI — Central AI & LLM Settings
Configures Google Gemini and future LLM providers via environment variables.
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional
from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.ai.exceptions import AIConfigurationException

# Load environment safely from backend/.env or root .env
current_dir = Path(__file__).resolve().parent
backend_env = current_dir.parent.parent / ".env"
root_env = current_dir.parent.parent.parent / ".env"

for env_path in [backend_env, root_env]:
    if env_path.exists():
        load_dotenv(env_path, override=False)


class AISettings(BaseSettings):
    """
    Central AI configuration model.
    Validated at runtime with secure masking of credentials.
    """

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    GOOGLE_API_KEY: Optional[str] = Field(default=None, alias="GOOGLE_API_KEY")
    OPENROUTER_API_KEY: Optional[str] = Field(default=None, alias="OPENROUTER_API_KEY")
    GROQ_API_KEY: Optional[str] = Field(default=None, alias="GROQ_API_KEY")
    AI_PROVIDER: str = Field(default="google", alias="AI_PROVIDER")
    AI_MODEL: str = Field(default="gemini-3.8-flash", alias="AI_MODEL")
    AI_TEMPERATURE: float = Field(default=0.2, alias="AI_TEMPERATURE", ge=0.0, le=2.0)
    AI_MAX_OUTPUT_TOKENS: int = Field(default=4096, alias="AI_MAX_OUTPUT_TOKENS", gt=0)
    AI_TIMEOUT_SECONDS: int = Field(default=60, alias="AI_TIMEOUT_SECONDS", gt=0)
    AI_MAX_RETRIES: int = Field(default=2, alias="AI_MAX_RETRIES", ge=0)

    @field_validator("AI_PROVIDER")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        allowed = {"google", "openrouter", "groq"}
        if v.lower() not in allowed:
            raise ValueError(f"Unsupported AI_PROVIDER '{v}'. Currently supported: {allowed}")
        return v.lower()

    @property
    def is_configured(self) -> bool:
        """
        Returns True if the required credentials for the active provider are present and valid.
        Never checks raw value against placeholder patterns.
        """
        if self.AI_PROVIDER == "google":
            key = self.GOOGLE_API_KEY
            if not key or not key.strip():
                return False
            # Check for dummy placeholder string from .env.example
            if key.strip().lower() in {"your_google_api_key", "your_api_key", "placeholder"}:
                return False
            return True
        elif self.AI_PROVIDER == "openrouter":
            key = self.OPENROUTER_API_KEY
            if not key or not key.strip():
                return False
            if key.strip().lower() in {"your_openrouter_api_key", "your_api_key", "placeholder"}:
                return False
            return True
        elif self.AI_PROVIDER == "groq":
            key = self.GROQ_API_KEY
            if not key or not key.strip():
                return False
            if key.strip().lower() in {"your_groq_api_key", "your_api_key", "placeholder"}:
                return False
            return True
        return False

    def validate_for_execution(self) -> None:
        """
        Raises AIConfigurationException if credentials for active provider are absent.
        Provides a safe, user-friendly error message without leaking sensitive info.
        """
        if not self.is_configured:
            if self.AI_PROVIDER == "google":
                raise AIConfigurationException(
                    "Google Gemini API key is not configured. "
                    "Please set the GOOGLE_API_KEY environment variable in your backend .env file.",
                    provider="google",
                )
            elif self.AI_PROVIDER == "openrouter":
                raise AIConfigurationException(
                    "OpenRouter API key is not configured. "
                    "Please set the OPENROUTER_API_KEY environment variable in your backend .env file.",
                    provider="openrouter",
                )
            elif self.AI_PROVIDER == "groq":
                raise AIConfigurationException(
                    "Groq API key is not configured. "
                    "Please set the GROQ_API_KEY environment variable in your backend .env file.",
                    provider="groq",
                )
            raise AIConfigurationException(
                f"Active provider '{self.AI_PROVIDER}' is not configured.",
                provider=self.AI_PROVIDER,
            )

    def safe_dict(self) -> Dict[str, Any]:
        """
        Returns sanitized configuration dictionary.
        Guarantees that GOOGLE_API_KEY is never exposed.
        """
        return {
            "provider": self.AI_PROVIDER,
            "model": self.AI_MODEL,
            "is_configured": self.is_configured,
            "temperature": self.AI_TEMPERATURE,
            "max_output_tokens": self.AI_MAX_OUTPUT_TOKENS,
            "timeout_seconds": self.AI_TIMEOUT_SECONDS,
            "max_retries": self.AI_MAX_RETRIES,
        }


# Global AI configuration singleton instance
ai_settings = AISettings()

