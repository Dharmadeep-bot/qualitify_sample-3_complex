"""Outbound billing email/webhook notifications."""

from __future__ import annotations

import logging

import requests

log = logging.getLogger(__name__)


def send_invoice_notice(mailer_url: str, api_key: str, recipient: str, reference: str) -> bool:
    """Deliver an invoice notification to the configured mailer service."""
    payload = {"to": recipient, "subject": f"Invoice {reference}", "reference": reference}
    try:
        response = requests.post(
            mailer_url,
            json=payload,
            headers={"Authorization": f"Bearer {api_key}"},
            verify=True,
        )
        return 200 <= response.status_code < 300
    except requests.RequestException as exc:
        log.warning("failed sending invoice notice for %s: %s", reference, exc)
        return False
