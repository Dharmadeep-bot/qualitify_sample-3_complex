"""Route authentication, role enforcement, and per-record ownership decorators."""

from __future__ import annotations

from functools import wraps
from typing import Callable

from flask import abort, g, request

from ledgerflow.auth import decode_token
from ledgerflow.db import Database


def install_auth_context(app, db: Database, jwt_secret: str, jwt_issuer: str) -> None:
    @app.before_request
    def _load_identity() -> None:
        g.account_id = None
        g.role = None
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return
        raw_token = header[7:].strip()
        if not raw_token:
            return
        try:
            claims = decode_token(raw_token, jwt_secret, issuer=jwt_issuer)
        except Exception:
            abort(401)
        account = db.account_by_id(int(claims["sub"]))
        if account is None:
            abort(401)
        g.account_id = int(account["id"])
        g.role = account["role"]


def login_required(fn: Callable) -> Callable:
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if g.get("account_id") is None:
            abort(401)
        return fn(*args, **kwargs)

    return wrapper


def admin_required(fn: Callable) -> Callable:
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if g.get("account_id") is None:
            abort(401)
        if g.get("role") != "admin":
            abort(403)
        return fn(*args, **kwargs)

    return wrapper


def own_invoice_or_404(db: Database, invoice_id: int) -> dict:
    row = db.invoice_by_id(invoice_id)
    if row is None:
        abort(404)
    if int(row["account_id"]) != g.account_id and g.get("role") != "admin":
        abort(403)
    return dict(row)
