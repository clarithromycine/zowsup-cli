#!/usr/bin/env python
"""
scripts/restore_db.py
─────────────────────
Restore dashboard.db from a backup file created by backup_db.py.

IMPORTANT: Stop the dashboard server before restoring!
The restore copies the backup over the live database file.

Usage
-----
  python scripts/restore_db.py data/backups/dashboard_20260428_120000.db
  python scripts/restore_db.py --latest             # restore most recent backup
  python scripts/restore_db.py --list               # list available backups

Exit codes
----------
  0  success
  1  bad arguments / file not found
  2  restore failed
"""

import argparse
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = PROJECT_ROOT / "data" / "dashboard.db"
DEFAULT_BACKUP_DIR = PROJECT_ROOT / "data" / "backups"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Restore dashboard.db from backup")
    p.add_argument(
        "backup_file",
        nargs="?",
        help="Path to the backup file to restore",
    )
    p.add_argument(
        "--latest",
        action="store_true",
        help="Restore the most recent backup in the backup directory",
    )
    p.add_argument(
        "--list",
        action="store_true",
        help="List available backup files and exit",
    )
    p.add_argument(
        "--dest",
        default=str(DEFAULT_DB),
        help=f"Destination path for restored database (default: {DEFAULT_DB})",
    )
    p.add_argument(
        "--backup-dir",
        default=str(DEFAULT_BACKUP_DIR),
        help=f"Directory to search for backups (default: {DEFAULT_BACKUP_DIR})",
    )
    return p.parse_args()


def list_backups(backup_dir: Path) -> list[Path]:
    backups = sorted(backup_dir.glob("dashboard_*.db"), key=lambda p: p.stat().st_mtime)
    return backups


def main() -> int:
    args = parse_args()
    backup_dir = Path(args.backup_dir)
    dest = Path(args.dest)

    # --list
    if args.list:
        backups = list_backups(backup_dir)
        if not backups:
            print(f"No backups found in {backup_dir}")
            return 0
        print(f"Available backups in {backup_dir}:")
        for b in reversed(backups):
            size_kb = b.stat().st_size / 1024
            print(f"  {b.name}  ({size_kb:.1f} KB)")
        return 0

    # Resolve backup file
    if args.latest:
        backups = list_backups(backup_dir)
        if not backups:
            print(f"ERROR: No backups found in {backup_dir}", file=sys.stderr)
            return 1
        source = backups[-1]
    elif args.backup_file:
        source = Path(args.backup_file)
    else:
        print("ERROR: Provide a backup file path or use --latest / --list", file=sys.stderr)
        return 1

    if not source.exists():
        print(f"ERROR: Backup file not found: {source}", file=sys.stderr)
        return 1

    # Safety: create a pre-restore snapshot of the current DB
    if dest.exists():
        pre_restore = dest.with_suffix(f".pre_restore_{dest.stat().st_mtime:.0f}.db")
        shutil.copy2(dest, pre_restore)
        print(f"Pre-restore snapshot saved: {pre_restore.name}")

    try:
        shutil.copy2(source, dest)
        size_kb = dest.stat().st_size / 1024
        print(f"Restored: {source.name} → {dest}  ({size_kb:.1f} KB)")
        print("Restart the dashboard server to use the restored database.")
        return 0
    except Exception as exc:
        print(f"ERROR: Restore failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
