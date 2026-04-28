"""
Data migration: import historical conversations from per-account db.db → dashboard.db

Source: ~/.zowsup/accounts/<phone_id>/db.db  →  table: ai_memory
         columns: id, user_jid, message_type, user_message, ai_response, created_at

Target: data/dashboard.db  →  table: chat_messages
         one row per message (in + out), with source_memory_id for dedup

Usage:
    python -m app.dashboard.utils.migrations --account-db /path/to/db.db
    python -m app.dashboard.utils.migrations   # auto-detects from config.conf
"""

import argparse
import logging
import sqlite3
import time
from pathlib import Path

from app.dashboard.config import CONFIG
from app.dashboard.utils.db_init import get_db_connection, init_db

logger = logging.getLogger(__name__)


def _find_account_db(account_path: str) -> Path | None:
    """
    Scan ACCOUNT_PATH for a db.db file.
    Returns the first one found (single-account deployment).
    """
    base = Path(account_path)
    if not base.exists():
        return None
    for candidate in sorted(base.rglob("db.db")):
        # skip tmp/ directories
        if "tmp" not in str(candidate):
            return candidate
    return None


def migrate_from_ai_memory(
    account_db_path: str,
    dashboard_db_path: str = CONFIG["DASHBOARD_DB_PATH"],
) -> dict:
    """
    Read ai_memory rows from account db and insert them as chat_messages rows.

    Each ai_memory row produces two chat_messages rows:
      - direction='in'  for user_message
      - direction='out' for ai_response

    Uses source_memory_id to avoid inserting duplicates on re-run.

    Returns:
        {"skipped": int, "imported": int, "errors": int}
    """
    stats = {"skipped": 0, "imported": 0, "errors": 0}

    # Ensure schema exists
    init_db(dashboard_db_path)

    try:
        src = sqlite3.connect(account_db_path)
        src.row_factory = sqlite3.Row
    except Exception as e:
        logger.error(f"Cannot open account db at {account_db_path}: {e}")
        stats["errors"] += 1
        return stats

    try:
        rows = src.execute(
            "SELECT id, user_jid, message_type, user_message, ai_response, created_at "
            "FROM ai_memory ORDER BY id ASC"
        ).fetchall()
    except sqlite3.OperationalError as e:
        logger.error(f"ai_memory table not found in {account_db_path}: {e}")
        src.close()
        return stats
    finally:
        src.close()

    with get_db_connection(dashboard_db_path) as dst:
        # Fetch already-migrated source IDs
        existing = {
            row[0]
            for row in dst.execute(
                "SELECT source_memory_id FROM chat_messages WHERE source_memory_id IS NOT NULL"
            ).fetchall()
        }

        pairs: list[tuple] = []
        for row in rows:
            mem_id = row["id"]
            if mem_id in existing:
                stats["skipped"] += 1
                continue

            user_jid = row["user_jid"]
            msg_type = row["message_type"] or "text"
            # Parse created_at to epoch; fall back to current time
            try:
                from datetime import datetime
                ts = int(datetime.fromisoformat(str(row["created_at"])).timestamp())
            except Exception:
                ts = int(time.time())

            # incoming message from user
            pairs.append((user_jid, "in", row["user_message"], msg_type, ts, mem_id))
            # outgoing AI response (same second, +1 to preserve order)
            pairs.append((user_jid, "out", row["ai_response"], "text", ts + 1, mem_id))

        if pairs:
            dst.executemany(
                "INSERT INTO chat_messages "
                "(user_jid, direction, content, message_type, timestamp, source_memory_id) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                pairs,
            )
            dst.commit()
            imported_pairs = len(pairs) // 2
            stats["imported"] += imported_pairs
            logger.info(f"Migrated {imported_pairs} conversation pairs from {account_db_path}")

    return stats


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Migrate ai_memory → dashboard.db chat_messages")
    parser.add_argument(
        "--account-db",
        default=None,
        help="Path to account db.db (auto-detected from config if omitted)",
    )
    parser.add_argument(
        "--dashboard-db",
        default=CONFIG["DASHBOARD_DB_PATH"],
        help=f"Path to dashboard.db (default: {CONFIG['DASHBOARD_DB_PATH']})",
    )
    args = parser.parse_args()

    account_db = args.account_db
    if account_db is None:
        found = _find_account_db(CONFIG["ACCOUNT_PATH"])
        if found is None:
            print(f"No db.db found under ACCOUNT_PATH={CONFIG['ACCOUNT_PATH']}")
            print("Pass --account-db /path/to/db.db explicitly.")
            raise SystemExit(1)
        account_db = str(found)
        print(f"Auto-detected account db: {account_db}")

    result = migrate_from_ai_memory(account_db, args.dashboard_db)
    print(f"Migration complete: imported={result['imported']}  skipped={result['skipped']}  errors={result['errors']}")
