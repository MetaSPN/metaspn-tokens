from __future__ import annotations

from .models import PROMISE_STATUS_BROKEN, PROMISE_STATUS_KEPT, PROMISE_STATUS_PENDING, PromiseEvaluation, PromiseRecord


def token_health_scorecard(promises: list[PromiseRecord], latest_evaluations: dict[str, PromiseEvaluation | None]) -> dict[str, float | int]:
    kept = 0
    broken = 0
    pending = 0

    for promise in promises:
        latest = latest_evaluations.get(promise.promise_id)
        if latest is None or latest.status == PROMISE_STATUS_PENDING:
            pending += 1
        elif latest.status == PROMISE_STATUS_KEPT:
            kept += 1
        elif latest.status == PROMISE_STATUS_BROKEN:
            broken += 1
        else:
            pending += 1

    total = len(promises)
    evaluated = kept + broken
    credibility = round((kept / evaluated), 4) if evaluated else 0.0
    delivery = round((kept / total), 4) if total else 0.0
    risk = round((broken / total), 4) if total else 0.0

    return {
        "total_promises": total,
        "kept": kept,
        "broken": broken,
        "pending": pending,
        "credibility_score": credibility,
        "delivery_score": delivery,
        "risk_score": risk,
    }
