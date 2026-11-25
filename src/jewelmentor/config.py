"""Environment configuration. Secrets never participate in repr or public metadata."""

import os
from pathlib import Path
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str = "demo"
    db_path: Path = Path("runtime/jewelmentor.db")
    api_key: SecretStr = Field(default_factory=lambda: SecretStr(""), repr=False)
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    node_timeout: float = Field(default=20, gt=0, le=120)
    turn_timeout: float = Field(default=60, gt=0, le=300)
    max_attempts: int = Field(default=2, ge=1, le=4)
    retry_delay: float = Field(default=0.25, ge=0, le=5)
    max_hops: int = Field(default=4, ge=1, le=8)

    @model_validator(mode="after")
    def validate_provider(self):
        if self.provider not in {"demo", "openai"}:
            raise ValueError("provider must be demo or openai")
        if self.provider == "openai":
            if not self.api_key.get_secret_value().strip():
                raise ValueError("OPENAI_API_KEY is required for live mode")
            parsed = urlparse(self.base_url)
            if parsed.username or parsed.password or parsed.query or parsed.fragment:
                raise ValueError("base URL must not contain credentials, query or fragment")
            if parsed.scheme != "https" and not (
                parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
            ):
                raise ValueError("remote providers require HTTPS")
            if not parsed.hostname:
                raise ValueError("base URL requires a hostname")
        return self

    @classmethod
    def from_env(cls):
        fields = {
            "provider": "JEWELMENTOR_PROVIDER",
            "db_path": "JEWELMENTOR_DB",
            "api_key": "OPENAI_API_KEY",
            "base_url": "OPENAI_BASE_URL",
            "model": "OPENAI_MODEL",
            "node_timeout": "JEWELMENTOR_NODE_TIMEOUT",
            "turn_timeout": "JEWELMENTOR_TURN_TIMEOUT",
        }
        return cls(**{key: os.environ[env] for key, env in fields.items() if env in os.environ})
