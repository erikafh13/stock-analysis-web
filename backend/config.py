"""
backend/config.py
Konfigurasi terpusat dari environment variables.
"""

import os
import json
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # Auth
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key-ganti-di-production")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))

    # Users: "admin:hash1,user2:hash2"
    USERS_RAW: str = os.getenv("USERS", "")

    # Google Drive
    GOOGLE_SERVICE_ACCOUNT_JSON: str = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    FOLDER_PENJUALAN: str = os.getenv("FOLDER_PENJUALAN", "")
    FOLDER_PRODUK: str = os.getenv("FOLDER_PRODUK", "")
    FOLDER_STOCK: str = os.getenv("FOLDER_STOCK", "")
    FOLDER_HASIL_ANALISIS: str = os.getenv("FOLDER_HASIL_ANALISIS", "")

    # Supabase
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")

    # App
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    CORS_ORIGINS: list[str] = os.getenv(
        "CORS_ORIGINS", "http://localhost:5500,http://127.0.0.1:5500"
    ).split(",")

    @property
    def users_dict(self) -> dict[str, str]:
        """Return {username: hashed_password}"""
        result = {}
        for entry in self.USERS_RAW.split(","):
            entry = entry.strip()
            if ":" in entry:
                user, pw_hash = entry.split(":", 1)
                result[user.strip()] = pw_hash.strip()
        return result

    @property
    def service_account_info(self) -> dict | None:
        if not self.GOOGLE_SERVICE_ACCOUNT_JSON:
            return None
        try:
            return json.loads(self.GOOGLE_SERVICE_ACCOUNT_JSON)
        except Exception:
            return None


settings = Settings()
