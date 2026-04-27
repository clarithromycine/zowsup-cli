"""
AI Backend abstraction and implementations.

Supported backends:
- GLM (Phase 1)
- QWEN (Phase 2)
- OpenAI (Phase 2)
"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
from app.ai_module.backend.base import AIBackendBase, AIBackendException
from app.ai_module.backend.glm_backend import GLMBackend

__all__ = [
    'AIBackendBase',
    'AIBackendException',
    'GLMBackend',
]
