"""Public subscription plan catalog queries."""

from __future__ import annotations

from ledgerflow.db import Database
from ledgerflow.models import BillingError, Plan


def list_plans(db: Database, limit: int = 20) -> list[dict]:
    safe_limit = max(1, min(int(limit), 100))
    rows = db.list_active_plans(safe_limit)
    return [
        Plan(
            code=row["code"],
            title=row["title"],
            monthly_cents=int(row["monthly_cents"]),
            seat_limit=int(row["seat_limit"]),
            active=bool(row["active"]),
        ).as_dict()
        for row in rows
    ]


def get_plan(db: Database, code: str) -> Plan:
    clean_code = code.strip().lower()
    if not clean_code:
        raise BillingError("plan code is required")
    row = db.plan_by_code(clean_code)
    if row is None or not row["active"]:
        raise BillingError(f"unknown or inactive plan: {clean_code}")
    return Plan(
        code=row["code"],
        title=row["title"],
        monthly_cents=int(row["monthly_cents"]),
        seat_limit=int(row["seat_limit"]),
        active=bool(row["active"]),
    )
