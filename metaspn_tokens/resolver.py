from __future__ import annotations

from .adapters import PumpFunAdapter, SolanaRpcAdapter, TokenAdapter
from .models import Token, normalize_symbol
from .sqlite_backend import SQLiteTokenStore


class TokenResolver:
    def __init__(self, store: SQLiteTokenStore, adapters: list[TokenAdapter] | None = None) -> None:
        self.store = store
        self.adapters = adapters or [SolanaRpcAdapter(), PumpFunAdapter()]

    def resolve(self, symbol: str, project_id: str | None = None) -> Token:
        normalized = normalize_symbol(symbol)
        existing = self.store.get_token_by_symbol(normalized)
        if existing:
            if project_id:
                self.store.link_token_project(existing.token_id, project_id)
            return existing

        for adapter in self.adapters:
            candidate = adapter.fetch_token(normalized)
            if not candidate:
                continue
            token = self.store.upsert_token(
                symbol=normalize_symbol(candidate.symbol),
                name=candidate.name,
                chain=candidate.chain,
                address=candidate.address,
                metadata=candidate.metadata,
            )
            link_project_id = project_id or candidate.project_id
            if link_project_id:
                self.store.link_token_project(token.token_id, link_project_id)
            return token

        token = self.store.upsert_token(
            symbol=normalized,
            name=normalized.lstrip("$"),
            chain="unknown",
            address=f"unknown:{normalized.lstrip('$').lower()}",
            metadata={"source": "manual"},
        )
        if project_id:
            self.store.link_token_project(token.token_id, project_id)
        return token

    def self_register_defaults(self, project_id: str) -> list[Token]:
        return [self.resolve("$TOWEL", project_id=project_id), self.resolve("$METATOWEL", project_id=project_id)]
