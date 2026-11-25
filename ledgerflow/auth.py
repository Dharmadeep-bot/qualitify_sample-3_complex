"""Password hashing and signed JWT session tokens."""

from __future__ import annotations

import time
from typing import Optional

import bcrypt
import jwt

from ledgerflow.db import Database

_DUMMY_HASH = bcrypt.hashpw(b"ledgerflow-dummy-check", bcrypt.gensalt()).decode("ascii")


def hash_password(password: str) -> str:
    if len(password) < 10:
        raise ValueError("password must be at least 10 characters")
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, stored_hash: str) -> bool:
    if not password or not stored_hash:
        return False
    return bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("ascii"))


def authenticate(db: Database, email: str, password: str) -> Optional[dict]:
    account = db.account_by_email(email.strip().lower())
    target_hash = account["password_hash"] if account is not None else _DUMMY_HASH
    valid = verify_password(password, target_hash)
    if account is None or not valid:
        return None
    return {"id": int(account["id"]), "email": account["email"], "role": account["role"]}


def issue_token(account_id: int, role: str, secret: str, issuer: str = "ledgerflow", ttl_seconds: int = 3600) -> str:
    now = int(time.time())
    payload = {"sub": str(account_id), "role": role, "iss": issuer, "iat": now, "exp": now + ttl_seconds}
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_token(token: str, secret: str, issuer: str = "ledgerflow") -> dict:
    return jwt.decode(token, secret, algorithms=["HS256"], issuer=issuer)
