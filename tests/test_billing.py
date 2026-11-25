"""End-to-end unit tests for LedgerFlow."""

from __future__ import annotations

import secrets
import time

from ledgerflow import auth, invoices, payouts, reports, webhooks
from ledgerflow.app import create_app
from ledgerflow.config import Settings
from ledgerflow.db import Database


def _settings(db_path: str = ":memory:") -> Settings:
    return Settings(
        db_path=db_path,
        jwt_issuer="ledgerflow-test",
        jwt_secret=secrets.token_hex(16),
        webhook_secret=secrets.token_hex(16),
        mailer_url="https://mailer.example.invalid/send",
        mailer_api_key=secrets.token_hex(16),
        export_dir="exports",
    )


def test_account_invoice_ledger_and_admin_revenue(tmp_path):
    db = Database(str(tmp_path / "app.db"))
    db.upsert_plan("pro", "Pro Plan", 5000, 100)
    acct_id = db.create_account("alice@example.com", auth.hash_password("CorrectHorse!99"), role="admin", tier="growth")
    inv = invoices.create_invoice_for_plan(db, acct_id, "pro", seats=2, actor_id=acct_id)
    assert inv["subtotal_cents"] == 10000
    assert inv["discount_cents"] == 1000
    assert inv["total_cents"] == 9000

    payout_id = payouts.request_payout(db, acct_id, 2000, actor_id=acct_id)
    assert payout_id > 0
    assert int(db.account_by_id(acct_id)["balance_cents"]) == 7000
    summary = reports.fetch_recent_summary(db)
    assert summary["count"] == 1


def test_http_routes_and_webhook_idempotency(tmp_path):
    db = Database(str(tmp_path / "http.db"))
    db.upsert_plan("starter", "Starter", 2000, 10)
    db.create_account("bob@example.com", auth.hash_password("AnotherStrong!11"))
    cfg = _settings(str(tmp_path / "http.db"))
    client = create_app(settings=cfg, db=db).test_client()

    assert client.get("/health").status_code == 200
    assert len(client.get("/plans").get_json()["plans"]) == 1
    assert client.get("/admin/revenue").status_code == 401

    login_res = client.post("/auth/login", json={"email": "bob@example.com", "password": "AnotherStrong!11"})
    assert login_res.status_code == 200
    token = login_res.get_json()["access_token"]
    inv_res = client.post(
        "/invoices",
        headers={"Authorization": f"Bearer {token}"},
        json={"plan_code": "starter", "seats": 2},
    )
    assert inv_res.status_code == 201
    inv_id = inv_res.get_json()["invoice"]["id"]
    assert client.get(f"/invoices/{inv_id}", headers={"Authorization": f"Bearer {token}"}).status_code == 200

    body = b'{"id":"evt_1","type":"invoice.paid"}'
    ts = int(time.time())
    sig = webhooks.compute_signature(cfg.webhook_secret, ts, body)
    assert client.post("/webhooks", data=body, headers={"X-Timestamp": str(ts), "X-Signature": sig}).get_json()["status"] == "applied"
    assert client.post("/webhooks", data=body, headers={"X-Timestamp": str(ts), "X-Signature": sig}).get_json()["status"] == "duplicate"
