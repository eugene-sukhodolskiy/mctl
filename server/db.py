import sqlite3
import json
import os
from datetime import datetime, timezone
from contextlib import contextmanager

DB_PATH = os.environ.get('MCTL_DB_PATH', 'data/medialib.db')


os.makedirs(os.path.dirname(DB_PATH) or '.', exist_ok=True)


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


AUDIO_CODEC_EXT = {
    "aac":   ".aac",
    "ac3":   ".ac3",
    "eac3":  ".eac3",
    "mp3":   ".mp3",
    "flac":  ".flac",
    "opus":  ".opus",
    "vorbis": ".ogg",
    "dts":   ".dts",
}




def upsert_file(path, name, size_bytes, media_info):
    now = datetime.now(timezone.utc).isoformat()
    media_info_json = json.dumps(media_info) if media_info is not None else None
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO files (path, name, size_bytes, media_info, first_seen, last_seen)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                name       = excluded.name,
                size_bytes = excluded.size_bytes,
                media_info = excluded.media_info,
                last_seen  = excluded.last_seen
        """, (path, name, size_bytes, media_info_json, now, now))
        conn.commit()
        row = conn.execute("SELECT id FROM files WHERE path = ?", (path,)).fetchone()
        return row["id"]


def get_file_path_by_id(file_id):
    with get_connection() as conn:
        row = conn.execute("SELECT path FROM files WHERE id = ?", (file_id,)).fetchone()
        return row["path"] if row else None


def get_file_by_path(path):
    with get_connection() as conn:
        return conn.execute("SELECT * FROM files WHERE path = ?", (path,)).fetchone()


def create_operation(file_id, op_type, params, snapshot_before, backup_path):
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO operations (file_id, type, started_at, status, params, snapshot_before, backup_path)
            VALUES (?, ?, ?, 'started', ?, ?, ?)
        """, (
            file_id,
            op_type,
            now,
            json.dumps(params) if params is not None else None,
            json.dumps(snapshot_before) if snapshot_before is not None else None,
            backup_path
        ))
        conn.commit()
        return cursor.lastrowid


def update_operation(operation_id, status):
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            "UPDATE operations SET status = ?, finished_at = ? WHERE id = ?",
            (status, now, operation_id)
        )
        conn.commit()


def get_operation_by_id(operation_id):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM operations WHERE id = ?", (operation_id,)).fetchone()
        return dict(row) if row else None


def get_file_operations(path):
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT o.*
            FROM operations o
            JOIN files f ON f.id = o.file_id
            WHERE f.path = ?
            ORDER BY o.started_at DESC
        """, (path,)).fetchall()
        return [dict(row) for row in rows]


def get_all_files():
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM files ORDER BY name").fetchall()
        return list(rows) if rows else None


def create_audio_track(source_file_id, track_index, title, language, codec, bitrate, channels, path):
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO audio_tracks (source_file_id, track_index, title, language, codec, bitrate, channels, path, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (source_file_id, track_index, title, language, codec, bitrate, channels, path, now))
        conn.commit()
        return cursor.lastrowid


def get_all_audio_tracks():
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT at.*, f.name AS source_name, f.path AS source_path
            FROM audio_tracks at
            JOIN files f ON f.id = at.source_file_id
            ORDER BY at.created_at DESC
        """).fetchall()
        return [dict(r) for r in rows]


def get_audio_track_by_id(track_id):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM audio_tracks WHERE id = ?", (track_id,)).fetchone()
        return dict(row) if row else None


def delete_audio_track(track_id):
    with get_connection() as conn:
        conn.execute("DELETE FROM audio_tracks WHERE id = ?", (track_id,))
        conn.commit()


def mark_backup_deleted(operation_id):
    with get_connection() as conn:
        conn.execute(
            "UPDATE operations SET backup_deleted = 1, backup_path = NULL WHERE id = ?",
            (operation_id,)
        )
        conn.commit()


def get_latest_operation_by_backup_path(backup_path):
    """Return the most recent operation record for a given backup file path."""
    with get_connection() as conn:
        row = conn.execute("""
            SELECT o.id AS operation_id, o.started_at, o.backup_path,
                   f.id AS file_id, f.name AS source_name, f.path AS source_path
            FROM operations o
            JOIN files f ON f.id = o.file_id
            WHERE o.backup_path = ?
            ORDER BY o.started_at DESC
            LIMIT 1
        """, (backup_path,)).fetchone()
        return dict(row) if row else None


def get_file_backup_paths(file_id):
    """Return all non-null backup_paths for a file's operations."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT backup_path FROM operations WHERE file_id = ? AND backup_path IS NOT NULL AND backup_deleted = 0",
            (file_id,)
        ).fetchall()
        return [row["backup_path"] for row in rows]


def delete_file_record(file_id):
    """Delete operations history and file record. Audio tracks are kept."""
    with get_connection() as conn:
        conn.execute("DELETE FROM operations WHERE file_id = ?", (file_id,))
        conn.execute("DELETE FROM files WHERE id = ?", (file_id,))
        conn.commit()


def get_users_count():
    with get_connection() as conn:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]


def create_user(username, password_hash, is_superadmin=False):
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO users (username, password_hash, is_superadmin, created_at) VALUES (?, ?, ?, ?)",
            (username, password_hash, 1 if is_superadmin else 0, now)
        )
        conn.commit()


def get_user_by_username(username):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def update_user_password(user_id, password_hash):
    with get_connection() as conn:
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id))
        conn.commit()


def get_app_stats():
    with get_connection() as conn:
        row = conn.execute("SELECT value FROM app_stats WHERE key = 'transcoding_stats'").fetchone()
        if row:
            return json.loads(row['value'])
    return None


def calculate_and_save_stats():
    """Recalculate transcoding savings from DB and cache the result."""
    with get_connection() as conn:
        # Total distinct files with at least one completed transcoding op
        transcoded_count = conn.execute("""
            SELECT COUNT(DISTINCT file_id) FROM operations
            WHERE type = 'transcoding' AND status = 'completed'
        """).fetchone()[0]

        # For each file: first completed transcoding op
        rows = conn.execute("""
            SELECT f.size_bytes AS current_size, o.params, o.backup_path
            FROM files f
            JOIN operations o ON o.file_id = f.id
            WHERE o.type = 'transcoding' AND o.status = 'completed'
            AND o.started_at = (
                SELECT MIN(o2.started_at) FROM operations o2
                WHERE o2.file_id = f.id
                AND o2.type = 'transcoding' AND o2.status = 'completed'
            )
        """).fetchall()

    total_original = 0
    total_current = 0

    for row in rows:
        current_size = row['current_size']
        if not current_size:
            continue

        original_size = None
        if row['params']:
            try:
                original_size = json.loads(row['params']).get('original_size_bytes')
            except Exception:
                pass

        if not original_size and row['backup_path']:
            import os as _os
            if _os.path.exists(row['backup_path']):
                original_size = _os.path.getsize(row['backup_path'])

        if original_size and original_size > current_size:
            total_original += original_size
            total_current += current_size

    saved_bytes = total_original - total_current
    percent_saved = round(saved_bytes / total_original * 100, 1) if total_original > 0 else 0

    stats = {
        'transcoded_count': transcoded_count,
        'saved_bytes': saved_bytes,
        'total_original_bytes': total_original,
        'percent_saved': percent_saved,
    }

    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO app_stats (key, value, updated_at) VALUES ('transcoding_stats', ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
        """, (json.dumps(stats), now))
        conn.commit()

    return stats


def update_file_media_info(path, size_bytes, media_info):
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute("""
            UPDATE files SET size_bytes = ?, media_info = ?, last_seen = ? WHERE path = ?
        """, (size_bytes, json.dumps(media_info) if media_info is not None else None, now, path))
        conn.commit()


def create_notification(user_id, notif_type, title, message):
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO notifications (user_id, type, title, message, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, notif_type, title, message, now)
        )
        conn.commit()
        return cursor.lastrowid


def get_notifications(user_id=None, limit=100):
    with get_connection() as conn:
        if user_id is not None:
            rows = conn.execute(
                "SELECT * FROM notifications WHERE user_id IS NULL OR user_id = ? ORDER BY created_at DESC LIMIT ?",
                (user_id, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM notifications ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]


def get_unread_count(user_id=None):
    with get_connection() as conn:
        if user_id is not None:
            return conn.execute(
                "SELECT COUNT(*) FROM notifications WHERE is_read = 0 AND (user_id IS NULL OR user_id = ?)",
                (user_id,)
            ).fetchone()[0]
        return conn.execute("SELECT COUNT(*) FROM notifications WHERE is_read = 0").fetchone()[0]


def mark_notification_read(notif_id):
    with get_connection() as conn:
        conn.execute("UPDATE notifications SET is_read = 1 WHERE id = ?", (notif_id,))
        conn.commit()


def mark_all_notifications_read(user_id=None):
    with get_connection() as conn:
        if user_id is not None:
            conn.execute(
                "UPDATE notifications SET is_read = 1 WHERE user_id IS NULL OR user_id = ?",
                (user_id,)
            )
        else:
            conn.execute("UPDATE notifications SET is_read = 1")
        conn.commit()


def delete_notification(notif_id):
    with get_connection() as conn:
        conn.execute("DELETE FROM notifications WHERE id = ?", (notif_id,))
        conn.commit()


def delete_all_notifications(user_id=None):
    with get_connection() as conn:
        if user_id is not None:
            conn.execute(
                "DELETE FROM notifications WHERE user_id IS NULL OR user_id = ?",
                (user_id,)
            )
        else:
            conn.execute("DELETE FROM notifications")
        conn.commit()
