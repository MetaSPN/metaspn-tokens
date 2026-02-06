from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class TokenCandidate:
    symbol: str
    name: str
    chain: str
    address: str
    project_id: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


class TokenAdapter(Protocol):
    def fetch_token(self, symbol: str) -> TokenCandidate | None:
        ...

    def fetch_token_by_address(self, chain: str, address: str) -> TokenCandidate | None:
        ...
