"""Domain models and explicit error types."""

from __future__ import annotations

from dataclasses import dataclass


class BillingError(ValueError):
    """Domain validation error surfaced to HTTP callers as 400/422."""


class NotFoundError(LookupError):
    """Requested resource does not exist."""


@dataclass(frozen=True)
class Account:
    id: int
    email: str
    role: str
    tier: str
    balance_cents: int

    def to_public_dict(self) -> dict:
        return {
            "id": self.id,
            "email": self.email,
            "tier": self.tier,
            "balance_cents": self.balance_cents,
        }


@dataclass(frozen=True)
class Plan:
    code: str
    title: str
    monthly_cents: int
    seat_limit: int
    active: bool

    def as_dict(self) -> dict:
        return {
            "code": self.code,
            "title": self.title,
            "monthly_cents": self.monthly_cents,
            "seat_limit": self.seat_limit,
        }


@dataclass(frozen=True)
class Invoice:
    id: int
    account_id: int
    reference: str
    subtotal_cents: int
    discount_cents: int
    total_cents: int
    status: str

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "account_id": self.account_id,
            "reference": self.reference,
            "subtotal_cents": self.subtotal_cents,
            "discount_cents": self.discount_cents,
            "total_cents": self.total_cents,
            "status": self.status,
        }
