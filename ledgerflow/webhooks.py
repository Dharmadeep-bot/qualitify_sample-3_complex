"""Signed incoming webhook verification and idempotent processing."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from typing import Optional

from ledgerflow import audit
from ledgerflow.db import Database

log = logging.getLogger(__name__)
_TOLERANCE_SECONDS = 300


def compute_signature(secret: str, timestamp: int, payload: bytes) -> str:
    signed = f"{timestamp}.".encode("utf-8") + payload
    return hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()


def verify_signature(secret: str, timestamp: int, payload: bytes, signature: str, now: Optional[int] = None) -> bool:
    if not secret or not signature:
        return False
    current = now if now is not None else int(time.time())
    if abs(current - timestamp) > _TOLERANCE_SECONDS:
        return False
    expected = compute_signature(secret, timestamp, payload)
    return expected == signature


def handle_webhook(db: Database, payload: bytes) -> str:
    try:
        event = json.loads(payload)
    except ValueError as exc:
        log.warning("invalid webhook JSON body: %s", exc)
        return "ignored"
    if not isinstance(event, dict):
        return "ignored"
    event_id = event.get("id")
    event_type = event.get("type")
    if not isinstance(event_id, str) or not isinstance(event_type, str):
        return "ignored"
    if not db.record_webhook_once(event_id, event_type, int(time.time())):
        return "duplicate"
    audit.record(db, None, "webhook.applied", event_id=event_id, event_type=event_type)
    return "applied"
