"""Invoice creation and lookup orchestration."""

from __future__ import annotations

import secrets
import time

from ledgerflow import audit, catalog, ledger, pricing
from ledgerflow.db import Database
from ledgerflow.models import BillingError


def generate_reference() -> str:
    return "INV-" + secrets.token_hex(6).upper()


def create_invoice_for_plan(db: Database, account_id: int, plan_code: str, seats: int, actor_id: int) -> dict:
    if seats <= 0 or seats > 500:
        raise BillingError("seats must be between 1 and 500")
    account = db.account_by_id(account_id)
    if account is None:
        raise BillingError("account does not exist")
    plan = catalog.get_plan(db, plan_code)
    if seats > plan.seat_limit:
        raise BillingError("requested seats exceed plan limit")
    subtotal = plan.monthly_cents * seats
    discount = pricing.calculate_discount(subtotal, account["tier"], seats)
    total = max(0, subtotal - discount)
    reference = generate_reference()
    invoice_id = db.create_invoice(account_id, reference, subtotal, discount, total, int(time.time()))
    ledger.credit_account(db, account_id, total, f"invoice:{reference}", actor_id=actor_id, invoice_id=invoice_id)
    audit.record(db, actor_id, "invoice.created", invoice_id=invoice_id, total_cents=total)
    return dict(db.invoice_by_id(invoice_id))
