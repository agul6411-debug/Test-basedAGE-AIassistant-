"""SQLite Database interface for desktop layout snapshot storage and retention.

Security Rule 13: Layout data lives strictly inside data/.
Auto-prunes snapshots to retain only the last 10 snapshots.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.logger import get_logger
from core.safety.path_validator import validate_path_within_root

logger = get_logger("layout.db")


class LayoutDB:
    """Manages SQLite storage for window placements and desktop icon snapshots."""

    def __init__(self, db_path: str | Path = "data/layout.db", base_dir: str | Path | None = None) -> None:
        """Initialize LayoutDB.

        Args:
            db_path: Path to SQLite database file inside data/.
            base_dir: Optional base confinement directory.
        """
        root = Path(base_dir).resolve() if base_dir else Path.cwd().resolve()
        data_root = (root / "data").resolve()
        data_root.mkdir(parents=True, exist_ok=True)

        p = Path(db_path)
        if p.is_absolute():
            target = p.resolve()
        elif p.parts and p.parts[0] == "data":
            target = (root / p).resolve()
        else:
            target = (data_root / p).resolve()

        self.db_path = validate_path_within_root(target, data_root)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        """Open SQLite connection with foreign key support."""
        conn = sqlite3.connect(str(self.db_path), timeout=5.0)
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        """Create tables and indexes if they do not exist."""
        with self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    trigger_type TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS window_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    snapshot_id INTEGER NOT NULL REFERENCES snapshots(id) ON DELETE CASCADE,
                    app_name TEXT NOT NULL,
                    process_name TEXT NOT NULL,
                    title TEXT NOT NULL,
                    x INTEGER NOT NULL,
                    y INTEGER NOT NULL,
                    width INTEGER NOT NULL,
                    height INTEGER NOT NULL,
                    state TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS icon_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    snapshot_id INTEGER NOT NULL REFERENCES snapshots(id) ON DELETE CASCADE,
                    icon_name TEXT NOT NULL,
                    x INTEGER NOT NULL,
                    y INTEGER NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_window_snapshot ON window_entries(snapshot_id);
                CREATE INDEX IF NOT EXISTS idx_icon_snapshot ON icon_entries(snapshot_id);
            """)

    def save_snapshot(
        self,
        trigger_type: str,
        windows: list[dict[str, Any]],
        icons: list[dict[str, Any]],
        max_snapshots: int = 10,
    ) -> int:
        """Insert a new layout snapshot and prune older snapshots beyond retention limit.

        Args:
            trigger_type: 'manual', 'autosave', or 'shutdown'.
            windows: List of window placement dictionaries.
            icons: List of desktop icon position dictionaries.
            max_snapshots: Maximum number of snapshots to retain (default: 10).

        Returns:
            The newly created snapshot ID.
        """
        now_iso = datetime.now(timezone.utc).isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO snapshots (timestamp, trigger_type) VALUES (?, ?);",
                (now_iso, trigger_type),
            )
            snapshot_id = cursor.lastrowid
            assert snapshot_id is not None  # nosec: B101

            # Insert window entries
            for w in windows:
                cursor.execute(
                    """
                    INSERT INTO window_entries
                    (snapshot_id, app_name, process_name, title, x, y, width, height, state)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        snapshot_id,
                        w.get("app_name", ""),
                        w.get("process_name", ""),
                        w.get("title", ""),
                        int(w.get("x", 0)),
                        int(w.get("y", 0)),
                        int(w.get("width", 0)),
                        int(w.get("height", 0)),
                        w.get("state", "normal"),
                    ),
                )

            # Insert icon entries
            for ic in icons:
                cursor.execute(
                    """
                    INSERT INTO icon_entries (snapshot_id, icon_name, x, y)
                    VALUES (?, ?, ?, ?);
                    """,
                    (
                        snapshot_id,
                        ic.get("icon_name", ""),
                        int(ic.get("x", 0)),
                        int(ic.get("y", 0)),
                    ),
                )

            # Prune snapshots beyond max_snapshots
            cursor.execute(
                "DELETE FROM snapshots WHERE id NOT IN (SELECT id FROM snapshots ORDER BY id DESC LIMIT ?);",
                (max_snapshots,),
            )
            conn.commit()

        logger.info(
            "Saved layout snapshot #%d (%s): %d windows, %d icons.",
            snapshot_id,
            trigger_type,
            len(windows),
            len(icons),
        )
        return snapshot_id

    def get_snapshots(self, limit: int = 10) -> list[dict[str, Any]]:
        """Retrieve recent snapshots summary."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, timestamp, trigger_type FROM snapshots ORDER BY id DESC LIMIT ?;", (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_latest_snapshot(self) -> dict[str, Any] | None:
        """Retrieve the most recent layout snapshot with complete window and icon entries."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, timestamp, trigger_type FROM snapshots ORDER BY id DESC LIMIT 1;")
            row = cursor.fetchone()
            if not row:
                return None

            snap_id = row["id"]
            cursor.execute("SELECT * FROM window_entries WHERE snapshot_id = ?;", (snap_id,))
            windows = [dict(w) for w in cursor.fetchall()]

            cursor.execute("SELECT * FROM icon_entries WHERE snapshot_id = ?;", (snap_id,))
            icons = [dict(ic) for ic in cursor.fetchall()]

            return {
                "id": snap_id,
                "timestamp": row["timestamp"],
                "trigger_type": row["trigger_type"],
                "windows": windows,
                "icons": icons,
            }
