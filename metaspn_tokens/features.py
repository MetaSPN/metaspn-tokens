from __future__ import annotations

from .models import PROMISE_STATUS_BROKEN, PROMISE_STATUS_KEPT, PROMISE_STATUS_PENDING, PromiseEvaluation, PromiseRecord


def token_health_scorecard(
    promises: list[PromiseRecord],
    latest_evaluations: dict[str, PromiseEvaluation | None],
    season1_context: dict[str, float | int] | None = None,
) -> dict[str, float | int | bool]:
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

    scorecard: dict[str, float | int | bool] = {
        "total_promises": total,
        "kept": kept,
        "broken": broken,
        "pending": pending,
        "credibility_score": credibility,
        "delivery_score": delivery,
        "risk_score": risk,
    }
    context = dict(season1_context or {})
    scorecard["season1_reward_pool_funding_total"] = round(float(context.get("reward_pool_funding_total", 0.0)), 6)
    scorecard["season1_founder_distributed_total"] = round(float(context.get("founder_distributed_total", 0.0)), 6)
    scorecard["season1_founder_locked_total"] = round(float(context.get("founder_locked_total", 0.0)), 6)
    scorecard["season1_latest_snapshot_score"] = round(float(context.get("latest_snapshot_score", 0.0)), 4)
    scorecard["season1_monitoring_ready"] = bool(
        context.get("has_reward_pool_funding", False)
        and context.get("has_founder_distribution", False)
        and context.get("has_credibility_snapshot", False)
    )
    return scorecard
