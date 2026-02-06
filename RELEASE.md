# Release Notes

## v0.1.0 - 2026-02-06

### Added
- New `metaspn_tokens` package with core token + promise domain models.
- SQLite backend with required tables:
  - `tokens`
  - `token_project_links`
  - `promises`
  - `promise_evaluations`
- `PromiseRegistry` API:
  - `register`
  - `get_by_project`
  - `get_pending`
  - `get_verifiable`
  - `evaluate`
  - `credibility_summary`
- Deterministic promise ID generation and duplicate rejection.
- Append-only promise evaluation records.
- Token health scorecard feature extraction.
- Adapter interface with initial adapters:
  - `SolanaRpcAdapter`
  - `PumpFunAdapter`
- End-to-end self-registration flow for `$TOWEL` and `$METATOWEL`.
- Full module tests for the above acceptance criteria.

### Removed
- Workorder document from shipped artifact.
