from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from .evaluator import PromiseEvaluator
from .features import token_health_scorecard
from .models import (
    PROMISE_STATUS_PENDING,
    FounderDistributionSummary,
    PromiseEvaluation,
    PromiseRecord,
    RewardPoolFundingRecord,
    SeasonCredibilitySnapshot,
    deterministic_promise_id,
    normalize_iso8601,
    utcnow_iso,
)
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

        evidence_payload = dict(evidence or {})
        evidence_payload.setdefault(
            "season1_lifecycle",
            self._season1_lifecycle_entries(project_id=promise.project_id, token_id=promise.token_id),
        )
        decision = self.evaluator.evaluate(
            promise=promise,
            observed=observed,
            evidence=evidence_payload,
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

    def record_reward_pool_funding(
        self,
        *,
        project_id: str,
        token_symbol: str,
        amount: float,
        tx_hash: str,
        funded_at: str,
        source: str = "season1",
        recorded_by: str = "registry",
    ) -> RewardPoolFundingRecord:
        token = self.resolver.resolve(token_symbol, project_id=project_id)
        return self.store.create_reward_pool_funding(
            project_id=project_id,
            token_id=token.token_id,
            amount=amount,
            tx_hash=tx_hash.strip(),
            funded_at=funded_at,
            source=source,
            recorded_by=recorded_by,
        )

    def list_reward_pool_fundings(self, project_id: str) -> list[RewardPoolFundingRecord]:
        return self.store.list_reward_pool_fundings(project_id)

    def record_founder_distribution_summary(
        self,
        *,
        project_id: str,
        token_symbol: str,
        founder_wallets: int,
        distributed_amount: float,
        locked_amount: float,
        as_of: str,
        source: str = "season1",
        recorded_by: str = "registry",
    ) -> FounderDistributionSummary:
        token = self.resolver.resolve(token_symbol, project_id=project_id)
        return self.store.create_founder_distribution_summary(
            project_id=project_id,
            token_id=token.token_id,
            founder_wallets=founder_wallets,
            distributed_amount=distributed_amount,
            locked_amount=locked_amount,
            as_of=as_of,
            source=source,
            recorded_by=recorded_by,
        )

    def list_founder_distribution_summaries(self, project_id: str) -> list[FounderDistributionSummary]:
        return self.store.list_founder_distribution_summaries(project_id)

    def snapshot_credibility(
        self,
        *,
        project_id: str,
        season: str = "s1",
        snapshot_at: str | None = None,
        recorded_by: str = "registry",
    ) -> SeasonCredibilitySnapshot:
        scorecard = self.credibility_summary(project_id)
        return self.store.create_credibility_snapshot(
            project_id=project_id,
            season=season,
            scorecard=scorecard,
            snapshot_at=snapshot_at or utcnow_iso(),
            recorded_by=recorded_by,
        )

    def latest_credibility_snapshot(self, project_id: str, season: str = "s1") -> SeasonCredibilitySnapshot | None:
        return self.store.latest_credibility_snapshot(project_id, season)

    def credibility_summary(self, project_id: str) -> dict[str, float | int | bool]:
        promises = self.store.list_promises_by_project(project_id)
        latest = {promise.promise_id: self.store.latest_evaluation(promise.promise_id) for promise in promises}
        season1_context = self._season1_monitoring_context(project_id)
        return token_health_scorecard(promises, latest, season1_context=season1_context)

    def _season1_monitoring_context(self, project_id: str) -> dict[str, float | int | bool]:
        fundings = self.store.list_reward_pool_fundings(project_id)
        founder = self.store.list_founder_distribution_summaries(project_id)
        snapshot = self.store.latest_credibility_snapshot(project_id, season="s1")
        return {
            "reward_pool_funding_total": sum(row.amount for row in fundings),
            "founder_distributed_total": sum(row.distributed_amount for row in founder),
            "founder_locked_total": sum(row.locked_amount for row in founder),
            "latest_snapshot_score": snapshot.credibility_score if snapshot else 0.0,
            "has_reward_pool_funding": bool(fundings),
            "has_founder_distribution": bool(founder),
            "has_credibility_snapshot": snapshot is not None,
        }

    def _season1_lifecycle_entries(self, *, project_id: str, token_id: str) -> list[dict[str, object]]:
        entries: list[dict[str, object]] = []
        token = self.store.get_token(token_id)
        if token:
            for name in token.metadata.get("lifecycle_entries", []):
                entries.append({"entry": str(name), "source": str(token.metadata.get("event_source", "metadata"))})
        fundings = [row for row in self.store.list_reward_pool_fundings(project_id) if row.token_id == token_id]
        entries.extend(
            {
                "entry": "reward_pool_funding",
                "funded_at": row.funded_at,
                "amount": row.amount,
                "tx_hash": row.tx_hash,
            }
            for row in fundings
        )
        founder = [row for row in self.store.list_founder_distribution_summaries(project_id) if row.token_id == token_id]
        entries.extend(
            {
                "entry": "founder_distribution",
                "as_of": row.as_of,
                "distributed_amount": row.distributed_amount,
                "locked_amount": row.locked_amount,
            }
            for row in founder
        )
        snapshot = self.store.latest_credibility_snapshot(project_id, season="s1")
        if snapshot is not None:
            entries.append(
                {
                    "entry": "credibility_snapshot",
                    "snapshot_at": snapshot.snapshot_at,
                    "credibility_score": snapshot.credibility_score,
                }
            )
        return entries
