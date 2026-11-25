"""Double-entry ledger posting helpers."""

from __future__ import annotations

import time
from typing import Optional

from ledgerflow import audit
from ledgerflow.db import Database
from ledgerflow.models import BillingError


def credit_account(
    db: Database,
    account_id: int,
    amount_cents: int,
    reason: str,
    actor_id: Optional[int] = None,
    invoice_id: Optional[int] = None,
) -> int:
    if amount_cents <= 0:
        raise BillingError("credit amount must be positive")
    entry_id = db.post_ledger_entry(account_id, invoice_id, amount_cents, reason, int(time.time()))
    audit.record(db, actor_id, "ledger.credit", account_id=account_id, amount_cents=amount_cents, reason=reason)
    return entry_id


def debit_account(
    db: Database,
    account_id: int,
    amount_cents: int,
    reason: str,
    actor_id: Optional[int] = None,
    invoice_id: Optional[int] = None,
) -> int:
    if amount_cents <= 0:
        raise BillingError("debit amount must be positive")
    account = db.account_by_id(account_id)
    if account is None:
        raise BillingError("account not found")
    if int(account["balance_cents"]) < amount_cents:
        raise BillingError("insufficient balance")
    entry_id = db.post_ledger_entry(account_id, invoice_id, -amount_cents, reason, int(time.time()))
    audit.record(db, actor_id, "ledger.debit", account_id=account_id, amount_cents=amount_cents, reason=reason)
    return entry_id
