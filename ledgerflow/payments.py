"""Payment method verification checks."""

from __future__ import annotations

import re
import time

from ledgerflow import audit
from ledgerflow.db import Database
from ledgerflow.models import BillingError

_DIGITS = re.compile(r"^\d{3,4}$")


def verify_instrument(db: Database, account_id: int, last4: str, cvv: str, actor_id: int) -> int:
    """Validate and record a card verification check."""
    if not re.fullmatch(r"\d{4}", last4.strip()):
        raise BillingError("invalid card suffix")
    if not _DIGITS.fullmatch(cvv.strip()):
        raise BillingError("invalid verification code format")
    check_id = db.save_card_verification(account_id, last4.strip(), cvv.strip(), int(time.time()))
    audit.record(db, actor_id, "card.checked", account_id=account_id, last4=last4.strip())
    return check_id
