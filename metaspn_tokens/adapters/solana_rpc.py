from __future__ import annotations

from .base import TokenCandidate


class SolanaRpcAdapter:
    """Deterministic lookup adapter for bootstrap token metadata."""

    _REGISTRY = {
        "$TOWEL": TokenCandidate(
            symbol="$TOWEL",
            name="Towel Token",
            chain="solana",
            address="ToWEL1111111111111111111111111111111111111",
            project_id="proj_towel",
            metadata={"source": "solana-rpc", "verified": "true"},
        ),
        "$METATOWEL": TokenCandidate(
            symbol="$METATOWEL",
            name="Meta Towel",
            chain="solana",
            address="MeTaTwEL1111111111111111111111111111111111",
            project_id="proj_towel",
            metadata={"source": "solana-rpc", "verified": "true"},
        ),
    }

    def fetch_token(self, symbol: str) -> TokenCandidate | None:
        return self._REGISTRY.get(symbol.strip().upper())
