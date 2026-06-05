"""
KeepSafe Backend — Configuration

All secrets use {{PLACEHOLDER_*}} placeholders.
Overwrite via environment variables or .env file.
"""

from __future__ import annotations


from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── FastAPI ──
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "info"

    # ── Database ──
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "keepsafe"
    db_user: str = "keepsafe"
    db_password: str = "{{PLACEHOLDER_DB_PASSWORD}}"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def database_url_sync(self) -> str:
        return (
            f"postgresql+psycopg2://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    # ── Redis ──
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = "{{PLACEHOLDER_REDIS_PASSWORD}}"

    @property
    def redis_url(self) -> str:
        return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/0"

    # ── EMQX ──
    emqx_host: str = "localhost"
    emqx_port: int = 1883

    # ── Firebase Cloud Messaging ──
    fcm_credentials_path: str = "./credentials/firebase-service-account.json"

    # ── APNs ──
    apns_key_path: str = "./credentials/apns-key.p8"
    apns_key_id: str = "{{PLACEHOLDER_APNS_KEY_ID}}"
    apns_team_id: str = "{{PLACEHOLDER_APNS_TEAM_ID}}"
    apns_topic: str = "com.keepsafe.app"

    # ── LBS (OpenCellID) ──
    opencellid_api_key: str = "{{PLACEHOLDER_OPENCELLID_API_KEY}}"

    # ── MQTT Topics ──
    mqtt_topic_location: str = "keepsafe/v1/{device_id}/location"
    mqtt_topic_heartbeat: str = "keepsafe/v1/{device_id}/heartbeat"
    mqtt_topic_sos: str = "keepsafe/v1/{device_id}/sos"
    mqtt_topic_low_battery: str = "keepsafe/v1/{device_id}/alert/low_battery"
    mqtt_topic_version: str = "keepsafe/v1/{device_id}/version"

    # ── Cache TTLs ──
    device_status_ttl: int = 180      # seconds
    lbs_cache_ttl: int = 604800       # 7 days

    # ── JWT ──
    jwt_secret: str = "{{PLACEHOLDER_JWT_SECRET}}"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440  # 24 hours

    # ── LBS source ──
    lbs_source: str = "opencellid"    # "opencellid" | "baidu"

    # ── Dev Mode ──
    dev_mode: bool = False
    # When True: uses SQLite + fakeredis for local development
    # When False: uses PostgreSQL + Redis (production)

    # ── Chat Agent ──
    chat_api_key: str = "{{PLACEHOLDER_CHAT_API_KEY}}"
    # Shared secret for /chat/api/* endpoints. Set via CHAT_API_KEY env var.

    # ── CORS ──
    cors_origins: str = ""    # comma-separated list, e.g. "https://app.keepsafe.com,https://dashboard.keepsafe.com"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
