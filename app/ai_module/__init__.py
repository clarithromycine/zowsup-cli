"""
AI Module for ZowBot - Auto-reply with LLM backends.

Supports:
- Conversation memory (SQLite per-account)
- Multiple LLM backends (GLM, QWEN, OpenAI)
- Message filtering (P2P only, self-device exclusion)
- Retry management (5 min delay, 1 retry)
"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
from app.ai_module.ai_service import AIService
from app.ai_module.memory.memory import ConversationMemory
from app.ai_module.filter.message_filter import MessageFilter
from app.ai_module.backend.base import AIBackendBase
from app.ai_module.backend.glm_backend import GLMBackend

__all__ = [
    'AIService',
    'ConversationMemory',
    'MessageFilter',
    'AIBackendBase',
    'GLMBackend',
]
