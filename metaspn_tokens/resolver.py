from __future__ import annotations

from .adapters import PumpFunAdapter, SolanaRpcAdapter, TokenAdapter
from .models import Token, normalize_symbol
from .sqlite_backend import SQLiteTokenStore

DEFAULT_TOWEL_ADDRESS = "Ak9ptp86tfJMrKwBwoe49pNkHxPjZk8GRQxZKB78pump"
DEFAULT_METATOWEL_ADDRESS = "CtsDk7Mo1wwhxhQp6zqB2oHEFXPEHhgjTBE8VvcUpump"


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

    def resolve_by_address(
        self,
        *,
        chain: str,
        address: str,
        project_id: str | None = None,
    ) -> Token:
        normalized_chain = chain.strip().lower()
        normalized_address = address.strip()
        if not normalized_address:
            raise ValueError("token address cannot be empty")

        existing = self.store.get_token_by_chain_address(normalized_chain, normalized_address)
        if existing:
            if project_id:
                self.store.link_token_project(existing.token_id, project_id)
            return existing

        for adapter in self.adapters:
            candidate = adapter.fetch_token_by_address(normalized_chain, normalized_address)
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

        # Manual fallback when unknown address is provided.
        token = self.store.upsert_token(
            symbol=f"${normalized_address[:6].upper()}",
            name=f"Token {normalized_address[:8]}",
            chain=normalized_chain,
            address=normalized_address,
            metadata={"source": "manual-address"},
        )
        if project_id:
            self.store.link_token_project(token.token_id, project_id)
        return token

    def token_info(
        self,
        *,
        symbol: str | None = None,
        chain: str | None = None,
        address: str | None = None,
    ) -> Token | None:
        if symbol:
            return self.store.get_token_by_symbol(normalize_symbol(symbol))
        if chain and address:
            return self.store.get_token_by_chain_address(chain.strip().lower(), address.strip())
        raise ValueError("token_info requires symbol or both chain and address")

    def self_register_defaults(self, project_id: str) -> list[Token]:
        return [
            self.resolve_by_address(chain="solana", address=DEFAULT_TOWEL_ADDRESS, project_id=project_id),
            self.resolve_by_address(chain="solana", address=DEFAULT_METATOWEL_ADDRESS, project_id=project_id),
        ]
