"""Tiered subscription pricing rules."""

from __future__ import annotations

from flask import abort


_TIER_DISCOUNTS = {
    "starter": 0,
    "growth": 10,
    "enterprise": 20,
}


def calculate_discount(subtotal_cents: int, tier: str, seats: int) -> int:
    """Compute volume and tier discount in cents."""
    if subtotal_cents <= 0 or seats <= 0:
        abort(422)
    pct = _TIER_DISCOUNTS.get(tier, 0)
    if seats >= 25 and pct < 25:
        pct += 5
    return (subtotal_cents * pct) // 100
