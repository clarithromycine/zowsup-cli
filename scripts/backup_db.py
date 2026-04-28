#!/usr/bin/env python
"""
scripts/backup_db.py
────────────────────
Back up dashboard.db using SQLite's online backup API (safe while the
server is running — no table locks, no corruption risk).

Usage
-----
  python scripts/backup_db.py                      # backup to data/backups/
  python scripts/backup_db.py --dest /my/backups   # custom destination
  python scripts/backup_db.py --keep 7             # keep last 7 backups

The backup file is named:
  dashboard_<YYYYMMDD_HHMMSS>.db

Exit codes
----------
  0  success
  1  source DB not found
  2  backup failed
"""

import argparse
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# Project root is one level above scripts/
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Backup dashboard.db")
    p.add_argument(
        "--source",
        default=str(PROJECT_ROOT / "data" / "dashboard.db"),
        help="Path to source dashboard.db (default: data/dashboard.db)",
    )
    p.add_argument(
        "--dest",
        default=str(PROJECT_ROOT / "data" / "backups"),
        help="Destination directory for backup files (default: data/backups/)",
    )
    p.add_argument(
        "--keep",
        type=int,
        default=30,
        help="Number of recent backups to retain; older ones are deleted (default: 30)",
    )
    return p.parse_args()


def backup(source: Path, dest_dir: Path) -> Path:
    """
    Use sqlite3.Connection.backup() to safely copy a live SQLite database.
    Returns the path of the newly created backup file.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest_file = dest_dir / f"dashboard_{timestamp}.db"

    src_conn = sqlite3.connect(str(source))
    dst_conn = sqlite3.connect(str(dest_file))
    try:
        src_conn.backup(dst_conn)
    finally:
        dst_conn.close()
        src_conn.close()

    return dest_file


def prune(dest_dir: Path, keep: int) -> None:
    """Delete oldest backup files, retaining only the `keep` most recent."""
    backups = sorted(dest_dir.glob("dashboard_*.db"), key=lambda p: p.stat().st_mtime)
    to_delete = backups[: max(0, len(backups) - keep)]
    for f in to_delete:
        f.unlink()
        print(f"  Deleted old backup: {f.name}")


def main() -> int:
    args = parse_args()
    source = Path(args.source)
    dest_dir = Path(args.dest)

    if not source.exists():
        print(f"ERROR: Source database not found: {source}", file=sys.stderr)
        return 1

    try:
        backup_file = backup(source, dest_dir)
        size_kb = backup_file.stat().st_size / 1024
        print(f"Backup created: {backup_file}  ({size_kb:.1f} KB)")
        prune(dest_dir, args.keep)
        return 0
    except Exception as exc:
        print(f"ERROR: Backup failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
