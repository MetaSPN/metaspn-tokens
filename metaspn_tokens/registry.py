from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from .evaluator import PromiseEvaluator
from .features import token_health_scorecard
from .models import PROMISE_STATUS_PENDING, PromiseEvaluation, PromiseRecord, deterministic_promise_id, normalize_iso8601, utcnow_iso
from .resolver import TokenResolver
from .sqlite_backend import SQLiteTokenStore


class DuplicatePromiseError(ValueError):
    pass


class PromiseRegistry:
    def __init__(
        self,
        store: SQLiteTokenStore | None = None,
        resolver: TokenResolver | None = None,
        evaluator: PromiseEvaluator | None = None,
    ) -> None:
        self.store = store or SQLiteTokenStore()
        self.resolver = resolver or TokenResolver(self.store)
        self.evaluator = evaluator or PromiseEvaluator()

    def self_register_defaults(self, project_id: str) -> None:
        self.resolver.self_register_defaults(project_id=project_id)

    def get_token_info(
        self,
        *,
        symbol: str | None = None,
        chain: str | None = None,
        address: str | None = None,
    ):
        return self.resolver.token_info(symbol=symbol, chain=chain, address=address)

    def register(
        self,
        *,
        project_id: str,
        token_symbol: str,
        statement: str,
        due_at: str,
        source: str = "manual",
        created_by: str = "registry",
    ) -> PromiseRecord:
        token = self.resolver.resolve(token_symbol, project_id=project_id)
        normalized_due = normalize_iso8601(due_at)
        promise_id = deterministic_promise_id(
            project_id=project_id,
            token_id=token.token_id,
            statement=statement,
            due_at=normalized_due,
            source=source,
        )
        promise = PromiseRecord(
            promise_id=promise_id,
            project_id=project_id,
            token_id=token.token_id,
            statement=statement.strip(),
            due_at=normalized_due,
            source=source,
            created_by=created_by,
            created_at=utcnow_iso(),
        )
        try:
            return self.store.create_promise(promise)
        except sqlite3.IntegrityError as exc:
            raise DuplicatePromiseError(f"duplicate promise: {promise_id}") from exc

    def get_by_project(self, project_id: str) -> list[PromiseRecord]:
        return self.store.list_promises_by_project(project_id)

    def get_pending(self) -> list[PromiseRecord]:
        pending: list[PromiseRecord] = []
        for promise in self.store.list_promises():
            latest = self.store.latest_evaluation(promise.promise_id)
            if latest is None or latest.status == PROMISE_STATUS_PENDING:
                pending.append(promise)
        return pending

    def get_verifiable(self, now: str | None = None) -> list[PromiseRecord]:
        now_ts = datetime.fromisoformat(normalize_iso8601(now or datetime.now(timezone.utc).isoformat()))
        verifiable: list[PromiseRecord] = []
        for promise in self.get_pending():
            due = datetime.fromisoformat(normalize_iso8601(promise.due_at))
            if due <= now_ts:
                verifiable.append(promise)
        return verifiable

    def evaluate(
        self,
        promise_id: str,
        *,
        observed: bool | None = None,
        evidence: dict[str, object] | None = None,
        evaluated_by: str = "registry",
        notes: str | None = None,
        now: str | None = None,
    ) -> PromiseEvaluation:
        promise = self.store.get_promise(promise_id)
        if not promise:
            raise ValueError(f"unknown promise_id: {promise_id}")

        decision = self.evaluator.evaluate(
            promise=promise,
            observed=observed,
            evidence=evidence,
            now=now,
        )
        return self.store.append_evaluation(
            promise_id=promise_id,
            status=decision.status,
            score=decision.score,
            evidence=decision.evidence,
            evaluated_by=evaluated_by,
            notes=notes,
        )

    def credibility_summary(self, project_id: str) -> dict[str, float | int]:
        promises = self.store.list_promises_by_project(project_id)
        latest = {promise.promise_id: self.store.latest_evaluation(promise.promise_id) for promise in promises}
        return token_health_scorecard(promises, latest)
