"""
Abstract base class for AI backends.

All backends must implement this interface to be compatible with AIService.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional


class AIBackendException(Exception):
    """Exception raised by AI backends."""
    pass


class AIBackendBase(ABC):
    """Abstract base for LLM backends."""
    
    @abstractmethod
    async def send_message(self, user_message: str,
                          memory_context: List[Dict],
                          system_extra: str = "") -> str:
        """
        Send message to LLM with context.
        
        Args:
            user_message: User's question/message
            memory_context: List of recent Q&A pairs from past 3 days
                - Each dict has: user_message, ai_response, created_at
            system_extra: Optional extra instructions appended to the system
                          prompt (injected by the Phase 3 strategy engine).
        
        Returns:
            str: AI's response text
        
        Raises:
            AIBackendException: On API errors, timeout, etc.
        """
        pass
    
    @abstractmethod
    def is_configured(self) -> bool:
        """
        Check if backend has valid configuration.
        
        Returns:
            bool: True if API key/token is set and valid
        """
        pass
    
    @abstractmethod
    def get_status(self) -> Dict:
        """
        Get backend status information.
        
        Returns:
            dict with keys: 'configured', 'model', 'auth_mode', 'last_used'
        """
        pass
