"""SQLite store shared by every stream. One file, plain tables, JSON columns for stream-specific detail."""
import json
import os
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = Path(os.environ.get("STUDIO_DB") or ROOT / "studio" / "data" / "studio.db")   # STUDIO_DB: a test copy

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id          TEXT PRIMARY KEY,          -- e.g. yt-cookedorcracked
    stream      TEXT NOT NULL,             -- clipping | influencer | youtube
    platform    TEXT NOT NULL,             -- youtube | instagram
    handle      TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    status      TEXT NOT NULL DEFAULT 'warming',   -- warming | active | paused | banned
    data        TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS campaigns (
    id          TEXT PRIMARY KEY,
    stream      TEXT NOT NULL DEFAULT 'clipping',
    name        TEXT NOT NULL,
    source_url  TEXT,
    added_at    TEXT NOT NULL DEFAULT (datetime('now')),
    verdict     TEXT,                      -- TAKE | MAYBE | SKIP
    score       INTEGER,
    status      TEXT NOT NULL DEFAULT 'candidate',  -- candidate | joined | ended | skipped
    data        TEXT NOT NULL              -- full brief as JSON
);

CREATE TABLE IF NOT EXISTS clips (
    id          TEXT PRIMARY KEY,
    stream      TEXT NOT NULL,
    campaign_id TEXT REFERENCES campaigns(id),
    account_id  TEXT REFERENCES accounts(id),
    status      TEXT NOT NULL DEFAULT 'planned',  -- planned | rendering | checks | needs_review | approved | posted | submitted | paid | rejected
    version     INTEGER NOT NULL DEFAULT 1,      -- current recipe version
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
    data        TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS clip_versions (
    clip_id     TEXT NOT NULL REFERENCES clips(id),
    version     INTEGER NOT NULL,
    recipe      TEXT NOT NULL,             -- timeline JSON
    note        TEXT,                      -- what changed and why
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (clip_id, version)
);

CREATE TABLE IF NOT EXISTS posts (
    id          TEXT PRIMARY KEY,
    clip_id     TEXT NOT NULL REFERENCES clips(id),
    account_id  TEXT NOT NULL REFERENCES accounts(id),
    url         TEXT,
    posted_at   TEXT,
    submitted_at TEXT,
    payout_usd  REAL,
    data        TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS metrics (
    post_id     TEXT NOT NULL REFERENCES posts(id),
    taken_at    TEXT NOT NULL DEFAULT (datetime('now')),
    views       INTEGER,
    likes       INTEGER,
    comments    INTEGER,
    avg_view_pct REAL,
    tier1_pct   REAL,
    data        TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS notes (          -- "notes at a moment" left on a clip while reviewing
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    clip_id     TEXT NOT NULL,
    version     INTEGER,
    t           REAL,                      -- seconds into the video
    text        TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    resolved_at TEXT
);

CREATE TABLE IF NOT EXISTS requests (       -- messages for Claude sent from the dashboard ("tell Claude")
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    room        TEXT NOT NULL DEFAULT 'hq',
    text        TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    done_at     TEXT
);

CREATE TABLE IF NOT EXISTS asks (           -- questions Claude leaves for Rishi, answered with one tap
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    room        TEXT NOT NULL DEFAULT 'hq',
    question    TEXT NOT NULL,
    options     TEXT NOT NULL DEFAULT '[]', -- JSON list of button labels
    answer      TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    answered_at TEXT
);

CREATE TABLE IF NOT EXISTS finds (            -- things Rishi spots online (repos, tools, reels) kept for later; no action taken
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    url         TEXT,
    title       TEXT NOT NULL,
    note        TEXT,                      -- what it is + how we might use it
    tags        TEXT,                      -- comma-separated, e.g. "stickman, ai video"
    source      TEXT,                      -- where he found it (Instagram reel, friend…)
    added_at    TEXT NOT NULL DEFAULT (datetime('now')),
    archived_at TEXT
);

CREATE TABLE IF NOT EXISTS events (
    at          TEXT NOT NULL DEFAULT (datetime('now')),
    stream      TEXT,
    kind        TEXT NOT NULL,             -- e.g. campaign.scored, clip.approved
    ref         TEXT,
    detail      TEXT
);
"""


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")          # the dashboard reads while chat/CLI writes
    con.executescript(SCHEMA)
    return con


def log_event(con: sqlite3.Connection, kind: str, ref: str = None, detail=None, stream: str = None):
    con.execute(
        "INSERT INTO events (stream, kind, ref, detail) VALUES (?, ?, ?, ?)",
        (stream, kind, ref, json.dumps(detail) if detail is not None else None),
    )
