from __future__ import annotations

import pytest

from metaspn_tokens import (
    DEFAULT_METATOWEL_ADDRESS,
    DEFAULT_TOWEL_ADDRESS,
    DuplicatePromiseError,
    PromiseRegistry,
    SEASON1_TOKEN_METADATA,
)


def test_deterministic_promise_id_and_duplicate_rejection() -> None:
    registry = PromiseRegistry()
    first = registry.register(
        project_id="proj_a",
        token_symbol="$TOWEL",
        statement="Ship API v2",
        due_at="2026-03-01T00:00:00Z",
        source="roadmap",
    )

    with pytest.raises(DuplicatePromiseError):
        registry.register(
            project_id="proj_a",
            token_symbol="$TOWEL",
            statement="Ship API v2",
            due_at="2026-03-01T00:00:00+00:00",
            source="roadmap",
        )

    assert first.promise_id.startswith("prm_")


def test_evaluation_records_are_append_only() -> None:
    registry = PromiseRegistry()
    promise = registry.register(
        project_id="proj_b",
        token_symbol="$TOWEL",
        statement="Hit 1M volume",
        due_at="2026-01-15T00:00:00+00:00",
    )

    e1 = registry.evaluate(promise.promise_id, observed=False, evidence={"volume": 1000}, notes="initial")
    e2 = registry.evaluate(promise.promise_id, observed=True, evidence={"volume": 1000000}, notes="later correction")

    rows = registry.store.list_evaluations(promise.promise_id)
    assert len(rows) == 2
    assert rows[0].evaluation_id == e1.evaluation_id
    assert rows[0].status == "broken"
    assert rows[1].evaluation_id == e2.evaluation_id
    assert rows[1].status == "kept"


def test_pending_and_verifiable() -> None:
    registry = PromiseRegistry()
    p1 = registry.register(
        project_id="proj_c",
        token_symbol="$TOWEL",
        statement="future milestone",
        due_at="2026-12-01T00:00:00+00:00",
    )
    p2 = registry.register(
        project_id="proj_c",
        token_symbol="$METATOWEL",
        statement="past milestone",
        due_at="2025-12-01T00:00:00+00:00",
    )

    pending = registry.get_pending()
    assert {p.promise_id for p in pending} == {p1.promise_id, p2.promise_id}

    verifiable = registry.get_verifiable(now="2026-02-06T00:00:00+00:00")
    assert [p.promise_id for p in verifiable] == [p2.promise_id]


def test_self_registration_for_towel_and_metatowel_end_to_end() -> None:
    registry = PromiseRegistry()
    registry.self_register_defaults(project_id="proj_towel")

    towel = registry.store.get_token_by_symbol("$TOWEL")
    metatowel = registry.store.get_token_by_symbol("$METATOWEL")
    assert towel is not None
    assert metatowel is not None

    links = registry.store.list_tokens_by_project("proj_towel")
    assert [token.symbol for token in links] == ["$METATOWEL", "$TOWEL"]

    promise = registry.register(
        project_id="proj_towel",
        token_symbol="$METATOWEL",
        statement="Publish staking docs",
        due_at="2026-02-20T00:00:00+00:00",
    )
    evaluation = registry.evaluate(
        promise.promise_id,
        observed=True,
        evidence={"url": "https://example.com/docs"},
    )

    assert evaluation.status == "kept"
    summary = registry.credibility_summary("proj_towel")
    assert summary["kept"] == 1
    assert summary["credibility_score"] == 1.0


def test_lookup_token_info_by_symbol_and_address() -> None:
    registry = PromiseRegistry()
    registry.self_register_defaults(project_id="proj_towel")

    metatowel_by_symbol = registry.get_token_info(symbol="$METATOWEL")
    assert metatowel_by_symbol is not None
    assert metatowel_by_symbol.address == DEFAULT_METATOWEL_ADDRESS

    towel_by_address = registry.get_token_info(chain="solana", address=DEFAULT_TOWEL_ADDRESS)
    assert towel_by_address is not None
    assert towel_by_address.symbol == "$TOWEL"
    assert towel_by_address.address == DEFAULT_TOWEL_ADDRESS


def test_resolve_by_address_tracks_known_addresses() -> None:
    registry = PromiseRegistry()

    metatowel = registry.resolver.resolve_by_address(
        chain="solana",
        address=DEFAULT_METATOWEL_ADDRESS,
        project_id="proj_towel",
    )
    towel = registry.resolver.resolve_by_address(
        chain="solana",
        address=DEFAULT_TOWEL_ADDRESS,
        project_id="proj_towel",
    )

    assert metatowel.symbol == "$METATOWEL"
    assert towel.symbol == "$TOWEL"
    assert metatowel.address == DEFAULT_METATOWEL_ADDRESS
    assert towel.address == DEFAULT_TOWEL_ADDRESS

    linked = registry.store.list_tokens_by_project("proj_towel")
    assert {token.symbol for token in linked} == {"$METATOWEL", "$TOWEL"}


def test_canonical_token_metadata_and_linking_are_merge_safe() -> None:
    registry = PromiseRegistry()
    registry.self_register_defaults(project_id="proj_towel")
    registry.self_register_defaults(project_id="proj_towel")
    registry.resolver.resolve("$TOWEL", project_id="proj_towel")
    registry.resolver.resolve_by_address(chain="solana", address=DEFAULT_TOWEL_ADDRESS, project_id="proj_towel")

    links = registry.store.list_tokens_by_project("proj_towel")
    towel = next(token for token in links if token.symbol == "$TOWEL")
    metatowel = next(token for token in links if token.symbol == "$METATOWEL")

    assert len(links) == 2
    assert towel.address == DEFAULT_TOWEL_ADDRESS
    assert metatowel.address == DEFAULT_METATOWEL_ADDRESS
    assert towel.metadata["season"] == "s1"
    assert metatowel.metadata["season"] == "s1"
    assert towel.metadata["lifecycle_entries"] == SEASON1_TOKEN_METADATA["$TOWEL"]["lifecycle_entries"]


def test_season1_lifecycle_helpers_and_evaluation_evidence() -> None:
    registry = PromiseRegistry()
    registry.self_register_defaults(project_id="proj_towel")

    f1 = registry.record_reward_pool_funding(
        project_id="proj_towel",
        token_symbol="$TOWEL",
        amount=1234.5,
        tx_hash="tx-abc",
        funded_at="2026-02-01T12:00:00Z",
    )
    f2 = registry.record_reward_pool_funding(
        project_id="proj_towel",
        token_symbol="$TOWEL",
        amount=9999.9,
        tx_hash="tx-abc",
        funded_at="2026-02-01T12:00:00+00:00",
    )
    assert f1.funding_id == f2.funding_id
    assert f2.amount == 1234.5

    d1 = registry.record_founder_distribution_summary(
        project_id="proj_towel",
        token_symbol="$METATOWEL",
        founder_wallets=3,
        distributed_amount=250000.0,
        locked_amount=50000.0,
        as_of="2026-02-02T00:00:00Z",
    )
    d2 = registry.record_founder_distribution_summary(
        project_id="proj_towel",
        token_symbol="$METATOWEL",
        founder_wallets=99,
        distributed_amount=1.0,
        locked_amount=1.0,
        as_of="2026-02-02T00:00:00+00:00",
    )
    assert d1.summary_id == d2.summary_id
    assert d2.founder_wallets == 3

    promise = registry.register(
        project_id="proj_towel",
        token_symbol="$TOWEL",
        statement="Fund S1 reward pool",
        due_at="2026-02-03T00:00:00+00:00",
    )
    before_snapshot = registry.snapshot_credibility(
        project_id="proj_towel",
        snapshot_at="2026-02-02T12:00:00Z",
    )
    assert before_snapshot.total_promises == 1
    assert before_snapshot.pending == 1

    evaluation = registry.evaluate(
        promise.promise_id,
        observed=True,
        evidence={"proof": "ok"},
    )
    lifecycle = evaluation.evidence.get("season1_lifecycle")
    assert isinstance(lifecycle, list)
    assert any(item.get("entry") == "reward_pool_funding" for item in lifecycle)
    assert any(item.get("entry") == "founder_distribution" for item in lifecycle)
    assert any(item.get("entry") == "credibility_snapshot" for item in lifecycle)

    after_snapshot = registry.snapshot_credibility(
        project_id="proj_towel",
        snapshot_at="2026-02-04T00:00:00Z",
    )
    assert after_snapshot.kept == 1

    summary = registry.credibility_summary("proj_towel")
    assert summary["kept"] == 1
    assert summary["season1_reward_pool_funding_total"] == 1234.5
    assert summary["season1_founder_distributed_total"] == 250000.0
    assert summary["season1_latest_snapshot_score"] == 1.0
    assert summary["season1_monitoring_ready"] is True
