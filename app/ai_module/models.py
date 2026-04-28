"""
AI result data models for structured thought recording.

These models are the return types of AIService.process_message() in Phase 2.
They carry both the text response (backward-compatible) and the structured
AI reasoning record that gets persisted to dashboard.db.

Backward compatibility contract:
  - AIResult.__bool__()  →  bool(result.response)
  - AIResult.__str__()   →  result.response
  Callers that only need the string can keep using:
      if ai_response:
          send(str(ai_response))   # or ai_response.response
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class AIThought:
    """
    Structured record of one AI reasoning step.

    Populated by AIService._build_thought() after each successful backend call.
    A Phase 2 implementation fills as many fields as possible from the response
    and simple heuristics; Phase 3+ may enrich this with a second LLM call.
    """

    # ── Intent & confidence ───────────────────────────────────────────────
    intent: Optional[str] = None
    """High-level intent inferred from the user message (e.g. 'question', 'complaint')."""

    confidence: Optional[float] = None
    """0.0 – 1.0 confidence that the intent label is correct."""

    # ── Keyword extraction ────────────────────────────────────────────────
    detected_keywords: List[str] = field(default_factory=list)
    """Important words/phrases extracted from the user message."""

    # ── Strategy ──────────────────────────────────────────────────────────
    strategy_selected: Optional[str] = None
    """Name of the reply strategy applied (e.g. 'default', 'empathy', 'formal')."""

    strategy_reasoning: Optional[str] = None
    """One-sentence explanation of why this strategy was chosen."""

    # ── Tone & quality ────────────────────────────────────────────────────
    tone: Optional[str] = None
    """Detected tone of the AI response (e.g. 'friendly', 'formal', 'empathetic')."""

    response_quality_score: Optional[float] = None
    """0.0 – 1.0 quality estimate (length adequacy × coherence heuristic)."""

    # ── Raw LLM output ────────────────────────────────────────────────────
    raw_thought: Optional[str] = None
    """The full text the LLM returned (same as AIResult.response unless a
    chain-of-thought prefix is stripped in future phases)."""

    def to_db_row(self) -> dict:
        """Return a dict ready to be inserted into the ai_thoughts table."""
        return {
            "intent": self.intent,
            "confidence": self.confidence,
            "detected_keywords": json.dumps(self.detected_keywords, ensure_ascii=False),
            "strategy_selected": self.strategy_selected,
            "strategy_reasoning": self.strategy_reasoning,
            "tone": self.tone,
            "response_quality_score": self.response_quality_score,
            "raw_thought": self.raw_thought,
        }


@dataclass
class AIResult:
    """
    Return value of AIService.process_message().

    Replaces the bare ``Optional[str]`` return type while keeping
    full backward compatibility with existing callers.
    """

    response: str
    """The AI-generated reply text to send to the user."""

    thought: AIThought = field(default_factory=AIThought)
    """Structured reasoning record — persisted to dashboard.db."""

    # ── Backward-compatibility dunder methods ─────────────────────────────

    def __bool__(self) -> bool:
        """Truthy iff response is non-empty (matches old ``if ai_response:`` pattern)."""
        return bool(self.response and self.response.strip())

    def __str__(self) -> str:
        """Allows ``str(ai_result)`` to return the response text directly."""
        return self.response

    def __len__(self) -> int:
        return len(self.response)
