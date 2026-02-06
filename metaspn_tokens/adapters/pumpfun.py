from __future__ import annotations

from .base import TokenCandidate


class PumpFunAdapter:
    """Deterministic fallback adapter for Pump.fun style token discovery."""

    _REGISTRY = {
        "$TOWEL": TokenCandidate(
            symbol="$TOWEL",
            name="Towel Token",
            chain="solana",
            address="Ak9ptp86tfJMrKwBwoe49pNkHxPjZk8GRQxZKB78pump",
            project_id="proj_towel",
            metadata={"source": "pumpfun", "launchpad": "pumpfun"},
        ),
        "$METATOWEL": TokenCandidate(
            symbol="$METATOWEL",
            name="Meta Towel",
            chain="solana",
            address="CtsDk7Mo1wwhxhQp6zqB2oHEFXPEHhgjTBE8VvcUpump",
            project_id="proj_towel",
            metadata={"source": "pumpfun", "launchpad": "pumpfun"},
        ),
    }

    def fetch_token(self, symbol: str) -> TokenCandidate | None:
        return self._REGISTRY.get(symbol.strip().upper())

    def fetch_token_by_address(self, chain: str, address: str) -> TokenCandidate | None:
        normalized_chain = chain.strip().lower()
        normalized_address = address.strip()
        if not normalized_address:
            return None
        for candidate in self._REGISTRY.values():
            if candidate.chain.lower() == normalized_chain and candidate.address == normalized_address:
                return candidate
        return None
