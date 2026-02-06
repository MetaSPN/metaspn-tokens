from __future__ import annotations

import json
import sqlite3
import uuid
from typing import Any

from .models import PromiseEvaluation, PromiseRecord, Token, TokenProjectLink, utcnow_iso


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
        return Token(
            token_id=str(row["token_id"]),
            symbol=str(row["symbol"]),
            name=str(row["name"]),
            chain=str(row["chain"]),
            address=str(row["address"]),
            metadata=json.loads(str(row["metadata_json"])),
            created_at=str(row["created_at"]),
        )

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
        return [
            Token(
                token_id=str(row["token_id"]),
                symbol=str(row["symbol"]),
                name=str(row["name"]),
                chain=str(row["chain"]),
                address=str(row["address"]),
                metadata=json.loads(str(row["metadata_json"])),
                created_at=str(row["created_at"]),
            )
            for row in rows
        ]

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
