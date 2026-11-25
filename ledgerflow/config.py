"""Runtime configuration loaded strictly from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment setting: {name}")
    return value


@dataclass(frozen=True)
class Settings:
    db_path: str
    jwt_issuer: str
    jwt_secret: str
    webhook_secret: str
    mailer_url: str
    mailer_api_key: str
    export_dir: str
    host: str = "127.0.0.1"
    port: int = 5050

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            db_path=os.environ.get("LEDGERFLOW_DB_PATH", "ledgerflow.db"),
            jwt_issuer=os.environ.get("LEDGERFLOW_JWT_ISSUER", "ledgerflow"),
            jwt_secret=_require_env("LEDGERFLOW_JWT_SECRET"),
            webhook_secret=_require_env("LEDGERFLOW_WEBHOOK_SECRET"),
            mailer_url=_require_env("LEDGERFLOW_MAILER_URL"),
            mailer_api_key=_require_env("LEDGERFLOW_MAILER_API_KEY"),
            export_dir=os.environ.get("LEDGERFLOW_EXPORT_DIR", "exports"),
            host=os.environ.get("LEDGERFLOW_HOST", "127.0.0.1"),
            port=int(os.environ.get("LEDGERFLOW_PORT", "5050")),
        )
