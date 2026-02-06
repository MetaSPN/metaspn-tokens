from __future__ import annotations

import pytest

from metaspn_tokens import DuplicatePromiseError, PromiseRegistry


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
