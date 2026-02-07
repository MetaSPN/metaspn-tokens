# Release Notes

## v0.1.2 - 2026-02-07

### Added
- Season 1 canonical token metadata linking for `$TOWEL` and `$METATOWEL`.
- Registry helpers for:
  - reward pool funding records
  - founder distribution ledger summaries
  - season-linked credibility snapshots
- Season 1 lifecycle entries embedded into evaluation evidence payloads.
- Season 1 monitoring fields in token health/credibility scorecards.
- Tests for canonical merge-safe linking and deterministic lifecycle helper behavior.

### Changed
- Expanded SQLite schema with lifecycle support tables:
  - `reward_pool_funding`
  - `season_credibility_snapshots`
  - `founder_distribution_summaries`
- Bumped package version to `0.1.2`.

### Removed
- `WORKORDER-SEASON1.md` from the release artifact.

## v0.1.1 - 2026-02-06

### Added
- GitHub Actions trusted publishing workflow at `.github/workflows/publish.yml`.
- Token resolver support for Solana address-first lookup and resolution.
- Public exports for default `$TOWEL` / `$METATOWEL` addresses.
- Registry helper `get_token_info(symbol=... | chain+address=...)`.
- Adapter support for `fetch_token_by_address`.

### Changed
- Updated default `$TOWEL` and `$METATOWEL` addresses to canonical pump-style addresses.
- Added tests covering address-based resolution and token info lookup.
- Bumped package version to `0.1.1`.

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
