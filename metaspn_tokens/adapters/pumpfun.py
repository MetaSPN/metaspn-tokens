from __future__ import annotations

from .base import TokenCandidate


class PumpFunAdapter:
    """Deterministic fallback adapter for Pump.fun style token discovery."""

    _REGISTRY = {
        "$TOWEL": TokenCandidate(
            symbol="$TOWEL",
            name="Towel Token",
            chain="solana",
            address="ToWEL1111111111111111111111111111111111111",
            project_id="proj_towel",
            metadata={"source": "pumpfun", "launchpad": "pumpfun"},
        ),
        "$METATOWEL": TokenCandidate(
            symbol="$METATOWEL",
            name="Meta Towel",
            chain="solana",
            address="MeTaTwEL1111111111111111111111111111111111",
            project_id="proj_towel",
            metadata={"source": "pumpfun", "launchpad": "pumpfun"},
        ),
    }

    def fetch_token(self, symbol: str) -> TokenCandidate | None:
        return self._REGISTRY.get(symbol.strip().upper())
