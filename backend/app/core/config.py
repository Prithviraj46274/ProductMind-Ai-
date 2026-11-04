"""
ProductMind AI — Backend Configuration Settings
Loads environment variables safely for MongoDB connection and lifecycle management.
"""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Try loading from backend/.env, then server/.env, then root .env
current_dir = Path(__file__).resolve().parent
backend_env = current_dir.parent.parent / ".env"
server_env = current_dir.parent.parent.parent / "server" / ".env"
root_env = current_dir.parent.parent.parent / ".env"

for env_path in [backend_env, server_env, root_env]:
    if env_path.exists():
        load_dotenv(env_path, override=False)


class Settings:
    MONGODB_URI: str = os.getenv("MONGODB_URI", "mongodb://127.0.0.1:27017/productmind_ai")
    DATABASE_NAME: str = os.getenv("DATABASE_NAME", "productmind_ai")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", os.getenv("NODE_ENV", "development"))
    
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

