"""SQLite unit-of-work store. Single-process async service; no network I/O inside transactions."""

import hashlib
import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from jewelmentor.models import ChatRequest, Message, State, TurnResult


class Conflict(Exception):
    pass


def encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


class Store:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY, created REAL NOT NULL, memory TEXT NOT NULL DEFAULT '{}');
                CREATE TABLE IF NOT EXISTS turns (
                    id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    request_id TEXT NOT NULL, fingerprint TEXT NOT NULL, request TEXT NOT NULL,
                    trace_id TEXT NOT NULL, state TEXT NOT NULL, checkpoint TEXT NOT NULL DEFAULT '{}',
                    result TEXT, provider TEXT NOT NULL, deadline REAL NOT NULL,
                    UNIQUE(session_id, request_id));
                CREATE TABLE IF NOT EXISTS messages (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    turn_id TEXT NOT NULL REFERENCES turns(id) ON DELETE CASCADE,
                    role TEXT NOT NULL, content TEXT NOT NULL, UNIQUE(turn_id, role));
                CREATE TABLE IF NOT EXISTS events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL,
                    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    turn_id TEXT NOT NULL REFERENCES turns(id) ON DELETE CASCADE,
                    trace_id TEXT NOT NULL, node TEXT NOT NULL, state TEXT NOT NULL,
                    timestamp REAL NOT NULL, attempt INTEGER NOT NULL DEFAULT 0,
                    elapsed_ms REAL NOT NULL DEFAULT 0, error_category TEXT);
                CREATE INDEX IF NOT EXISTS events_session ON events(session_id, seq);
                CREATE INDEX IF NOT EXISTS messages_session ON messages(session_id, seq);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def create_session(self):
        sid = uuid4().hex
        with self.connect() as db:
            db.execute("INSERT INTO sessions(id,created) VALUES(?,?)", (sid, time.time()))
        return self.session(sid)

    def session(self, sid):
        with self.connect() as db:
            row = db.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
            if row is None:
                raise KeyError(sid)
            messages = [dict(r) for r in db.execute("SELECT role,content,turn_id FROM messages WHERE session_id=? ORDER BY seq", (sid,))]
            turns = [dict(r) for r in db.execute("SELECT id,state,trace_id,request_id FROM turns WHERE session_id=? ORDER BY rowid", (sid,))]
            return {"id": sid, "created": row["created"], "memory": json.loads(row["memory"]), "messages": messages, "turns": turns}

    def trace(self, sid):
        with self.connect() as db:
            return [dict(r) for r in db.execute("SELECT * FROM events WHERE session_id=? ORDER BY seq", (sid,))]

    def delete_session(self, sid):
        with self.connect() as db:
            if not db.execute("DELETE FROM sessions WHERE id=?", (sid,)).rowcount:
                raise KeyError(sid)

    def prepare(self, sid: str, request: ChatRequest, provider: str, timeout: float):
        payload = request.model_dump_json()
        fingerprint = hashlib.sha256(payload.encode()).hexdigest()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM sessions WHERE id=?", (sid,)).fetchone() is None:
                raise KeyError(sid)
            old = db.execute("SELECT * FROM turns WHERE session_id=? AND request_id=?", (sid, request.request_id)).fetchone()
            if old:
                if old["fingerprint"] != fingerprint:
                    raise Conflict("request_id already belongs to a different payload")
                return dict(old)
            pending = db.execute("SELECT 1 FROM turns WHERE session_id=? AND result IS NULL", (sid,)).fetchone()
            if pending:
                raise Conflict("an interrupted turn requires recovery before a new message")
            tid, trace = uuid4().hex, uuid4().hex
            db.execute("INSERT INTO turns(id,session_id,request_id,fingerprint,request,trace_id,state,provider,deadline) VALUES(?,?,?,?,?,?,?,?,?)",
                       (tid, sid, request.request_id, fingerprint, payload, trace, State.PENDING.value, provider, time.time() + timeout))
            db.execute("INSERT INTO messages(session_id,turn_id,role,content) VALUES(?,?,?,?)", (sid, tid, "user", request.message))
            return dict(db.execute("SELECT * FROM turns WHERE id=?", (tid,)).fetchone())

    def turn(self, sid, tid):
        with self.connect() as db:
            row = db.execute("SELECT * FROM turns WHERE session_id=? AND id=?", (sid, tid)).fetchone()
            if row is None:
                raise KeyError(tid)
            return dict(row)

    def update(self, turn, state, checkpoint, node, attempt=0, elapsed_ms=0, error=None):
        with self.connect() as db:
            db.execute("UPDATE turns SET state=?,checkpoint=? WHERE id=?", (state.value, encode(checkpoint), turn["id"]))
            self._event(db, turn, state, node, attempt, elapsed_ms, error)
        turn["state"], turn["checkpoint"] = state.value, encode(checkpoint)

    def _event(self, db, turn, state, node, attempt, elapsed_ms, error):
        db.execute("INSERT INTO events(id,session_id,turn_id,trace_id,node,state,timestamp,attempt,elapsed_ms,error_category) VALUES(?,?,?,?,?,?,?,?,?,?)",
                   (uuid4().hex, turn["session_id"], turn["id"], turn["trace_id"], node, state.value, time.time(), attempt, round(elapsed_ms, 2), error))

    def finish(self, turn, result: TurnResult, memory):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("INSERT INTO messages(session_id,turn_id,role,content) VALUES(?,?,?,?)", (turn["session_id"], turn["id"], "assistant", result.answer))
            db.execute("UPDATE turns SET state=?,result=? WHERE id=?", (result.state.value, result.model_dump_json(), turn["id"]))
            db.execute("UPDATE sessions SET memory=? WHERE id=?", (encode(memory), turn["session_id"]))
            self._event(db, turn, result.state, "dialogue", 0, 0, result.error_category)

    def context(self, sid):
        session = self.session(sid)
        selected, length = [], 0
        for msg in reversed(session["messages"]):
            if len(selected) >= 12 or length + len(msg["content"]) > 18000:
                break
            selected.append(Message(role=msg["role"], content=msg["content"]))
            length += len(msg["content"])
        return list(reversed(selected)), session["memory"]
