"""
Application configuration using pydantic-settings.
All environment variables are validated and typed.
"""

import os
from pydantic_settings import BaseSettings
from pydantic import field_validator, model_validator


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Required tokens
    tg_token: str
    github_token: str
    
    # Gemini API keys (comma-separated)
    gemini_api_key: str = ""
    
    # Optional logging - raw value may contain "channel_id:topic_id"
    log_channel_id: str | None = None
    log_topic_id: int | None = None

    # Collector API (LK data)
    site_api_base_url: str | None = None
    site_api_key: str | None = None

    # Public WebApp URL for Telegram Mini App entry
    site_webapp_url: str | None = None

    # LK admin requests (raw "channel_id:topic_id")
    lk_admin_channel_id: str | None = None

    # Debug logging (raw "channel_id:topic_id")
    debug_channel_id: str | None = None

    # Admin user IDs (comma/space separated)
    admin_user_ids: str | None = None

    # Reminder timezone (IANA name, e.g. Europe/Moscow)
    reminder_timezone: str = "Europe/Moscow"
    
    # Webhook
    webhook_secret: str | None = None
    
    # Constants with defaults
    github_repo: str = "ckeiituk/iplist"
    github_branch: str = "master"
    gemini_model: str = "gemma-3-27b-it"
    dns_servers: list[str] = ["127.0.0.11:53", "77.88.8.88:53", "8.8.8.8:53", "1.1.1.1:53"]
    
    # Parsed values (set by model_validator)
    _parsed_channel_id: int | None = None
    _parsed_topic_id: int | None = None
    _parsed_lk_admin_channel_id: int | None = None
    _parsed_lk_admin_topic_id: int | None = None
    _parsed_debug_channel_id: int | None = None
    _parsed_debug_topic_id: int | None = None
    
    @property
    def gemini_api_keys(self) -> list[str]:
        """Parse comma-separated API keys."""
        keys = [k.strip() for k in self.gemini_api_key.split(",") if k.strip()]
        return keys if keys else [""]
    
    @property
    def channel_id(self) -> int | None:
        """Get parsed channel ID."""
        return self._parsed_channel_id
    
    @property
    def topic_id(self) -> int | None:
        """Get parsed topic ID."""
        return self._parsed_topic_id

    @property
    def lk_admin_channel(self) -> int | None:
        """Get parsed LK admin channel ID."""
        return self._parsed_lk_admin_channel_id

    @property
    def lk_admin_topic(self) -> int | None:
        """Get parsed LK admin topic ID."""
        return self._parsed_lk_admin_topic_id

    @property
    def debug_channel(self) -> int | None:
        """Get parsed debug channel ID."""
        return self._parsed_debug_channel_id

    @property
    def debug_topic(self) -> int | None:
        """Get parsed debug topic ID."""
        return self._parsed_debug_topic_id

    @staticmethod
    def _parse_int_list(raw: str | None) -> list[int]:
        if raw is None:
            return []
        tokens = str(raw).replace(",", " ").split()
        result: list[int] = []
        for token in tokens:
            try:
                result.append(int(token))
            except ValueError:
                continue
        return result

    @property
    def admin_ids(self) -> set[int]:
        """Get parsed admin user IDs."""
        return set(self._parse_int_list(self.admin_user_ids))

    @field_validator("site_webapp_url", mode="before")
    @classmethod
    def _normalize_webapp_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None

    @staticmethod
    def _parse_channel_with_topic(raw: str | None) -> tuple[int | None, int | None]:
        if raw is None or raw == "":
            return None, None

        if ":" in raw:
            parts = raw.split(":")
            try:
                return int(parts[0]), int(parts[1])
            except (ValueError, IndexError):
                return None, None

        try:
            return int(raw), None
        except ValueError:
            return None, None
    
    @model_validator(mode="after")
    def parse_log_channel_and_topic(self):
        """Parse LOG_CHANNEL_ID which may contain 'channel_id:topic_id'."""
        self._parsed_channel_id, self._parsed_topic_id = self._parse_channel_with_topic(self.log_channel_id)
        self._parsed_lk_admin_channel_id, self._parsed_lk_admin_topic_id = self._parse_channel_with_topic(
            self.lk_admin_channel_id
        )
        self._parsed_debug_channel_id, self._parsed_debug_topic_id = self._parse_channel_with_topic(
            self.debug_channel_id
        )
        return self
    
    model_config = {
        "env_file": os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


# Singleton settings instance
settings = Settings()
