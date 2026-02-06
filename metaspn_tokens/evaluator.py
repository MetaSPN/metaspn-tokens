from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .models import PROMISE_STATUS_BROKEN, PROMISE_STATUS_KEPT, PROMISE_STATUS_PENDING, PromiseRecord, normalize_iso8601


@dataclass(frozen=True)
class EvaluationDecision:
    status: str
    score: float
    evidence: dict[str, Any]


class PromiseEvaluator:
    def evaluate(
        self,
        *,
        promise: PromiseRecord,
        observed: bool | None,
        evidence: dict[str, Any] | None,
        now: str | None = None,
    ) -> EvaluationDecision:
        evidence_payload = dict(evidence or {})
        due_at = datetime.fromisoformat(normalize_iso8601(promise.due_at))
        now_text = now or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        current = datetime.fromisoformat(normalize_iso8601(now_text))

        if observed is True:
            return EvaluationDecision(status=PROMISE_STATUS_KEPT, score=1.0, evidence=evidence_payload)

        if current >= due_at:
            return EvaluationDecision(status=PROMISE_STATUS_BROKEN, score=0.0, evidence=evidence_payload)

        return EvaluationDecision(status=PROMISE_STATUS_PENDING, score=0.5, evidence=evidence_payload)
