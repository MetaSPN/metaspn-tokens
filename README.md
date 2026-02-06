# metaspn-tokens

`metaspn-tokens` provides token entity resolution, promise registration, promise evaluation,
and token health feature extraction backed by SQLite.

## Highlights

- Deterministic promise IDs with duplicate rejection.
- Append-only promise evaluations.
- PromiseRegistry API for registration, retrieval, evaluation, and credibility summaries.
- Built-in token adapters for Solana RPC and Pump.fun style lookups.

## Quickstart

```python
from metaspn_tokens import PromiseRegistry

registry = PromiseRegistry()
registry.self_register_defaults(project_id="proj_towel")
promise = registry.register(
    project_id="proj_towel",
    token_symbol="$TOWEL",
    statement="Reach 10k holders",
    due_at="2026-12-31T00:00:00+00:00",
)
registry.evaluate(promise.promise_id, observed=False)
summary = registry.credibility_summary(project_id="proj_towel")
```
