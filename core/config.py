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
    
    @model_validator(mode="after")
    def parse_log_channel_and_topic(self):
        """Parse LOG_CHANNEL_ID which may contain 'channel_id:topic_id'."""
        raw = self.log_channel_id
        if raw is None or raw == "":
            self._parsed_channel_id = None
            self._parsed_topic_id = None
            return self
        
        if ":" in raw:
            parts = raw.split(":")
            try:
                self._parsed_channel_id = int(parts[0])
                self._parsed_topic_id = int(parts[1])
            except (ValueError, IndexError):
                self._parsed_channel_id = None
                self._parsed_topic_id = None
        else:
            try:
                self._parsed_channel_id = int(raw)
            except ValueError:
                self._parsed_channel_id = None
            self._parsed_topic_id = None
        
        return self
    
    model_config = {
        "env_file": os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


# Singleton settings instance
settings = Settings()
