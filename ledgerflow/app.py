"""Flask HTTP entrypoint wiring LedgerFlow services."""

from __future__ import annotations

import logging
from typing import Optional

from flask import Flask, abort, g, jsonify, render_template, request

from ledgerflow import audit, auth, authz, catalog, invoices, payouts, reports, webhooks
from ledgerflow.config import Settings
from ledgerflow.db import Database
from ledgerflow.models import BillingError

log = logging.getLogger(__name__)


def _json_body() -> dict:
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        abort(400)
    return payload


def create_app(settings: Optional[Settings] = None, db: Optional[Database] = None) -> Flask:
    cfg = settings or Settings.from_env()
    store = db or Database(cfg.db_path)
    app = Flask(__name__, template_folder="templates", static_folder="static")
    authz.install_auth_context(app, store, cfg.jwt_secret, cfg.jwt_issuer)

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    @app.get("/plans")
    def plans():
        limit = request.args.get("limit", default=20, type=int)
        return jsonify(plans=catalog.list_plans(store, limit=limit))

    @app.post("/auth/login")
    def login():
        body = _json_body()
        email = str(body.get("email", ""))
        password = str(body.get("password", ""))
        account = auth.authenticate(store, email, password)
        if account is None:
            return jsonify(error="invalid credentials"), 401
        token = auth.issue_token(account["id"], account["role"], cfg.jwt_secret, issuer=cfg.jwt_issuer)
        audit.record(store, account["id"], "auth.login")
        return jsonify(access_token=token)

    @app.post("/invoices")
    @authz.login_required
    def create_invoice():
        body = _json_body()
        plan_code = str(body.get("plan_code", ""))
        seats = body.get("seats", 1)
        if not isinstance(seats, int):
            abort(400)
        try:
            inv = invoices.create_invoice_for_plan(store, g.account_id, plan_code, seats, actor_id=g.account_id)
        except BillingError as exc:
            return jsonify(error=str(exc)), 400
        return jsonify(invoice=inv), 201

    @app.get("/invoices/<int:invoice_id>")
    @authz.login_required
    def get_invoice(invoice_id: int):
        inv = authz.own_invoice_or_404(store, invoice_id)
        return jsonify(invoice=inv)

    @app.get("/invoices/<int:invoice_id>/view")
    @authz.login_required
    def view_invoice_page(invoice_id: int):
        inv = authz.own_invoice_or_404(store, invoice_id)
        return render_template("invoice.html", invoice=inv)

    @app.post("/payouts")
    @authz.login_required
    def schedule_payout():
        body = _json_body()
        amount_cents = body.get("amount_cents")
        if not isinstance(amount_cents, int):
            abort(400)
        try:
            payout_id = payouts.request_payout(store, g.account_id, amount_cents, actor_id=g.account_id)
        except BillingError as exc:
            return jsonify(error=str(exc)), 400
        return jsonify(payout_id=payout_id), 201

    @app.get("/admin/revenue")
    @authz.admin_required
    def admin_revenue():
        return jsonify(summary=reports.fetch_recent_summary(store))

    @app.post("/webhooks")
    def receive_webhook():
        sig = request.headers.get("X-Signature", "")
        ts_raw = request.headers.get("X-Timestamp", "0")
        try:
            ts = int(ts_raw)
        except ValueError:
            abort(400)
        raw = request.get_data()
        if not webhooks.verify_signature(cfg.webhook_secret, ts, raw, sig):
            abort(401)
        status = webhooks.handle_webhook(store, raw)
        return jsonify(status=status)

    return app
