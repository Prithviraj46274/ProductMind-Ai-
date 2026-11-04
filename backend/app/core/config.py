"""
ProductMind AI — Central Application Configuration Settings
Loads environment variables safely for FastAPI, CORS, and database lifecycle management.
"""

import os
from pathlib import Path
from typing import List
from dotenv import load_dotenv

# Try loading from backend/.env, then root .env
current_dir = Path(__file__).resolve().parent
backend_env = current_dir.parent.parent / ".env"
root_env = current_dir.parent.parent.parent / ".env"

for env_path in [backend_env, root_env]:
    if env_path.exists():
        load_dotenv(env_path, override=False)


class Settings:
    # API Metadata
    PROJECT_NAME: str = "ProductMind AI"
    DESCRIPTION: str = "Production-grade AI Product Manager Copilot API providing customer feedback analysis, algorithmic prioritization, and automated PRD generation."
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", os.getenv("NODE_ENV", "development"))

    # CORS Origins (Environment-driven, safe development defaults, no guessed production domains)
    @property
    def CORS_ORIGINS(self) -> List[str]:
        raw_origins = os.getenv("CORS_ORIGINS", "")
        if raw_origins:
            return [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
        # Default local development origins
        return [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]

    # Database Settings
    MONGODB_URI: str = os.getenv("MONGODB_URI", "mongodb://127.0.0.1:27017/productmind_ai")
    DATABASE_NAME: str = os.getenv("DATABASE_NAME", "productmind_ai")
    
    # Connection Pool Settings
    MONGO_MAX_POOL_SIZE: int = int(os.getenv("MONGO_MAX_POOL_SIZE", "50"))
    MONGO_MIN_POOL_SIZE: int = int(os.getenv("MONGO_MIN_POOL_SIZE", "5"))
    MONGO_SERVER_SELECTION_TIMEOUT_MS: int = int(os.getenv("MONGO_SERVER_SELECTION_TIMEOUT_MS", "5000"))
    MONGO_SOCKET_TIMEOUT_MS: int = int(os.getenv("MONGO_SOCKET_TIMEOUT_MS", "45000"))
    
    # Retention
    ANALYTICS_EVENT_RETENTION_DAYS: int = int(os.getenv("ANALYTICS_EVENT_RETENTION_DAYS", "90"))
    AUDIT_LOG_RETENTION_DAYS: int = int(os.getenv("AUDIT_LOG_RETENTION_DAYS", "180"))
    AUTH_SESSION_RETENTION_DAYS: int = int(os.getenv("AUTH_SESSION_RETENTION_DAYS", "30"))


settings = Settings()
