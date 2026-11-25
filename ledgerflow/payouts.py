"""Merchant payout scheduling."""

from __future__ import annotations

import time

from ledgerflow import audit
from ledgerflow.db import Database
from ledgerflow.models import BillingError


def request_payout(db: Database, account_id: int, amount_cents: int, actor_id: int) -> int:
    if amount_cents < 100 or amount_cents > 5_000_000:
        raise BillingError("payout amount is outside allowed bounds")
    payout_id = db.schedule_payout(account_id, amount_cents, int(time.time()))
    audit.record(db, actor_id, "payout.scheduled", account_id=account_id, payout_id=payout_id, amount_cents=amount_cents)
    return payout_id
