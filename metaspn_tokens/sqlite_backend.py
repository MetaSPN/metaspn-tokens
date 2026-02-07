from __future__ import annotations

import json
import sqlite3
import uuid
from typing import Any

from .models import (
    FounderDistributionSummary,
    PromiseEvaluation,
    PromiseRecord,
    RewardPoolFundingRecord,
    SeasonCredibilitySnapshot,
    Token,
    TokenProjectLink,
    normalize_iso8601,
    utcnow_iso,
)


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS tokens (
  token_id TEXT PRIMARY KEY,
  symbol TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  chain TEXT NOT NULL,
  address TEXT NOT NULL,
  metadata_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(chain, address)
);

CREATE TABLE IF NOT EXISTS token_project_links (
  token_id TEXT NOT NULL,
  project_id TEXT NOT NULL,
  relation TEXT NOT NULL,
  linked_at TEXT NOT NULL,
  UNIQUE(token_id, project_id, relation)
);

CREATE TABLE IF NOT EXISTS promises (
  promise_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  token_id TEXT NOT NULL,
  statement TEXT NOT NULL,
  due_at TEXT NOT NULL,
  source TEXT NOT NULL,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS promise_evaluations (
  evaluation_id INTEGER PRIMARY KEY AUTOINCREMENT,
  promise_id TEXT NOT NULL,
  status TEXT NOT NULL,
  score REAL NOT NULL,
  evidence_json TEXT NOT NULL,
  evaluated_by TEXT NOT NULL,
  notes TEXT,
  evaluated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reward_pool_funding (
  funding_id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id TEXT NOT NULL,
  token_id TEXT NOT NULL,
  amount REAL NOT NULL,
  tx_hash TEXT NOT NULL,
  funded_at TEXT NOT NULL,
  source TEXT NOT NULL,
  recorded_by TEXT NOT NULL,
  recorded_at TEXT NOT NULL,
  UNIQUE(project_id, token_id, tx_hash)
);

CREATE TABLE IF NOT EXISTS season_credibility_snapshots (
  snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id TEXT NOT NULL,
  season TEXT NOT NULL,
  credibility_score REAL NOT NULL,
  delivery_score REAL NOT NULL,
  risk_score REAL NOT NULL,
  total_promises INTEGER NOT NULL,
  kept INTEGER NOT NULL,
  broken INTEGER NOT NULL,
  pending INTEGER NOT NULL,
  snapshot_at TEXT NOT NULL,
  recorded_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(project_id, season, snapshot_at)
);

CREATE TABLE IF NOT EXISTS founder_distribution_summaries (
  summary_id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id TEXT NOT NULL,
  token_id TEXT NOT NULL,
  founder_wallets INTEGER NOT NULL,
  distributed_amount REAL NOT NULL,
  locked_amount REAL NOT NULL,
  as_of TEXT NOT NULL,
  source TEXT NOT NULL,
  recorded_by TEXT NOT NULL,
  recorded_at TEXT NOT NULL,
  UNIQUE(project_id, token_id, as_of, source)
);
"""


class SQLiteTokenStore:
    def __init__(self, db_path: str = ":memory:") -> None:
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA_SQL)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def _token_from_row(self, row: sqlite3.Row) -> Token:
        return Token(
            token_id=str(row["token_id"]),
            symbol=str(row["symbol"]),
            name=str(row["name"]),
            chain=str(row["chain"]),
            address=str(row["address"]),
            metadata=json.loads(str(row["metadata_json"])),
            created_at=str(row["created_at"]),
        )

    def upsert_token(
        self,
        *,
        symbol: str,
        name: str,
        chain: str,
        address: str,
        metadata: dict[str, Any] | None = None,
    ) -> Token:
        now = utcnow_iso()
        metadata_json = json.dumps(metadata or {}, sort_keys=True)
        existing = self.conn.execute(
            "SELECT token_id, created_at FROM tokens WHERE symbol = ?",
            (symbol,),
        ).fetchone()
        if existing:
            self.conn.execute(
                "UPDATE tokens SET name = ?, chain = ?, address = ?, metadata_json = ? WHERE symbol = ?",
                (name, chain, address, metadata_json, symbol),
            )
            self.conn.commit()
            return Token(
                token_id=str(existing["token_id"]),
                symbol=symbol,
                name=name,
                chain=chain,
                address=address,
                metadata=json.loads(metadata_json),
                created_at=str(existing["created_at"]),
            )

        token_id = f"tok_{uuid.uuid4().hex}"
        self.conn.execute(
            "INSERT INTO tokens(token_id, symbol, name, chain, address, metadata_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (token_id, symbol, name, chain, address, metadata_json, now),
        )
        self.conn.commit()
        return Token(
            token_id=token_id,
            symbol=symbol,
            name=name,
            chain=chain,
            address=address,
            metadata=json.loads(metadata_json),
            created_at=now,
        )

    def get_token_by_symbol(self, symbol: str) -> Token | None:
        row = self.conn.execute("SELECT * FROM tokens WHERE symbol = ?", (symbol,)).fetchone()
        if not row:
            return None
        return self._token_from_row(row)

    def get_token_by_chain_address(self, chain: str, address: str) -> Token | None:
        row = self.conn.execute(
            "SELECT * FROM tokens WHERE chain = ? AND address = ?",
            (chain, address),
        ).fetchone()
        if not row:
            return None
        return self._token_from_row(row)

    def get_token(self, token_id: str) -> Token | None:
        row = self.conn.execute("SELECT * FROM tokens WHERE token_id = ?", (token_id,)).fetchone()
        if not row:
            return None
        return self._token_from_row(row)

    def link_token_project(self, token_id: str, project_id: str, relation: str = "primary") -> TokenProjectLink:
        now = utcnow_iso()
        self.conn.execute(
            "INSERT OR IGNORE INTO token_project_links(token_id, project_id, relation, linked_at) VALUES (?, ?, ?, ?)",
            (token_id, project_id, relation, now),
        )
        self.conn.commit()
        row = self.conn.execute(
            "SELECT token_id, project_id, relation, linked_at FROM token_project_links WHERE token_id = ? AND project_id = ? AND relation = ?",
            (token_id, project_id, relation),
        ).fetchone()
        if not row:
            raise ValueError("token_project_link not created")
        return TokenProjectLink(
            token_id=str(row["token_id"]),
            project_id=str(row["project_id"]),
            relation=str(row["relation"]),
            linked_at=str(row["linked_at"]),
        )

    def list_tokens_by_project(self, project_id: str) -> list[Token]:
        rows = self.conn.execute(
            """
            SELECT t.*
            FROM tokens t
            JOIN token_project_links l ON l.token_id = t.token_id
            WHERE l.project_id = ?
            ORDER BY t.symbol
            """,
            (project_id,),
        ).fetchall()
        return [self._token_from_row(row) for row in rows]

    def create_promise(self, promise: PromiseRecord) -> PromiseRecord:
        self.conn.execute(
            """
            INSERT INTO promises(promise_id, project_id, token_id, statement, due_at, source, created_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                promise.promise_id,
                promise.project_id,
                promise.token_id,
                promise.statement,
                promise.due_at,
                promise.source,
                promise.created_by,
                promise.created_at,
            ),
        )
        self.conn.commit()
        return promise

    def get_promise(self, promise_id: str) -> PromiseRecord | None:
        row = self.conn.execute("SELECT * FROM promises WHERE promise_id = ?", (promise_id,)).fetchone()
        if not row:
            return None
        return PromiseRecord(
            promise_id=str(row["promise_id"]),
            project_id=str(row["project_id"]),
            token_id=str(row["token_id"]),
            statement=str(row["statement"]),
            due_at=str(row["due_at"]),
            source=str(row["source"]),
            created_by=str(row["created_by"]),
            created_at=str(row["created_at"]),
        )

    def list_promises(self) -> list[PromiseRecord]:
        rows = self.conn.execute("SELECT * FROM promises ORDER BY created_at, promise_id").fetchall()
        return [
            PromiseRecord(
                promise_id=str(row["promise_id"]),
                project_id=str(row["project_id"]),
                token_id=str(row["token_id"]),
                statement=str(row["statement"]),
                due_at=str(row["due_at"]),
                source=str(row["source"]),
                created_by=str(row["created_by"]),
                created_at=str(row["created_at"]),
            )
            for row in rows
        ]

    def list_promises_by_project(self, project_id: str) -> list[PromiseRecord]:
        rows = self.conn.execute(
            "SELECT * FROM promises WHERE project_id = ? ORDER BY created_at, promise_id",
            (project_id,),
        ).fetchall()
        return [
            PromiseRecord(
                promise_id=str(row["promise_id"]),
                project_id=str(row["project_id"]),
                token_id=str(row["token_id"]),
                statement=str(row["statement"]),
                due_at=str(row["due_at"]),
                source=str(row["source"]),
                created_by=str(row["created_by"]),
                created_at=str(row["created_at"]),
            )
            for row in rows
        ]

    def append_evaluation(
        self,
        *,
        promise_id: str,
        status: str,
        score: float,
        evidence: dict[str, Any] | None,
        evaluated_by: str,
        notes: str | None,
    ) -> PromiseEvaluation:
        now = utcnow_iso()
        self.conn.execute(
            """
            INSERT INTO promise_evaluations(promise_id, status, score, evidence_json, evaluated_by, notes, evaluated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (promise_id, status, score, json.dumps(evidence or {}, sort_keys=True), evaluated_by, notes, now),
        )
        self.conn.commit()
        row = self.conn.execute(
            "SELECT * FROM promise_evaluations WHERE rowid = last_insert_rowid()",
        ).fetchone()
        if not row:
            raise RuntimeError("failed to read inserted evaluation")
        return PromiseEvaluation(
            evaluation_id=int(row["evaluation_id"]),
            promise_id=str(row["promise_id"]),
            status=str(row["status"]),
            score=float(row["score"]),
            evidence=json.loads(str(row["evidence_json"])),
            evaluated_by=str(row["evaluated_by"]),
            notes=row["notes"] if row["notes"] is None else str(row["notes"]),
            evaluated_at=str(row["evaluated_at"]),
        )

    def list_evaluations(self, promise_id: str) -> list[PromiseEvaluation]:
        rows = self.conn.execute(
            "SELECT * FROM promise_evaluations WHERE promise_id = ? ORDER BY evaluation_id",
            (promise_id,),
        ).fetchall()
        return [
            PromiseEvaluation(
                evaluation_id=int(row["evaluation_id"]),
                promise_id=str(row["promise_id"]),
                status=str(row["status"]),
                score=float(row["score"]),
                evidence=json.loads(str(row["evidence_json"])),
                evaluated_by=str(row["evaluated_by"]),
                notes=row["notes"] if row["notes"] is None else str(row["notes"]),
                evaluated_at=str(row["evaluated_at"]),
            )
            for row in rows
        ]

    def latest_evaluation(self, promise_id: str) -> PromiseEvaluation | None:
        row = self.conn.execute(
            "SELECT * FROM promise_evaluations WHERE promise_id = ? ORDER BY evaluation_id DESC LIMIT 1",
            (promise_id,),
        ).fetchone()
        if not row:
            return None
        return PromiseEvaluation(
            evaluation_id=int(row["evaluation_id"]),
            promise_id=str(row["promise_id"]),
            status=str(row["status"]),
            score=float(row["score"]),
            evidence=json.loads(str(row["evidence_json"])),
            evaluated_by=str(row["evaluated_by"]),
            notes=row["notes"] if row["notes"] is None else str(row["notes"]),
            evaluated_at=str(row["evaluated_at"]),
        )

    def record_reward_pool_funding(
        self,
        *,
        project_id: str,
        token_id: str,
        amount: float,
        tx_hash: str,
        funded_at: str,
        source: str,
        recorded_by: str,
    ) -> RewardPoolFundingRecord:
        normalized_funded_at = normalize_iso8601(funded_at)
        now = utcnow_iso()
        self.conn.execute(
            """
            INSERT OR IGNORE INTO reward_pool_funding(project_id, token_id, amount, tx_hash, funded_at, source, recorded_by, recorded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (project_id, token_id, amount, tx_hash, normalized_funded_at, source, recorded_by, now),
        )
        self.conn.commit()
        row = self.conn.execute(
            """
            SELECT * FROM reward_pool_funding
            WHERE project_id = ? AND token_id = ? AND tx_hash = ?
            """,
            (project_id, token_id, tx_hash),
        ).fetchone()
        if not row:
            raise RuntimeError("failed to read reward_pool_funding")
        return RewardPoolFundingRecord(
            funding_id=int(row["funding_id"]),
            project_id=str(row["project_id"]),
            token_id=str(row["token_id"]),
            amount=float(row["amount"]),
            tx_hash=str(row["tx_hash"]),
            funded_at=str(row["funded_at"]),
            source=str(row["source"]),
            recorded_by=str(row["recorded_by"]),
            recorded_at=str(row["recorded_at"]),
        )

    def create_reward_pool_funding(
        self,
        *,
        project_id: str,
        token_id: str,
        amount: float,
        tx_hash: str,
        funded_at: str,
        source: str,
        recorded_by: str,
    ) -> RewardPoolFundingRecord:
        return self.record_reward_pool_funding(
            project_id=project_id,
            token_id=token_id,
            amount=amount,
            tx_hash=tx_hash,
            funded_at=funded_at,
            source=source,
            recorded_by=recorded_by,
        )

    def list_reward_pool_funding(self, project_id: str) -> list[RewardPoolFundingRecord]:
        rows = self.conn.execute(
            """
            SELECT * FROM reward_pool_funding
            WHERE project_id = ?
            ORDER BY funded_at, funding_id
            """,
            (project_id,),
        ).fetchall()
        return [
            RewardPoolFundingRecord(
                funding_id=int(row["funding_id"]),
                project_id=str(row["project_id"]),
                token_id=str(row["token_id"]),
                amount=float(row["amount"]),
                tx_hash=str(row["tx_hash"]),
                funded_at=str(row["funded_at"]),
                source=str(row["source"]),
                recorded_by=str(row["recorded_by"]),
                recorded_at=str(row["recorded_at"]),
            )
            for row in rows
        ]

    def list_reward_pool_fundings(self, project_id: str) -> list[RewardPoolFundingRecord]:
        return self.list_reward_pool_funding(project_id)

    def record_credibility_snapshot(
        self,
        *,
        project_id: str,
        season: str,
        credibility_score: float,
        delivery_score: float,
        risk_score: float,
        total_promises: int,
        kept: int,
        broken: int,
        pending: int,
        snapshot_at: str,
        recorded_by: str,
    ) -> SeasonCredibilitySnapshot:
        normalized_snapshot_at = normalize_iso8601(snapshot_at)
        now = utcnow_iso()
        self.conn.execute(
            """
            INSERT OR IGNORE INTO season_credibility_snapshots(
                project_id,
                season,
                credibility_score,
                delivery_score,
                risk_score,
                total_promises,
                kept,
                broken,
                pending,
                snapshot_at,
                recorded_by,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                season,
                credibility_score,
                delivery_score,
                risk_score,
                total_promises,
                kept,
                broken,
                pending,
                normalized_snapshot_at,
                recorded_by,
                now,
            ),
        )
        self.conn.commit()
        row = self.conn.execute(
            """
            SELECT * FROM season_credibility_snapshots
            WHERE project_id = ? AND season = ? AND snapshot_at = ?
            """,
            (project_id, season, normalized_snapshot_at),
        ).fetchone()
        if not row:
            raise RuntimeError("failed to read season_credibility_snapshot")
        return SeasonCredibilitySnapshot(
            snapshot_id=int(row["snapshot_id"]),
            project_id=str(row["project_id"]),
            season=str(row["season"]),
            credibility_score=float(row["credibility_score"]),
            delivery_score=float(row["delivery_score"]),
            risk_score=float(row["risk_score"]),
            total_promises=int(row["total_promises"]),
            kept=int(row["kept"]),
            broken=int(row["broken"]),
            pending=int(row["pending"]),
            snapshot_at=str(row["snapshot_at"]),
            recorded_by=str(row["recorded_by"]),
            created_at=str(row["created_at"]),
        )

    def create_credibility_snapshot(
        self,
        *,
        project_id: str,
        season: str,
        scorecard: dict[str, float | int],
        snapshot_at: str,
        recorded_by: str,
    ) -> SeasonCredibilitySnapshot:
        return self.record_credibility_snapshot(
            project_id=project_id,
            season=season,
            credibility_score=float(scorecard.get("credibility_score", 0.0)),
            delivery_score=float(scorecard.get("delivery_score", 0.0)),
            risk_score=float(scorecard.get("risk_score", 0.0)),
            total_promises=int(scorecard.get("total_promises", 0)),
            kept=int(scorecard.get("kept", 0)),
            broken=int(scorecard.get("broken", 0)),
            pending=int(scorecard.get("pending", 0)),
            snapshot_at=snapshot_at,
            recorded_by=recorded_by,
        )

    def latest_credibility_snapshot(self, project_id: str, season: str = "s1") -> SeasonCredibilitySnapshot | None:
        rows = self.list_credibility_snapshots(project_id=project_id, season=season)
        if not rows:
            return None
        return rows[-1]

    def list_credibility_snapshots(self, project_id: str, season: str | None = None) -> list[SeasonCredibilitySnapshot]:
        if season:
            rows = self.conn.execute(
                """
                SELECT * FROM season_credibility_snapshots
                WHERE project_id = ? AND season = ?
                ORDER BY snapshot_at, snapshot_id
                """,
                (project_id, season),
            ).fetchall()
        else:
            rows = self.conn.execute(
                """
                SELECT * FROM season_credibility_snapshots
                WHERE project_id = ?
                ORDER BY snapshot_at, snapshot_id
                """,
                (project_id,),
            ).fetchall()

        return [
            SeasonCredibilitySnapshot(
                snapshot_id=int(row["snapshot_id"]),
                project_id=str(row["project_id"]),
                season=str(row["season"]),
                credibility_score=float(row["credibility_score"]),
                delivery_score=float(row["delivery_score"]),
                risk_score=float(row["risk_score"]),
                total_promises=int(row["total_promises"]),
                kept=int(row["kept"]),
                broken=int(row["broken"]),
                pending=int(row["pending"]),
                snapshot_at=str(row["snapshot_at"]),
                recorded_by=str(row["recorded_by"]),
                created_at=str(row["created_at"]),
            )
            for row in rows
        ]

    def record_founder_distribution_summary(
        self,
        *,
        project_id: str,
        token_id: str,
        founder_wallets: int,
        distributed_amount: float,
        locked_amount: float,
        as_of: str,
        source: str,
        recorded_by: str,
    ) -> FounderDistributionSummary:
        normalized_as_of = normalize_iso8601(as_of)
        now = utcnow_iso()
        self.conn.execute(
            """
            INSERT OR IGNORE INTO founder_distribution_summaries(
                project_id,
                token_id,
                founder_wallets,
                distributed_amount,
                locked_amount,
                as_of,
                source,
                recorded_by,
                recorded_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                token_id,
                founder_wallets,
                distributed_amount,
                locked_amount,
                normalized_as_of,
                source,
                recorded_by,
                now,
            ),
        )
        self.conn.commit()
        row = self.conn.execute(
            """
            SELECT * FROM founder_distribution_summaries
            WHERE project_id = ? AND token_id = ? AND as_of = ? AND source = ?
            """,
            (project_id, token_id, normalized_as_of, source),
        ).fetchone()
        if not row:
            raise RuntimeError("failed to read founder_distribution_summary")
        return FounderDistributionSummary(
            summary_id=int(row["summary_id"]),
            project_id=str(row["project_id"]),
            token_id=str(row["token_id"]),
            founder_wallets=int(row["founder_wallets"]),
            distributed_amount=float(row["distributed_amount"]),
            locked_amount=float(row["locked_amount"]),
            as_of=str(row["as_of"]),
            source=str(row["source"]),
            recorded_by=str(row["recorded_by"]),
            recorded_at=str(row["recorded_at"]),
        )

    def create_founder_distribution_summary(
        self,
        *,
        project_id: str,
        token_id: str,
        founder_wallets: int,
        distributed_amount: float,
        locked_amount: float,
        as_of: str,
        source: str,
        recorded_by: str,
    ) -> FounderDistributionSummary:
        return self.record_founder_distribution_summary(
            project_id=project_id,
            token_id=token_id,
            founder_wallets=founder_wallets,
            distributed_amount=distributed_amount,
            locked_amount=locked_amount,
            as_of=as_of,
            source=source,
            recorded_by=recorded_by,
        )

    def list_founder_distribution_summaries(self, project_id: str) -> list[FounderDistributionSummary]:
        rows = self.conn.execute(
            """
            SELECT * FROM founder_distribution_summaries
            WHERE project_id = ?
            ORDER BY as_of, summary_id
            """,
            (project_id,),
        ).fetchall()
        return [
            FounderDistributionSummary(
                summary_id=int(row["summary_id"]),
                project_id=str(row["project_id"]),
                token_id=str(row["token_id"]),
                founder_wallets=int(row["founder_wallets"]),
                distributed_amount=float(row["distributed_amount"]),
                locked_amount=float(row["locked_amount"]),
                as_of=str(row["as_of"]),
                source=str(row["source"]),
                recorded_by=str(row["recorded_by"]),
                recorded_at=str(row["recorded_at"]),
            )
            for row in rows
        ]
