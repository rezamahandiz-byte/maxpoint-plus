"""Backup — JSON export and import.

Export: writes every table to a JSON file the user picks. The file contains
a `version` field for forward-compatible restores.

Import: reads the JSON file, validates the schema, and replaces all tables
inside a single transaction. The UI is expected to confirm with the user
twice before calling `restore_from_dict` — the function itself does not
ask for confirmation.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from core import db

BACKUP_VERSION = 1

# Order matters: child tables first (so FK constraints don't fire on DELETE),
# parent tables last. Insert happens in reverse, which is FK-safe.
_BACKUP_TABLES = [
    "settings",
    "reports",
    "exam_subjects",
    "exams",
    "sessions",
    "goals",
    "weekly_goals",
    "activities",
    "activity_groups",
]

# Insert order = reverse of delete order.
_INSERT_ORDER = list(reversed(_BACKUP_TABLES))


# --------------------------------------------------------------------------- #
# Export
# --------------------------------------------------------------------------- #


# [Ch7] Transient settings that should NOT be included in backup
_TRANSIENT_SETTINGS_KEYS = {
    "clock_sync_offset_seconds", "clock_sync_last_utc", "clock_sync_status",
    "clock_tamper_detected",
    "active_study_started_at", "active_study_activity_id", "active_study_kind",
    "active_study_activity_name", "active_study_test_count",
    "active_study_paused_at", "active_study_paused_seconds",
    "notif_silenced_until", "notif_next_check_at", "notif_last_shown",
}


def export_to_dict() -> dict[str, Any]:
    """Read every table into a JSON-serialisable dict.
    [Ch7] Excludes transient settings (clock sync, active timer, notifier state)."""
    out: dict[str, Any] = {
        "version": BACKUP_VERSION,
        "app": "MAXPOINT",
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "tables": {},
    }
    for table in _BACKUP_TABLES:
        rows = db.fetch_all(f"SELECT * FROM {table};")
        if table == "settings":
            # [Ch7] Filter out transient keys
            rows = [r for r in rows if r["key"] not in _TRANSIENT_SETTINGS_KEYS]
        out["tables"][table] = [dict(r) for r in rows]
    return out


def export_to_file(path: str | os.PathLike) -> Path:
    """Write the backup dict to `path` as pretty JSON. Returns the Path."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = export_to_dict()
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


# --------------------------------------------------------------------------- #
# Import
# --------------------------------------------------------------------------- #


def restore_from_dict(data: dict[str, Any]) -> dict[str, int]:
    """Replace every table with the contents of `data`.

    Returns a {table_name: rows_written} dict for the UI to show.

    Safety:
        - Runs inside a single transaction; rolls back on any error.
        - Skips unknown tables.
        - Always preserves the schema (deletes rows, not the table).
        - Re-runs the seed AFTER clearing only if no activities remain
          (so a blank restore still leaves the app usable).
    """
    tables_data = data.get("tables")
    if not isinstance(tables_data, dict):
        raise ValueError("ساختار فایل پشتیبان معتبر نیست.")
    try:
        version = int(data.get("version", 0))
    except (TypeError, ValueError) as exc:
        raise ValueError("نسخه‌ی فایل پشتیبان معتبر نیست.") from exc
    if version > BACKUP_VERSION:
        raise ValueError("این فایل با نسخه‌ی جدیدتری از MAXPOINT ساخته شده و قابل بازیابی نیست.")

    # Validate all rows before the first DELETE. Older backups may omit new
    # columns (SQLite defaults will fill them), but may not inject columns or
    # mix incompatible row shapes inside the same table.
    validated_rows: dict[str, tuple[list[str], list[tuple]]] = {}
    with db.connect() as conn:
        for table in _BACKUP_TABLES:
            rows = tables_data.get(table, [])
            if not isinstance(rows, list):
                raise ValueError(f"بخش «{table}» در فایل پشتیبان معتبر نیست.")
            schema_columns = {r[1] for r in conn.execute(f"PRAGMA table_info({table});").fetchall()}
            columns: list[str] = []
            values: list[tuple] = []
            expected_keys = None
            for row in rows:
                if not isinstance(row, dict):
                    raise ValueError(f"یک رکورد در بخش «{table}» معتبر نیست.")
                keys = set(row.keys())
                unknown = keys - schema_columns
                if unknown:
                    raise ValueError(f"فایل پشتیبان دارای فیلد ناشناخته در «{table}» است: {', '.join(sorted(unknown))}")
                if expected_keys is None:
                    expected_keys = keys
                    columns = list(row.keys())
                elif keys != expected_keys:
                    raise ValueError(f"ساختار رکوردهای بخش «{table}» یکسان نیست.")
                values.append(tuple(row[c] for c in columns))
            validated_rows[table] = (columns, values)

    counts: dict[str, int] = {}
    with db.connect() as conn:
        cur = conn.cursor()
        # 1. Delete in child-first order (FK-safe).
        for table in _BACKUP_TABLES:
            cur.execute(f"DELETE FROM {table};")
        # 2. Insert in parent-first order (FK-safe).
        for table in _INSERT_ORDER:
            cols, values = validated_rows[table]
            if values:
                placeholders = ",".join("?" * len(cols))
                sql = (
                    f"INSERT OR REPLACE INTO {table} "
                    f"({','.join(cols)}) VALUES ({placeholders});"
                )
                cur.executemany(sql, values)
                counts[table] = len(values)
            else:
                counts[table] = 0

    # Re-seed if the restore left the app empty (rare but possible).
    from core import models as _m
    if not _m.list_activities(active_only=False):
        with db.connect() as conn:
            db._seed(conn)

    return counts


def restore_from_file(path: str | os.PathLike) -> dict[str, int]:
    """Read a JSON backup file and replace all tables. Throws on bad JSON."""
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    data = json.loads(text)
    if not isinstance(data, dict) or "tables" not in data:
        raise ValueError("فایل پشتیبان معتبر نیست.")
    return restore_from_dict(data)
