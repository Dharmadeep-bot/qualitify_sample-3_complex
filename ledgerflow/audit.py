"""Redacted structured audit trail helper."""

from __future__ import annotations

import json
import logging
import time
from typing import Optional

from ledgerflow.db import Database

log = logging.getLogger(__name__)
_SENSITIVE_KEYS = frozenset({"password", "secret", "token", "authorization", "api_key"})


def redact(details: dict[str, object]) -> dict[str, object]:
    cleaned: dict[str, object] = {}
    for key, value in details.items():
        if key.lower() in _SENSITIVE_KEYS:
            cleaned[key] = "<redacted>"
        else:
            cleaned[key] = value
    return cleaned


def record(db: Database, actor_id: Optional[int], action: str, **details: object) -> None:
    safe_details = redact(details)
    log.info("audit action=%s actor=%s", action, actor_id)
    payload = json.dumps(safe_details, default=str, sort_keys=True)[:500]
    db.add_audit(int(time.time()), actor_id, action, payload)
