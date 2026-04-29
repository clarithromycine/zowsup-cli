"""
StrategyManager — Phase 3 strategy engine.

Responsibilities:
  - CRUD for strategy_applications table (personal + global)
  - Strategy version control (monotonically increasing version per scope)
  - Rollback to previous version
  - Conflict detection between personal and global strategies
  - Build system-prompt injection text for AIService

Priority rule: personal strategy overrides global (field-by-field merge).

Supported strategy config fields:
  response_style  : "formal" | "casual" | "concise" | "detailed"
  tone            : "polite" | "friendly" | "professional" | "empathetic" | "neutral"
  language        : "auto" | "zh" | "en" | "mixed"
  custom_instructions : free-text string appended verbatim to the system prompt

Storage: data/dashboard.db, table strategy_applications
"""

import json
import logging
import sqlite3
from contextlib import contextmanager
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Validation constants
# ---------------------------------------------------------------------------

VALID_RESPONSE_STYLES: frozenset = frozenset({"formal", "casual", "concise", "detailed"})
VALID_TONES: frozenset = frozenset({"polite", "friendly", "professional", "empathetic", "neutral"})
VALID_LANGUAGES: frozenset = frozenset({"auto", "zh", "en", "mixed"})

# Pairs (personal_val, global_val) that are considered conflicts
_CONFLICT_PAIRS: Dict[str, frozenset] = {
    "response_style": frozenset({
        ("formal", "casual"), ("casual", "formal"),
        ("concise", "detailed"), ("detailed", "concise"),
    }),
    "tone": frozenset({
        ("friendly", "professional"), ("professional", "friendly"),
    }),
    "language": frozenset({
        ("zh", "en"), ("en", "zh"),
    }),
}

# Human-readable descriptions for each strategy field value
_STYLE_DESCRIPTIONS = {
    "formal": "Use formal, professional language",
    "casual": "Use casual, conversational language",
    "concise": "Keep responses brief and to the point",
    "detailed": "Provide thorough, detailed explanations",
}
_TONE_DESCRIPTIONS = {
    "polite": "Maintain a polite and respectful tone",
    "friendly": "Be warm and friendly in your responses",
    "professional": "Keep a professional and objective tone",
    "empathetic": "Show empathy and understanding",
    "neutral": "Use a neutral, balanced tone",
}
_LANG_DESCRIPTIONS = {
    "zh": "Respond in Chinese (中文)",
    "en": "Respond in English",
    "mixed": "You may mix Chinese and English naturally",
}


class StrategyManager:
    """
    Thread-safe (open-close-per-operation) interface to the strategy tables.

    Designed to be instantiated per-request in Flask and also held as an
    attribute on AIService (read-only, with optional TTL caching).
    """

    def __init__(self, db_path: str):
        self.db_path = db_path

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
        finally:
            conn.close()

    def _parse_config(self, row) -> dict:
        """Safely parse config_json from a DB row."""
        try:
            return json.loads(row["config_json"])
        except Exception:
            return {}

    # ------------------------------------------------------------------
    # 4.1  Core strategy read
    # ------------------------------------------------------------------

    def get_active_strategy(self, user_jid: str = None) -> Dict:
        """
        Return merged strategy dict: personal (if any) overrides global.
        Returns {} if no strategy is configured.
        """
        with self._conn() as conn:
            global_row = conn.execute(
                "SELECT config_json FROM strategy_applications "
                "WHERE user_jid IS NULL AND strategy_type='global' AND is_active=1 "
                "ORDER BY id DESC LIMIT 1"
            ).fetchone()

            personal_row = None
            if user_jid:
                personal_row = conn.execute(
                    "SELECT config_json FROM strategy_applications "
                    "WHERE user_jid=? AND strategy_type='personal' AND is_active=1 "
                    "ORDER BY id DESC LIMIT 1",
                    (user_jid,),
                ).fetchone()

        merged: Dict = {}
        if global_row:
            merged.update(self._parse_config(global_row))
        if personal_row:
            merged.update(self._parse_config(personal_row))
        return merged

    def get_raw_strategies(self, user_jid: str = None) -> Dict:
        """
        Return {'global': {...}|None, 'personal': {...}|None} for transparency.
        Used by the GET /api/strategy endpoint.
        """
        with self._conn() as conn:
            global_row = conn.execute(
                "SELECT config_json FROM strategy_applications "
                "WHERE user_jid IS NULL AND strategy_type='global' AND is_active=1 "
                "ORDER BY id DESC LIMIT 1"
            ).fetchone()

            personal_row = None
            if user_jid:
                personal_row = conn.execute(
                    "SELECT config_json FROM strategy_applications "
                    "WHERE user_jid=? AND strategy_type='personal' AND is_active=1 "
                    "ORDER BY id DESC LIMIT 1",
                    (user_jid,),
                ).fetchone()

        return {
            "global": self._parse_config(global_row) if global_row else None,
            "personal": self._parse_config(personal_row) if personal_row else None,
        }

    # ------------------------------------------------------------------
    # 4.2 / 4.3  Apply strategy
    # ------------------------------------------------------------------

    def apply_strategy(self, user_jid: str, config: dict, note: str = None) -> int:
        """
        Deactivate all previous personal strategies for this JID, insert a new
        one.  Returns the new strategy row ID.
        """
        config_json = json.dumps(config, ensure_ascii=False)
        with self._conn() as conn:
            row = conn.execute(
                "SELECT MAX(version) AS v FROM strategy_applications "
                "WHERE user_jid=? AND strategy_type='personal'",
                (user_jid,),
            ).fetchone()
            version = (row["v"] or 0) + 1

            conn.execute(
                "UPDATE strategy_applications SET is_active=0 "
                "WHERE user_jid=? AND strategy_type='personal' AND is_active=1",
                (user_jid,),
            )
            cursor = conn.execute(
                "INSERT INTO strategy_applications "
                "  (user_jid, strategy_type, config_json, version, is_active, note) "
                "VALUES (?, 'personal', ?, ?, 1, ?)",
                (user_jid, config_json, version, note),
            )
            new_id = cursor.lastrowid
            conn.commit()

        logger.info("Personal strategy applied for %s: v%d id=%d", user_jid, version, new_id)

        # Record any newly detected conflicts (fire-and-forget)
        conflicts = self.detect_conflicts(user_jid)
        if conflicts:
            self._record_conflicts(user_jid, conflicts)

        return new_id

    def apply_global_strategy(self, config: dict, note: str = None) -> int:
        """
        Deactivate previous global strategy, insert new one.
        Returns the new strategy row ID.
        """
        config_json = json.dumps(config, ensure_ascii=False)
        with self._conn() as conn:
            row = conn.execute(
                "SELECT MAX(version) AS v FROM strategy_applications "
                "WHERE user_jid IS NULL AND strategy_type='global'",
            ).fetchone()
            version = (row["v"] or 0) + 1

            conn.execute(
                "UPDATE strategy_applications SET is_active=0 "
                "WHERE user_jid IS NULL AND strategy_type='global' AND is_active=1",
            )
            cursor = conn.execute(
                "INSERT INTO strategy_applications "
                "  (user_jid, strategy_type, config_json, version, is_active, note) "
                "VALUES (NULL, 'global', ?, ?, 1, ?)",
                (config_json, version, note),
            )
            new_id = cursor.lastrowid
            conn.commit()

        logger.info("Global strategy applied: v%d id=%d", version, new_id)
        return new_id

    # ------------------------------------------------------------------
    # 4.4  Version control — rollback
    # ------------------------------------------------------------------

    def rollback_strategy(self, user_jid: str = None) -> bool:
        """
        Deactivate the currently active version, reactivate the previous one.
        If user_jid is None, operates on the global strategy.
        Returns True if there was an active strategy to roll back from.
        When no previous version exists, the active strategy is simply deactivated
        (rolls back to "no strategy" state).
        """
        with self._conn() as conn:
            if user_jid:
                current = conn.execute(
                    "SELECT id, version FROM strategy_applications "
                    "WHERE user_jid=? AND strategy_type='personal' AND is_active=1 "
                    "ORDER BY version DESC LIMIT 1",
                    (user_jid,),
                ).fetchone()
            else:
                current = conn.execute(
                    "SELECT id, version FROM strategy_applications "
                    "WHERE user_jid IS NULL AND strategy_type='global' AND is_active=1 "
                    "ORDER BY version DESC LIMIT 1",
                ).fetchone()

            if not current:
                return False  # nothing active to roll back from

            # Find the previous version (highest version strictly below current)
            if user_jid:
                prev = conn.execute(
                    "SELECT id, version FROM strategy_applications "
                    "WHERE user_jid=? AND strategy_type='personal' AND version < ? "
                    "ORDER BY version DESC LIMIT 1",
                    (user_jid, current["version"]),
                ).fetchone()
            else:
                prev = conn.execute(
                    "SELECT id, version FROM strategy_applications "
                    "WHERE user_jid IS NULL AND strategy_type='global' AND version < ? "
                    "ORDER BY version DESC LIMIT 1",
                    (current["version"],),
                ).fetchone()

            conn.execute(
                "UPDATE strategy_applications SET is_active=0 WHERE id=?",
                (current["id"],),
            )
            if prev:
                conn.execute(
                    "UPDATE strategy_applications SET is_active=1 WHERE id=?",
                    (prev["id"],),
                )
            conn.commit()

        logger.info(
            "Strategy rolled back for %s (from v%d to %s)",
            "global" if user_jid is None else user_jid,
            current["version"],
            f"v{prev['version']}" if prev else "none",
        )
        return True

    # ------------------------------------------------------------------
    # 4.5  Audit history
    # ------------------------------------------------------------------

    def get_history(self, user_jid: str = None, limit: int = 20) -> List[Dict]:
        """Return audit history of strategy applications (newest first)."""
        with self._conn() as conn:
            if user_jid:
                rows = conn.execute(
                    "SELECT id, user_jid, strategy_type, config_json, version, "
                    "       is_active, applied_at, note "
                    "FROM strategy_applications "
                    "WHERE user_jid=? "
                    "ORDER BY id DESC LIMIT ?",
                    (user_jid, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, user_jid, strategy_type, config_json, version, "
                    "       is_active, applied_at, note "
                    "FROM strategy_applications "
                    "WHERE user_jid IS NULL "
                    "ORDER BY id DESC LIMIT ?",
                    (limit,),
                ).fetchall()

        result = []
        for r in rows:
            d = dict(r)
            d["config"] = self._parse_config(r)
            del d["config_json"]
            result.append(d)
        return result

    # ------------------------------------------------------------------
    # 4.5b  Toggle / delete individual rows
    # ------------------------------------------------------------------

    def toggle_strategy(self, strategy_id: int) -> dict:
        """
        Toggle is_active for a single strategy row.
        When activating: deactivate any other active row of the same type/jid
        so there is at most one active row per scope.
        Returns {'id': ..., 'is_active': new_value}.
        Raises ValueError if strategy_id not found.
        """
        with self._conn() as conn:
            row = conn.execute(
                "SELECT id, user_jid, strategy_type, is_active "
                "FROM strategy_applications WHERE id=?",
                (strategy_id,),
            ).fetchone()
            if not row:
                raise ValueError(f"Strategy id={strategy_id} not found")

            new_active = 0 if row["is_active"] else 1

            if new_active == 1:
                # Deactivate any currently active row of the same scope
                if row["user_jid"] is None:
                    conn.execute(
                        "UPDATE strategy_applications SET is_active=0 "
                        "WHERE user_jid IS NULL AND strategy_type=? AND is_active=1",
                        (row["strategy_type"],),
                    )
                else:
                    conn.execute(
                        "UPDATE strategy_applications SET is_active=0 "
                        "WHERE user_jid=? AND strategy_type=? AND is_active=1",
                        (row["user_jid"], row["strategy_type"]),
                    )

            conn.execute(
                "UPDATE strategy_applications SET is_active=? WHERE id=?",
                (new_active, strategy_id),
            )
            conn.commit()

        logger.info(
            "Strategy id=%d toggled to is_active=%d", strategy_id, new_active
        )
        return {"id": strategy_id, "is_active": new_active}

    def delete_strategy(self, strategy_id: int) -> bool:
        """
        Permanently delete a strategy row.
        Returns True if a row was deleted, False if not found.
        """
        with self._conn() as conn:
            cursor = conn.execute(
                "DELETE FROM strategy_applications WHERE id=?",
                (strategy_id,),
            )
            conn.commit()
        deleted = cursor.rowcount > 0
        if deleted:
            logger.info("Strategy id=%d deleted", strategy_id)
        return deleted

    # ------------------------------------------------------------------
    # 4.6 / 4.7  Conflict detection
    # ------------------------------------------------------------------

    def detect_conflicts(self, user_jid: str) -> List[Dict]:
        """
        Compare active personal vs active global strategy.
        Returns list of conflict dicts:
          {field, personal_value, global_value, description}
        Returns [] if no personal or global strategy is configured.
        """
        raw = self.get_raw_strategies(user_jid)
        global_cfg = raw["global"] or {}
        personal_cfg = raw["personal"] or {}

        if not global_cfg or not personal_cfg:
            return []

        conflicts = []
        for field, conflict_pairs in _CONFLICT_PAIRS.items():
            g_val = global_cfg.get(field)
            p_val = personal_cfg.get(field)
            if g_val and p_val and (p_val, g_val) in conflict_pairs:
                conflicts.append({
                    "field": field,
                    "personal_value": p_val,
                    "global_value": g_val,
                    "description": (
                        f"Personal '{field}={p_val}' conflicts "
                        f"with global '{field}={g_val}'"
                    ),
                })

        return conflicts

    def get_stored_conflicts(
        self, user_jid: str = None, resolved: bool = False
    ) -> List[Dict]:
        """Return stored conflict records from the strategy_conflicts table."""
        with self._conn() as conn:
            if user_jid:
                rows = conn.execute(
                    "SELECT id, user_jid, conflict_type, description, resolved, created_at "
                    "FROM strategy_conflicts "
                    "WHERE user_jid=? AND resolved=? "
                    "ORDER BY created_at DESC",
                    (user_jid, 1 if resolved else 0),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, user_jid, conflict_type, description, resolved, created_at "
                    "FROM strategy_conflicts "
                    "WHERE resolved=? "
                    "ORDER BY created_at DESC",
                    (1 if resolved else 0,),
                ).fetchall()

        return [dict(r) for r in rows]

    def _record_conflicts(self, user_jid: str, conflicts: List[Dict]) -> None:
        """Persist detected conflicts to strategy_conflicts table."""
        try:
            with self._conn() as conn:
                for c in conflicts:
                    conn.execute(
                        "INSERT INTO strategy_conflicts (user_jid, conflict_type, description) "
                        "VALUES (?, ?, ?)",
                        (user_jid, c["field"], c["description"]),
                    )
                conn.commit()
        except Exception as exc:
            logger.warning("Failed to record conflicts: %s", exc)

    # ------------------------------------------------------------------
    # 4.11  Build system-prompt injection text
    # ------------------------------------------------------------------

    def build_system_prompt_extra(self, user_jid: str = None) -> str:
        """
        Return strategy instructions as a string ready to be appended to the
        AI system prompt.  Returns "" if no strategy is configured.
        """
        strategy = self.get_active_strategy(user_jid)
        if not strategy:
            return ""

        parts = ["\n\n[Communication Strategy — follow these rules strictly]"]

        style = strategy.get("response_style")
        tone = strategy.get("tone")
        language = strategy.get("language")
        custom = (strategy.get("custom_instructions") or "").strip()

        if style and style in _STYLE_DESCRIPTIONS:
            parts.append(f"- {_STYLE_DESCRIPTIONS[style]}")
        if tone and tone in _TONE_DESCRIPTIONS:
            parts.append(f"- {_TONE_DESCRIPTIONS[tone]}")
        if language and language != "auto" and language in _LANG_DESCRIPTIONS:
            parts.append(f"- {_LANG_DESCRIPTIONS[language]}")
        if custom:
            parts.append(f"- {custom}")

        if len(parts) == 1:
            # Only the header — nothing useful to inject
            return ""

        return "\n".join(parts)
