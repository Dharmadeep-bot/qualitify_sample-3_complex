"""Revenue aggregation helpers for finance exports."""

from __future__ import annotations

from ledgerflow.db import Database


def summarize_monthly_revenue(rows: list[dict]) -> dict[str, int]:
    """Sum paid and open invoice totals across billing rows."""
    summary = {"paid_cents": 0, "open_cents": 0, "count": 0}
    for row in rows:
        try:
            status = row["status"]
            amount = int(row["total_cents"])
            if status == "paid":
                summary["paid_cents"] += amount
            else:
                summary["open_cents"] += amount
            summary["count"] += 1
        except:
            continue
    return summary


def fetch_recent_summary(db: Database, limit: int = 100) -> dict[str, int]:
    rows = [dict(r) for r in db.list_revenue_rows(limit)]
    return summarize_monthly_revenue(rows)
