"""
SatisfactionPlugin
==================
A self-contained, plug-in/plug-out component that:

  - Tracks the last AI-reply time per JID
  - After a configurable silence period sends a 1-5 satisfaction question
  - Intercepts the user's rating reply, persists an EMA score to
    ``user_profiles.satisfaction_score``, and sends a thank-you message

Usage in the bot layer
----------------------
::

    # on login success
    self._satisfaction = SatisfactionPlugin.from_config(
        config        = ai_config.get('ai_satisfaction', {}),
        send_fn       = self._ai_send_response,
        db_path       = self._dashboard_db_path,
        logger        = self.logger,
        is_connected  = lambda: self.isConnected,
    )
    self._satisfaction.start(asyncio.get_event_loop())

    # on disconnect
    self._satisfaction.stop()

    # in onMessage — before AI processing
    if await self._satisfaction.intercept(jid, text):
        return

    # after AI response is sent
    self._satisfaction.record_ai_reply(jid)
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
import time
from typing import Awaitable, Callable


class SatisfactionPlugin:
    """Plug-in satisfaction survey.  Fully encapsulates all state and logic."""

    # ── Construction ────────────────────────────────────────────────────────

    def __init__(
        self,
        *,
        enabled: bool,
        timeout_minutes: int,
        question_text: str,
        thank_you_text: str,
        send_fn: Callable[[str, str], Awaitable[None]],
        db_path: str | None,
        logger: logging.Logger,
        is_connected: Callable[[], bool],
    ) -> None:
        self._enabled = enabled
        self._timeout_minutes = timeout_minutes
        self._question_text = question_text
        self._thank_you_text = thank_you_text
        self._send_fn = send_fn
        self._db_path = db_path
        self._logger = logger
        self._is_connected = is_connected

        # {jid: {last_ai_reply: float, asked: bool, waiting: bool}}
        self._state: dict[str, dict] = {}
        self._task: asyncio.Task | None = None

    @classmethod
    def from_config(
        cls,
        config: dict,
        send_fn: Callable[[str, str], Awaitable[None]],
        db_path: str | None,
        logger: logging.Logger,
        is_connected: Callable[[], bool],
    ) -> "SatisfactionPlugin":
        return cls(
            enabled          = bool(config.get("enabled", False)),
            timeout_minutes  = int(config.get("timeout_minutes", 30)),
            question_text    = config.get(
                "question_text",
                "请问这次回答对您有帮助吗？请回复 1-5 分（1=很差，5=非常好）",
            ),
            thank_you_text   = config.get("thank_you_text", "感谢您的反馈！"),
            send_fn          = send_fn,
            db_path          = db_path,
            logger           = logger,
            is_connected     = is_connected,
        )

    # ── Public API ───────────────────────────────────────────────────────────

    @property
    def enabled(self) -> bool:
        return self._enabled

    def enable(self) -> None:
        """Enable the plugin at runtime."""
        self._enabled = True
        self._logger.info("SatisfactionPlugin enabled")

    def disable(self) -> None:
        """Disable the plugin at runtime (does not stop the timer task)."""
        self._enabled = False
        self._logger.info("SatisfactionPlugin disabled")

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        """Create the background timer task on *loop*. No-op if already running."""
        if self._task is None or self._task.done():
            self._task = loop.create_task(self._timer_task())
            self._logger.info(f"SatisfactionPlugin timer task started (enabled={self._enabled}, timeout={self._timeout_minutes}m)")

    def stop(self) -> None:
        """Cancel the background timer task."""
        if self._task and not self._task.done():
            self._task.cancel()
            self._task = None
            self._logger.debug("SatisfactionPlugin timer task stopped")

    def record_ai_reply(self, jid: str) -> None:
        """Call this every time the AI sends a reply to *jid*."""
        state = self._state.setdefault(jid, {})
        state["last_ai_reply"] = time.time()
        state["asked"] = False
        state["waiting"] = False
        self._logger.info(f"SatisfactionPlugin: AI reply recorded for {jid}, survey in {self._timeout_minutes}m")

    async def intercept(self, jid: str, text: str) -> bool:
        """
        Check whether *text* is a satisfaction rating we are waiting for.

        Returns ``True`` and handles the reply if it is — caller should
        ``return`` immediately and skip normal AI processing.
        """
        if not self._enabled:
            return False
        if not self._is_satisfaction_reply(jid, text):
            return False
        await self._handle_reply(jid, text)
        return True

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _is_satisfaction_reply(self, jid: str, text: str) -> bool:
        state = self._state.get(jid)
        if not state or not state.get("waiting"):
            return False
        return text.strip() in {"1", "2", "3", "4", "5"}

    async def _handle_reply(self, jid: str, score_str: str) -> None:
        score = int(score_str.strip())
        self._write_score(jid, score)
        state = self._state.get(jid, {})
        state["waiting"] = False
        state["asked"] = False
        state["last_ai_reply"] = 0
        try:
            await self._send_fn(jid, self._thank_you_text)
        except Exception as exc:
            self._logger.warning(f"SatisfactionPlugin: failed to send thank-you to {jid}: {exc}")
        self._logger.info(f"SatisfactionPlugin: score {score}/5 recorded for {jid}")

    async def _send_question(self, jid: str) -> None:
        await self._send_fn(jid, self._question_text)

    async def _timer_task(self) -> None:
        """Background loop: every 30 s check for timed-out conversations."""
        try:
            while True:
                await asyncio.sleep(30)
                if not self._enabled or not self._is_connected():
                    continue
                timeout_secs = self._timeout_minutes * 60
                now = time.time()
                for jid, state in list(self._state.items()):
                    if state.get("waiting") or state.get("asked"):
                        continue
                    last_reply = state.get("last_ai_reply", 0)
                    if last_reply > 0 and now - last_reply > timeout_secs:
                        try:
                            await self._send_question(jid)
                            state["asked"] = True
                            state["waiting"] = True
                            self._logger.info(f"SatisfactionPlugin: question sent to {jid}")
                        except Exception as exc:
                            self._logger.warning(
                                f"SatisfactionPlugin: failed to send question to {jid}: {exc}"
                            )
        except asyncio.CancelledError:
            self._logger.debug("SatisfactionPlugin timer task cancelled")

    def _write_score(self, jid: str, score: int) -> None:
        """Persist score using exponential moving average (EMA 0.7/0.3)."""
        if not self._db_path:
            return
        normalized = round(score / 5.0, 4)
        try:
            conn = sqlite3.connect(self._db_path, timeout=5)
            try:
                conn.execute("PRAGMA journal_mode=WAL")
                row = conn.execute(
                    "SELECT satisfaction_score FROM user_profiles WHERE user_jid = ?",
                    (jid,),
                ).fetchone()
                new_score = (
                    round(0.7 * row[0] + 0.3 * normalized, 4)
                    if (row and row[0] is not None)
                    else normalized
                )
                conn.execute(
                    """
                    INSERT INTO user_profiles
                        (user_jid, satisfaction_score, total_interactions,
                         first_seen, last_seen, updated_at)
                    VALUES (?, ?, 0,
                            CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ON CONFLICT(user_jid) DO UPDATE SET
                        satisfaction_score = excluded.satisfaction_score,
                        updated_at         = CURRENT_TIMESTAMP
                    """,
                    (jid, new_score),
                )
                conn.commit()
                self._logger.info(
                    f"SatisfactionPlugin: score {new_score:.4f} written for {jid}"
                )
            finally:
                conn.close()
        except Exception as exc:
            self._logger.warning(
                f"SatisfactionPlugin: failed to write score for {jid}: {exc}"
            )
