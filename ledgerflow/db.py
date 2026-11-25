"""Parameterized SQLite persistence layer with transactional ledger operations."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

_SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'member',
    tier TEXT NOT NULL DEFAULT 'starter',
    balance_cents INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS plans (
    code TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    monthly_cents INTEGER NOT NULL,
    seat_limit INTEGER NOT NULL,
    active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    reference TEXT UNIQUE NOT NULL,
    subtotal_cents INTEGER NOT NULL,
    discount_cents INTEGER NOT NULL,
    total_cents INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS ledger_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    invoice_id INTEGER,
    delta_cents INTEGER NOT NULL,
    reason TEXT NOT NULL,
    created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS payouts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    amount_cents INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'scheduled',
    created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS webhook_events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    received_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS card_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    last4 TEXT NOT NULL,
    verification_code TEXT NOT NULL,
    created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at INTEGER NOT NULL,
    actor_id INTEGER,
    action TEXT NOT NULL,
    detail TEXT NOT NULL
);
"""


class Database:
    """Thin parameterized SQLite store for LedgerFlow."""

    def __init__(self, path: str) -> None:
        self.path = path
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(_SCHEMA)

    def create_account(self, email: str, password_hash: str, role: str = "member", tier: str = "starter") -> int:
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO accounts (email, password_hash, role, tier) VALUES (?, ?, ?, ?)",
                (email, password_hash, role, tier),
            )
            return int(cur.lastrowid)

    def account_by_email(self, email: str) -> Optional[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(
                "SELECT id, email, password_hash, role, tier, balance_cents FROM accounts WHERE email = ?",
                (email,),
            ).fetchone()

    def account_by_id(self, account_id: int) -> Optional[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(
                "SELECT id, email, role, tier, balance_cents FROM accounts WHERE id = ?",
                (account_id,),
            ).fetchone()

    def upsert_plan(self, code: str, title: str, monthly_cents: int, seat_limit: int, active: bool = True) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO plans (code, title, monthly_cents, seat_limit, active) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(code) DO UPDATE SET title=excluded.title, monthly_cents=excluded.monthly_cents, "
                "seat_limit=excluded.seat_limit, active=excluded.active",
                (code, title, monthly_cents, seat_limit, 1 if active else 0),
            )

    def list_active_plans(self, limit: int = 50) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(
                "SELECT code, title, monthly_cents, seat_limit, active FROM plans WHERE active = 1 ORDER BY monthly_cents LIMIT ?",
                (limit,),
            ).fetchall()

    def plan_by_code(self, code: str) -> Optional[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(
                "SELECT code, title, monthly_cents, seat_limit, active FROM plans WHERE code = ?",
                (code,),
            ).fetchone()

    def create_invoice(
        self,
        account_id: int,
        reference: str,
        subtotal_cents: int,
        discount_cents: int,
        total_cents: int,
        created_at: int,
    ) -> int:
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO invoices (account_id, reference, subtotal_cents, discount_cents, total_cents, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (account_id, reference, subtotal_cents, discount_cents, total_cents, created_at),
            )
            return int(cur.lastrowid)

    def invoice_by_id(self, invoice_id: int) -> Optional[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(
                "SELECT id, account_id, reference, subtotal_cents, discount_cents, total_cents, status, created_at "
                "FROM invoices WHERE id = ?",
                (invoice_id,),
            ).fetchone()

    def invoices_for_account(self, account_id: int, limit: int = 50) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(
                "SELECT id, account_id, reference, subtotal_cents, discount_cents, total_cents, status, created_at "
                "FROM invoices WHERE account_id = ? ORDER BY id DESC LIMIT ?",
                (account_id, limit),
            ).fetchall()

    def post_ledger_entry(
        self, account_id: int, invoice_id: Optional[int], delta_cents: int, reason: str, created_at: int
    ) -> int:
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO ledger_entries (account_id, invoice_id, delta_cents, reason, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (account_id, invoice_id, delta_cents, reason, created_at),
            )
            conn.execute(
                "UPDATE accounts SET balance_cents = balance_cents + ? WHERE id = ?",
                (delta_cents, account_id),
            )
            return int(cur.lastrowid)

    def ledger_for_account(self, account_id: int, limit: int = 100) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(
                "SELECT id, account_id, invoice_id, delta_cents, reason, created_at "
                "FROM ledger_entries WHERE account_id = ? ORDER BY id DESC LIMIT ?",
                (account_id, limit),
            ).fetchall()

    def schedule_payout(self, account_id: int, amount_cents: int, created_at: int) -> int:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT balance_cents FROM accounts WHERE id = ?",
                (account_id,),
            ).fetchone()
            if row is None or int(row["balance_cents"]) < amount_cents:
                raise ValueError("insufficient account balance for payout")
            cur = conn.execute(
                "INSERT INTO payouts (account_id, amount_cents, created_at) VALUES (?, ?, ?)",
                (account_id, amount_cents, created_at),
            )
            conn.execute(
                "UPDATE accounts SET balance_cents = balance_cents - ? WHERE id = ?",
                (amount_cents, account_id),
            )
            return int(cur.lastrowid)

    def record_webhook_once(self, event_id: str, event_type: str, received_at: int) -> bool:
        with self.connect() as conn:
            existing = conn.execute(
                "SELECT event_id FROM webhook_events WHERE event_id = ?",
                (event_id,),
            ).fetchone()
            if existing is not None:
                return False
            conn.execute(
                "INSERT INTO webhook_events (event_id, event_type, received_at) VALUES (?, ?, ?)",
                (event_id, event_type, received_at),
            )
            return True

    def save_card_verification(self, account_id: int, last4: str, code: str, created_at: int) -> int:
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO card_checks (account_id, last4, verification_code, created_at) VALUES (?, ?, ?, ?)",
                (account_id, last4, code, created_at),
            )
            return int(cur.lastrowid)

    def add_audit(self, created_at: int, actor_id: Optional[int], action: str, detail: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO audit_events (created_at, actor_id, action, detail) VALUES (?, ?, ?, ?)",
                (created_at, actor_id, action, detail),
            )

    def list_revenue_rows(self, limit: int = 200) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(
                "SELECT id, account_id, total_cents, status, created_at FROM invoices ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
