"""
User Profile Analyzer — Phase 2 画像计算引擎

读 dashboard.db 的 chat_messages 和 ai_thoughts 表，
写回 user_profiles 表。被 APScheduler 定时触发（每 5 分钟）。

分级实现策略
  Phase 2 (now)   – 统计数据 + 简单规则推断标签
  Phase 3+        – 接入 LLM 做语义分类、满意度评估

调用方式
  from app.dashboard.analyzer.user_profile_analyzer import UserProfileAnalyzer
  analyzer = UserProfileAnalyzer(db_path)
  analyzer.update_all_profiles()           # 更新所有活跃用户
  analyzer.update_profile(jid)             # 更新单个用户
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from app.dashboard.utils.db_init import get_db_connection

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

_TREND_7D_DAYS = 7
_TREND_30D_DAYS = 30

# VIP: ≥20 interactions in last 30 days
_VIP_THRESHOLD = 20
# new: first seen within last 7 days
_NEW_USER_DAYS = 7
# at_risk: no interaction for 14+ days despite past activity
_AT_RISK_INACTIVE_DAYS = 14
_AT_RISK_MIN_PAST = 5        # must have had at least 5 messages to be "at risk"

# Response quality bands
_HIGH_QUALITY_THRESHOLD = 0.7
_LOW_QUALITY_THRESHOLD = 0.3

# Tone → communication style mapping
_TONE_TO_STYLE: Dict[str, str] = {
    "detailed":   "detailed",
    "verbose":    "detailed",
    "concise":    "concise",
    "brief":      "concise",
    "impatient":  "impatient",
    "urgent":     "impatient",
    "patient":    "patient",
    "friendly":   "patient",
}


# ─────────────────────────────────────────────────────────────────────────────
# Analyzer
# ─────────────────────────────────────────────────────────────────────────────

class UserProfileAnalyzer:
    """
    Computes and persists user portrait data from raw chat + AI thought records.
    """

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    # ─────────────────────────────────────────── public interface ────────────

    def update_all_profiles(self) -> int:
        """
        Update profiles for every JID that has new activity since their last
        profile update.  Returns the number of profiles updated.
        """
        jids = self._get_active_jids()
        updated = 0
        for jid in jids:
            try:
                self.update_profile(jid)
                updated += 1
            except Exception:
                logger.exception(f"Failed to update profile for {jid}")
        logger.info(f"UserProfileAnalyzer: updated {updated}/{len(jids)} profiles")
        return updated

    def update_profile(self, jid: str) -> None:
        """Compute and upsert the portrait for a single JID."""
        t0 = time.monotonic()

        stats = self._compute_stats(jid)
        if stats["total_interactions"] == 0:
            return  # nothing to persist for a JID with no messages

        category = self._classify_user(stats)
        comm_style = self._infer_communication_style(jid, stats)
        topic_prefs = self._compute_topic_preferences(jid)
        satisfaction = self._compute_satisfaction_score(jid, stats)
        trend_7d = self._compute_trend(jid, _TREND_7D_DAYS)
        trend_30d = self._compute_trend(jid, _TREND_30D_DAYS)

        self._upsert_profile(
            jid=jid,
            stats=stats,
            category=category,
            comm_style=comm_style,
            topic_prefs=topic_prefs,
            satisfaction=satisfaction,
            trend_7d=trend_7d,
            trend_30d=trend_30d,
        )

        elapsed = (time.monotonic() - t0) * 1000
        logger.debug(f"update_profile({jid}) took {elapsed:.1f}ms")

    # ─────────────────────────────────────────── private helpers ─────────────

    def _get_active_jids(self) -> List[str]:
        """Return JIDs that have messages but whose profile is stale or missing."""
        with get_db_connection(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT m.user_jid
                FROM chat_messages m
                LEFT JOIN user_profiles p ON m.user_jid = p.user_jid
                WHERE p.user_jid IS NULL
                   OR p.updated_at < datetime('now', '-5 minutes')
                """
            ).fetchall()
        return [r[0] for r in rows]

    def _compute_stats(self, jid: str) -> dict:
        """Aggregate basic message stats for a JID."""
        with get_db_connection(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT
                    COUNT(*)                                           AS total,
                    SUM(CASE WHEN direction='in'  THEN 1 ELSE 0 END)  AS incoming,
                    SUM(CASE WHEN direction='out' THEN 1 ELSE 0 END)  AS outgoing,
                    MIN(timestamp)                                     AS first_ts,
                    MAX(timestamp)                                     AS last_ts,
                    SUM(CASE WHEN timestamp >= strftime('%s','now','-30 days')
                             THEN 1 ELSE 0 END)                       AS last30
                FROM chat_messages
                WHERE user_jid = ?
                """,
                (jid,),
            ).fetchone()

        return {
            "total_interactions":  row["total"]    or 0,
            "incoming":            row["incoming"] or 0,
            "outgoing":            row["outgoing"] or 0,
            "first_ts":            row["first_ts"],
            "last_ts":             row["last_ts"],
            "interactions_last30": row["last30"]   or 0,
        }

    def _classify_user(self, stats: dict) -> str:
        """
        Rule-based user classification.

        Precedence: new > VIP > at_risk > regular
        """
        now = int(time.time())
        first_ts = stats["first_ts"] or now
        last_ts  = stats["last_ts"]  or now

        days_since_first = (now - first_ts) / 86400
        days_since_last  = (now - last_ts)  / 86400

        if days_since_first <= _NEW_USER_DAYS:
            return "new"

        if stats["interactions_last30"] >= _VIP_THRESHOLD:
            return "VIP"

        if (days_since_last >= _AT_RISK_INACTIVE_DAYS
                and stats["total_interactions"] >= _AT_RISK_MIN_PAST):
            return "at_risk"

        return "regular"

    def _infer_communication_style(self, jid: str, stats: dict) -> Optional[str]:
        """
        Infer style from average user message length and AI thought tone records.
        """
        with get_db_connection(self.db_path) as conn:
            # Average incoming message length
            length_row = conn.execute(
                """
                SELECT AVG(LENGTH(content)) AS avg_len
                FROM chat_messages
                WHERE user_jid = ? AND direction = 'in'
                """,
                (jid,),
            ).fetchone()

            # Most common tone in ai_thoughts for this user
            tone_row = conn.execute(
                """
                SELECT tone, COUNT(*) AS cnt
                FROM ai_thoughts
                WHERE user_jid = ? AND tone IS NOT NULL
                GROUP BY tone
                ORDER BY cnt DESC
                LIMIT 1
                """,
                (jid,),
            ).fetchone()

        avg_len = length_row["avg_len"] or 0
        tone    = tone_row["tone"] if tone_row else None

        if tone and tone in _TONE_TO_STYLE:
            return _TONE_TO_STYLE[tone]

        # Fall back to message-length heuristic
        if avg_len > 120:
            return "detailed"
        if avg_len < 20:
            return "concise"
        return "patient"

    def _compute_topic_preferences(self, jid: str) -> dict:
        """
        Build a topic → count dict from detected_keywords in ai_thoughts.
        """
        with get_db_connection(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT detected_keywords
                FROM ai_thoughts
                WHERE user_jid = ? AND detected_keywords IS NOT NULL
                ORDER BY created_at DESC
                LIMIT 200
                """,
                (jid,),
            ).fetchall()

        topic_counts: Dict[str, int] = {}
        for row in rows:
            try:
                keywords = json.loads(row["detected_keywords"])
                for kw in keywords:
                    kw = kw.strip().lower()
                    if kw:
                        topic_counts[kw] = topic_counts.get(kw, 0) + 1
            except (json.JSONDecodeError, TypeError):
                continue

        # Keep top-20 topics
        sorted_topics = sorted(topic_counts.items(), key=lambda x: -x[1])[:20]
        return dict(sorted_topics)

    def _compute_satisfaction_score(self, jid: str, stats: dict) -> Optional[float]:
        """
        Derive a 0-1 satisfaction score from avg response quality and
        conversation continuity (how often the user replies after AI responds).
        """
        with get_db_connection(self.db_path) as conn:
            quality_row = conn.execute(
                """
                SELECT AVG(response_quality_score) AS avg_quality
                FROM ai_thoughts
                WHERE user_jid = ? AND response_quality_score IS NOT NULL
                """,
                (jid,),
            ).fetchone()

        avg_quality = quality_row["avg_quality"] if quality_row else None
        if avg_quality is None:
            return None

        # Continuity bonus: if user sends > 1 message on average per session
        total = stats["total_interactions"]
        incoming = stats["incoming"]
        continuity_ratio = min(1.0, incoming / max(1, total - incoming + 1))

        # Weighted blend
        score = 0.7 * avg_quality + 0.3 * continuity_ratio
        return round(min(1.0, max(0.0, score)), 4)

    def _compute_trend(self, jid: str, days: int) -> dict:
        """
        Return {dates: [...], counts: [...]} for the last N days.
        """
        with get_db_connection(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT date(timestamp, 'unixepoch') AS day, COUNT(*) AS cnt
                FROM chat_messages
                WHERE user_jid = ?
                  AND timestamp >= strftime('%s', 'now', ? || ' days')
                GROUP BY day
                ORDER BY day ASC
                """,
                (jid, f"-{days}"),
            ).fetchall()

        # Fill in missing dates with zero
        today = datetime.now(timezone.utc).date()
        date_map: Dict[str, int] = {str(today - timedelta(days=i)): 0 for i in range(days)}
        for row in rows:
            if row["day"] in date_map:
                date_map[row["day"]] = row["cnt"]

        sorted_dates = sorted(date_map.keys())
        return {
            "dates":  sorted_dates,
            "counts": [date_map[d] for d in sorted_dates],
        }

    def _upsert_profile(
        self,
        jid: str,
        stats: dict,
        category: str,
        comm_style: Optional[str],
        topic_prefs: dict,
        satisfaction: Optional[float],
        trend_7d: dict,
        trend_30d: dict,
    ) -> None:
        first_seen = (
            datetime.fromtimestamp(stats["first_ts"], tz=timezone.utc).isoformat()
            if stats["first_ts"] else None
        )
        last_seen = (
            datetime.fromtimestamp(stats["last_ts"], tz=timezone.utc).isoformat()
            if stats["last_ts"] else None
        )

        with get_db_connection(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO user_profiles
                    (user_jid, total_interactions, first_seen, last_seen,
                     user_category, communication_style, topic_preferences,
                     satisfaction_score, trend_7d, trend_30d, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_jid) DO UPDATE SET
                    total_interactions  = excluded.total_interactions,
                    first_seen          = excluded.first_seen,
                    last_seen           = excluded.last_seen,
                    user_category       = excluded.user_category,
                    communication_style = excluded.communication_style,
                    topic_preferences   = excluded.topic_preferences,
                    satisfaction_score  = excluded.satisfaction_score,
                    trend_7d            = excluded.trend_7d,
                    trend_30d           = excluded.trend_30d,
                    updated_at          = CURRENT_TIMESTAMP
                """,
                (
                    jid,
                    stats["total_interactions"],
                    first_seen,
                    last_seen,
                    category,
                    comm_style,
                    json.dumps(topic_prefs, ensure_ascii=False),
                    satisfaction,
                    json.dumps(trend_7d, ensure_ascii=False),
                    json.dumps(trend_30d, ensure_ascii=False),
                ),
            )
            conn.commit()
