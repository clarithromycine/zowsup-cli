"""
GLM backend implementation.

Supports:
- API Key authentication using official zhipuai SDK
- Multiple GLM models
- Async/await pattern
"""

import logging
import asyncio
import time
import warnings
import httpx
from typing import List, Dict, Optional
from datetime import datetime

from zhipuai import ZhipuAI

from app.ai_module.backend.base import AIBackendBase, AIBackendException

logger = logging.getLogger(__name__)

# Suppress JWT insecure key length warning for short API keys
warnings.filterwarnings('ignore', message='.*HMAC key is.*bytes long.*')


class GLMBackend(AIBackendBase):
    """GLM backend for LLM-based auto-replies."""
    
    # Official GLM API endpoint
    ENDPOINT = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    

    
    def __init__(self, api_key: str = None, model: str = "glm-4-plus", 
                 auth_mode: str = "apikey"):
        """
        Initialize GLM backend.
        
        Args:
            api_key: GLM API key (for API Key auth mode)
            model: GLM model name (default: glm-4-plus)
            auth_mode: 'apikey' 
        """
        self.api_key = api_key
        self.model = model 
        self.auth_mode = auth_mode        
        self.last_used = None
        
        logger.info(f"GLMBackend initialized: model={self.model}, "
                   f"auth_mode={self.auth_mode}")
    
    async def send_message(self, user_message: str,
                          memory_context: List[Dict],
                          system_extra: str = "") -> str:
        """
        Send message to GLM backend.

        Args:
            user_message: User's question
            memory_context: Past conversation history (3-day window)
            system_extra: Optional strategy instructions to append to system prompt

        Returns:
            str: AI response

        Raises:
            AIBackendException: On API errors
        """
        return await self._real_send_message(user_message, memory_context, system_extra)
    
    def _mock_send_message(self, user_message: str,
                          memory_context: List[Dict]) -> str:
        """
        Mock GLM API response for Phase 1 testing.
        
        Args:
            user_message: User's question
            memory_context: Historical Q&A pairs
        
        Returns:
            str: Mock response
        """
        # Build context string
        context_str = ""
        if memory_context:
            context_str = "过去对话:\n"
            for item in memory_context:  # pre-sliced by AIService (context_turns)
                context_str += f"用户: {item.get('user_message', '')}\n"
                context_str += f"我: {item.get('ai_response', '')}\n"
        
        # Log the interaction
        logger.debug(f"GLM Mock mode: Processing message from user")
        logger.debug(f"  Context items: {len(memory_context)}")
        logger.debug(f"  User message: {user_message[:100]}")
        
        # Record last used time
        self.last_used = datetime.now()
        
        # Return mock response
        response = f"[Mock GLM Response to: {user_message[:20]}...]"
        logger.debug(f"  Mock response: {response}")
        
        return response
    
    async def _real_send_message(self, user_message: str,
                               memory_context: List[Dict],
                               system_extra: str = "") -> str:
        """
        Real GLM API integration using official zhipuai SDK.
        
        Makes API call to GLM using the official SDK.
        
        Args:
            user_message: User's question
            memory_context: Historical Q&A pairs
        
        Returns:
            str: AI response text
        
        Raises:
            AIBackendException: On API errors
        """
        try:
            # Initialize official GLM client with increased timeout for thinking model
            # GLM models with thinking feature may take 10-30+ seconds
            client = ZhipuAI(
                api_key=self.api_key,
                timeout=httpx.Timeout(60.0)  # 60-second timeout for thinking models
            )
            
            # Build messages list with memory context
            messages = []
            
            # Add memory context to system context
            if memory_context:
                context_str = "以下是过去的对话记录:\n"
                for item in memory_context:  # pre-sliced by AIService (context_turns)
                    context_str += f"用户: {item.get('user_message', '')}\n"
                    context_str += f"助手: {item.get('ai_response', '')}\n"
                
                system_prompt = "你是一个有用且友好的WhatsApp助手,帮助用户回答问题。" + context_str
            else:
                system_prompt = "你是一个有用且友好的WhatsApp助手,帮助用户回答问题。"

            if system_extra:
                system_prompt += system_extra
            
            messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": user_message})
            
            logger.debug(f"Calling GLM API with model={self.model}, messages={len(messages)}")
            
            # Call GLM API synchronously (in thread pool for async compat)
            loop = asyncio.get_event_loop()
            
            def make_api_call():
                response = client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=16384,  # Increased to allow longer responses
                    thinking=None  # Disable thinking mode to get direct answers
                )
                return response
            
            # Run in thread pool to avoid blocking with extended timeout (60 seconds for thinking models)
            response = await asyncio.wait_for(
                loop.run_in_executor(None, make_api_call),
                timeout=70.0  # 70 seconds total timeout (60s API + 10s overhead)
            )
            
            # Debug: log full response structure
            logger.debug(f"GLM API response object: {response}")
            logger.debug(f"GLM API response type: {type(response)}")
            
            # Extract response
            if response and hasattr(response, 'choices') and response.choices:
                choice = response.choices[0]
                logger.debug(f"First choice: {choice}")
                logger.debug(f"First choice message: {choice.message}")
                
                ai_response = choice.message.content
                
                logger.info(f"GLM API raw content: '{ai_response}'")
                
                # Check if content is actually empty
                if not ai_response or not ai_response.strip():
                    logger.warning(f"GLM API returned empty content. Response: {response}")
                    raise AIBackendException("GLM API returned empty response content")
                
                # Record last used time
                self.last_used = datetime.now()
                
                logger.info(f"GLM API success: model={self.model}, response_len={len(ai_response)}")
                logger.debug(f"GLM response: {ai_response[:100]}")
                
                return ai_response
            else:
                logger.error(f"Invalid response structure: {response}")
                raise AIBackendException("Invalid response from GLM API")
        
        except Exception as e:
            logger.error(f"GLM API error: {type(e).__name__}: {e}")
            raise AIBackendException(f"GLM API error: {str(e)}")
    
    def is_configured(self) -> bool:
        """
        
        Returns:
            bool: True if configured
        """
        
        # In real mode, require API key
        return bool(self.api_key and len(self.api_key) > 0)
    
    def get_status(self) -> Dict:
        """
        Get GLM backend status.
        
        Returns:
            dict with configuration and status info
        """
        return {
            "backend": "glm",
            "model": self.model,
            "auth_mode": self.auth_mode,            
            "configured": self.is_configured(),
            "api_key_set": bool(self.api_key),
            "last_used": self.last_used.isoformat() if self.last_used else None,
        }
