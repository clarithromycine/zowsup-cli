#!/usr/bin/env python
"""
scripts/check_production.py
────────────────────────────
Pre-flight checks for a production dashboard deployment.

Run this script BEFORE starting the server in production.
It validates configuration, database, filesystem permissions,
and required environment variables.

Usage
-----
  python scripts/check_production.py
  python scripts/check_production.py --fix   # attempt to fix auto-fixable issues

Exit codes
----------
  0  all checks passed (or only warnings)
  1  one or more CRITICAL checks failed
"""

import argparse
import os
import socket
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ── colour helpers ──────────────────────────────────────────────────────────
_GREEN  = "\033[32m"
_YELLOW = "\033[33m"
_RED    = "\033[31m"
_RESET  = "\033[0m"

def _ok(msg):   print(f"  {_GREEN}✔{_RESET}  {msg}")
def _warn(msg): print(f"  {_YELLOW}⚠{_RESET}  {msg}")
def _fail(msg): print(f"  {_RED}✘{_RESET}  {msg}")


def check_env_token() -> bool:
    token = os.environ.get("DASHBOARD_API_TOKEN", "")
    if not token:
        _fail("DASHBOARD_API_TOKEN is not set — API has no authentication!")
        return False
    if len(token) < 32:
        _warn("DASHBOARD_API_TOKEN is shorter than 32 characters — consider using a longer token")
    else:
        _ok(f"DASHBOARD_API_TOKEN set ({len(token)} chars)")
    return True


def check_debug_mode() -> bool:
    if os.environ.get("DASHBOARD_DEBUG", "false").lower() == "true":
        _fail("DASHBOARD_DEBUG=true — debug mode must be disabled in production!")
        return False
    _ok("DASHBOARD_DEBUG is not enabled")
    return True


def check_dotenv() -> None:
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        _ok(".env file found — environment loaded")
    else:
        _warn(".env file not found — using system environment variables")


def check_db_path(fix: bool) -> bool:
    db_path = Path(os.environ.get("DASHBOARD_DB_PATH",
                                   str(PROJECT_ROOT / "data" / "dashboard.db")))
    data_dir = db_path.parent

    if not data_dir.exists():
        if fix:
            data_dir.mkdir(parents=True, exist_ok=True)
            _ok(f"Created data directory: {data_dir}")
        else:
            _fail(f"Data directory does not exist: {data_dir}  (run with --fix)")
            return False

    if db_path.exists():
        # Verify it's a valid SQLite file
        try:
            conn = sqlite3.connect(str(db_path))
            conn.execute("SELECT count(*) FROM sqlite_master")
            conn.close()
            size_kb = db_path.stat().st_size / 1024
            _ok(f"Database exists and is valid: {db_path} ({size_kb:.1f} KB)")
        except Exception as e:
            _fail(f"Database file is corrupt or unreadable: {e}")
            return False
    else:
        _warn(f"Database does not exist yet: {db_path}  (will be created on first start)")

    return True


def check_logs_dir(fix: bool) -> bool:
    log_dir = Path(os.environ.get("LOG_DIR", str(PROJECT_ROOT / "logs")))
    if not log_dir.exists():
        if fix:
            log_dir.mkdir(parents=True, exist_ok=True)
            _ok(f"Created logs directory: {log_dir}")
        else:
            _warn(f"Logs directory does not exist: {log_dir}  (will be created automatically)")
    else:
        # Check write permission
        test_file = log_dir / ".write_test"
        try:
            test_file.touch()
            test_file.unlink()
            _ok(f"Logs directory is writable: {log_dir}")
        except OSError:
            _fail(f"Logs directory is not writable: {log_dir}")
            return False
    return True


def check_port() -> bool:
    port = int(os.environ.get("DASHBOARD_PORT", "5000"))
    host = os.environ.get("DASHBOARD_HOST", "0.0.0.0")
    bind_host = "127.0.0.1" if host == "0.0.0.0" else host
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.5)
    try:
        s.bind((bind_host, port))
        s.close()
        _ok(f"Port {port} is available")
        return True
    except OSError:
        _warn(f"Port {port} is already in use — another process may be running")
        return True  # warning, not fatal
    finally:
        try:
            s.close()
        except Exception:
            pass


def check_requirements() -> bool:
    required = ["flask", "flask_cors", "flask_socketio", "flask_limiter", "dotenv"]
    missing = []
    for pkg in required:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        _fail(f"Missing Python packages: {', '.join(missing)} — run: pip install -r requirements.txt")
        return False
    _ok("All required Python packages are installed")
    return True


def check_python_version() -> bool:
    if sys.version_info < (3, 11):
        _fail(f"Python 3.11+ required, got {sys.version_info.major}.{sys.version_info.minor}")
        return False
    _ok(f"Python version: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    return True


def check_backup_dir() -> None:
    backup_dir = PROJECT_ROOT / "data" / "backups"
    if not backup_dir.exists():
        _warn(f"Backup directory missing: {backup_dir}  — run backup_db.py to create first backup")
    else:
        backups = list(backup_dir.glob("dashboard_*.db"))
        if backups:
            _ok(f"Found {len(backups)} backup(s) in {backup_dir}")
        else:
            _warn("Backup directory exists but no backups found — run backup_db.py")


def main() -> int:
    p = argparse.ArgumentParser(description="Production pre-flight checks")
    p.add_argument("--fix", action="store_true", help="Auto-fix common issues (create missing dirs)")
    args = p.parse_args()

    # Load .env if present
    try:
        from dotenv import load_dotenv
        env_file = PROJECT_ROOT / ".env"
        if env_file.exists():
            load_dotenv(env_file, override=False)
    except ImportError:
        pass

    print("\nDashboard Production Pre-flight Checks")
    print("=" * 42)

    failures = 0

    print("\n[Python environment]")
    if not check_python_version(): failures += 1
    if not check_requirements(): failures += 1

    print("\n[Configuration]")
    check_dotenv()
    if not check_env_token(): failures += 1
    if not check_debug_mode(): failures += 1

    print("\n[Database]")
    if not check_db_path(fix=args.fix): failures += 1
    check_backup_dir()

    print("\n[Filesystem]")
    check_logs_dir(fix=args.fix)

    print("\n[Network]")
    check_port()

    print()
    if failures == 0:
        print(f"{_GREEN}All critical checks passed. Ready for production.{_RESET}\n")
        return 0
    else:
        print(f"{_RED}{failures} critical check(s) failed. Fix issues before deploying.{_RESET}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
