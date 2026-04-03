"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-04-02

"""
from alembic import op

revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            path        TEXT UNIQUE NOT NULL,
            name        TEXT NOT NULL,
            size_bytes  INTEGER,
            media_info  TEXT,
            first_seen  TEXT NOT NULL,
            last_seen   TEXT NOT NULL
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS operations (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id         INTEGER NOT NULL REFERENCES files(id),
            type            TEXT NOT NULL,
            started_at      TEXT NOT NULL,
            finished_at     TEXT,
            status          TEXT NOT NULL DEFAULT 'started',
            params          TEXT,
            snapshot_before TEXT,
            backup_path     TEXT,
            backup_deleted  INTEGER NOT NULL DEFAULT 0
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS audio_tracks (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            source_file_id  INTEGER NOT NULL REFERENCES files(id),
            track_index     INTEGER NOT NULL,
            title           TEXT,
            language        TEXT,
            codec           TEXT,
            bitrate         TEXT,
            channels        INTEGER,
            path            TEXT NOT NULL,
            created_at      TEXT NOT NULL
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_superadmin INTEGER NOT NULL DEFAULT 0,
            created_at    TEXT NOT NULL
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS app_stats (
            key        TEXT PRIMARY KEY,
            value      TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER,
            type       TEXT NOT NULL DEFAULT 'info',
            title      TEXT NOT NULL,
            message    TEXT,
            is_read    INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS notifications")
    op.execute("DROP TABLE IF EXISTS app_stats")
    op.execute("DROP TABLE IF EXISTS users")
    op.execute("DROP TABLE IF EXISTS audio_tracks")
    op.execute("DROP TABLE IF EXISTS operations")
    op.execute("DROP TABLE IF EXISTS files")
