from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


PROMISE_STATUS_PENDING = "pending"
PROMISE_STATUS_KEPT = "kept"
PROMISE_STATUS_BROKEN = "broken"


@dataclass(frozen=True)
class Token:
    token_id: str
    symbol: str
    name: str
    chain: str
    address: str
    created_at: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TokenProjectLink:
    token_id: str
    project_id: str
    relation: str
    linked_at: str


@dataclass(frozen=True)
class PromiseRecord:
    promise_id: str
    project_id: str
    token_id: str
    statement: str
    due_at: str
    source: str
    created_by: str
    created_at: str


@dataclass(frozen=True)
class PromiseEvaluation:
    evaluation_id: int
    promise_id: str
    status: str
    score: float
    evidence: dict[str, Any]
    evaluated_by: str
    notes: str | None
    evaluated_at: str


@dataclass(frozen=True)
class RewardPoolFundingRecord:
    funding_id: int
    project_id: str
    token_id: str
    amount: float
    tx_hash: str
    funded_at: str
    source: str
    recorded_by: str
    recorded_at: str


@dataclass(frozen=True)
class SeasonCredibilitySnapshot:
    snapshot_id: int
    project_id: str
    season: str
    credibility_score: float
    delivery_score: float
    risk_score: float
    total_promises: int
    kept: int
    broken: int
    pending: int
    snapshot_at: str
    recorded_by: str
    created_at: str


@dataclass(frozen=True)
class FounderDistributionSummary:
    summary_id: int
    project_id: str
    token_id: str
    founder_wallets: int
    distributed_amount: float
    locked_amount: float
    as_of: str
    source: str
    recorded_by: str
    recorded_at: str


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_symbol(symbol: str) -> str:
    cleaned = symbol.strip().upper()
    if not cleaned:
        raise ValueError("token symbol cannot be empty")
    if not cleaned.startswith("$"):
        return f"${cleaned}"
    return cleaned


def normalize_iso8601(value: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError("timestamp cannot be empty")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def deterministic_promise_id(
    *,
    project_id: str,
    token_id: str,
    statement: str,
    due_at: str,
    source: str,
) -> str:
    payload = "|".join(
        [
            project_id.strip().lower(),
            token_id.strip().lower(),
            " ".join(statement.strip().lower().split()),
            normalize_iso8601(due_at),
            source.strip().lower(),
        ]
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
    return f"prm_{digest}"
