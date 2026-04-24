"""
QWEN backend implementation for Alibaba Cloud Bailian.

Supports:
- OAuth authentication (refresh token / access token)
- API Key authentication (fallback)
- Multiple QWEN models (qwen-max, qwen-plus, qwen-turbo)
- OpenAI-compatible API interface
- Async/await pattern
"""

import logging
import asyncio
import httpx
import json
from typing import Any, List, Dict, Optional
from datetime import datetime, timedelta
import time

from app.ai_module.backend.base import AIBackendBase, AIBackendException

logger = logging.getLogger(__name__)


class QWENBackend(AIBackendBase):
    """QWEN backend for LLM-based auto-replies using Alibaba Cloud."""
    
    # Official QWEN API endpoint (OpenAI-compatible)
    ENDPOINT = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    
    
    
    def __init__(self, refresh_token: str = None, access_token: str = None,
                 api_key: str = None, model: str = "qwen-max",
                 auth_mode: str = "apikey") -> Any:
        """
        Initialize QWEN backend.
        
        Args:
            refresh_token: OAuth refresh token from Alibaba Bailian
            access_token: Current OAuth access token (optional, will be refreshed if needed)
            api_key: API key for fallback authentication
            model: QWEN model name (default: qwen-max)
            auth_mode: 'oauth' or 'apikey'            
        """
        self.refresh_token = refresh_token
        self.access_token = access_token
        self.api_key = api_key
        self.model = model
        self.auth_mode = auth_mode        
        self.last_used = None
        self.token_expiry = None
        
        logger.info(f"QWENBackend initialized: model={self.model}, "
                   f"auth_mode={self.auth_mode}")
    
    async def send_message(self, user_message: str,
                          memory_context: List[Dict]) -> str:
        """
        Send message to QWEN backend.
        
        Args:
            user_message: User's question
            memory_context: Past conversation history (3-day window)
        
        Returns:
            str: AI response
        
        Raises:
            AIBackendException: On API errors
        """
        
        return await self._real_send_message(user_message, memory_context)
    
    def _mock_send_message(self, user_message: str,
                          memory_context: List[Dict]) -> str:
        """
        Mock QWEN API response for testing.
        
        Args:
            user_message: User's question
            memory_context: Historical Q&A pairs
        
        Returns:
            str: Mock response
        """
        context_str = ""
        if memory_context:
            context_str = "过去对话:\n"
            for item in memory_context[-10:]:  # Last 10 items (most recent)
                context_str += f"用户: {item.get('user_message', '')}\n"
                context_str += f"我: {item.get('ai_response', '')}\n"
        
        logger.debug(f"QWEN Mock mode: Processing message")
        logger.debug(f"  Context items: {len(memory_context)}")
        logger.debug(f"  User message: {user_message[:100]}")
        
        self.last_used = datetime.now()
        response = f"[Mock QWEN Response to: {user_message[:20]}...]"
        logger.debug(f"  Mock response: {response}")
        
        return response
    
    async def _refresh_access_token(self) -> bool:
        """
        Refresh OAuth access token using refresh token.
        
        Returns:
            bool: True if successful
        """
        if not self.refresh_token:
            logger.error("No refresh token available for QWEN OAuth")
            return False
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                payload = {
                    "grant_type": "refresh_token",
                    "refresh_token": self.refresh_token
                }
                
                logger.debug(f"Refreshing QWEN access token...")
                response = await client.post(
                    self.OAUTH_TOKEN_ENDPOINT,
                    json=payload
                )
                
                if response.status_code == 200:
                    data = response.json()
                    self.access_token = data.get("access_token")
                    
                    # Set expiry to 1 hour from now (typical OAuth expiry)
                    expires_in = data.get("expires_in", 3600)
                    self.token_expiry = datetime.now() + timedelta(seconds=expires_in - 60)
                    
                    logger.info(f"✓ QWEN access token refreshed, expires in {expires_in}s")
                    return True
                else:
                    logger.error(f"Failed to refresh token: {response.status_code} - {response.text}")
                    return False
        
        except Exception as e:
            logger.error(f"Error refreshing QWEN access token: {e}")
            return False
    
    async def _get_auth_header(self) -> Dict[str, str]:
        """
        Get appropriate authorization header for API call.
        
        Returns:
            dict: Authorization header
        """
        if self.auth_mode == "oauth":
            # Check if token needs refresh
            if not self.access_token or (self.token_expiry and datetime.now() > self.token_expiry):
                success = await self._refresh_access_token()
                if not success:
                    raise AIBackendException("Failed to obtain QWEN access token")
            
            return {"Authorization": f"Bearer {self.access_token}"}
        
        elif self.auth_mode == "apikey":
            # API key goes in header
            return {"Authorization": f"Bearer {self.api_key}"}
        
        else:
            raise AIBackendException(f"Unsupported auth mode: {self.auth_mode}")
    
    async def _real_send_message(self, user_message: str,
                               memory_context: List[Dict]) -> str:
        """
        Real QWEN API call.
        
        Args:
            user_message: User's question
            memory_context: Historical Q&A pairs
        
        Returns:
            str: AI response text
        
        Raises:
            AIBackendException: On API errors
        """
        try:
            # DEBUG: Log input
            logger.debug(f"[QWEN_SEND] Called with:")
            logger.debug(f"[QWEN_SEND]   user_message={repr(user_message[:80] if user_message else user_message)}")
            logger.debug(f"[QWEN_SEND]   user_message length: {len(user_message) if user_message else 0}")
            logger.debug(f"[QWEN_SEND]   memory_context length: {len(memory_context)}")
            
            # Build messages with context
            messages = []
            
            if memory_context:
                context_str = "以下是过去的对话记录:\n"
                for item in memory_context[-10:]:  # Last 10 items (most recent)
                    context_str += f"用户: {item.get('user_message', '')}\n"
                    context_str += f"助手: {item.get('ai_response', '')}\n"
                
                system_prompt = "你是一个有用且友好的WhatsApp助手,帮助用户回答问题。" + context_str
            else:
                system_prompt = "你是一个有用且友好的WhatsApp助手,帮助用户回答问题。"
            
            messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": user_message})
            
            # Get auth header
            auth_header = await self._get_auth_header()
            
            # Prepare request payload
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 1024,
                "top_p": 0.9
            }
            
            logger.debug(f"Calling QWEN API: model={self.model}, auth_mode={self.auth_mode}")
            
            # Make async HTTP call
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.ENDPOINT,
                    json=payload,
                    headers=auth_header
                )
            
            if response.status_code == 401:
                logger.error("QWEN API authentication failed (401)")
                if self.auth_mode == "oauth":
                    logger.info("Attempting token refresh...")
                    if await self._refresh_access_token():
                        # Retry with new token
                        auth_header = await self._get_auth_header()
                        async with httpx.AsyncClient(timeout=60.0) as client:
                            response = await client.post(
                                self.ENDPOINT,
                                json=payload,
                                headers=auth_header
                            )
                    else:
                        raise AIBackendException("Failed to refresh QWEN OAuth token")
                else:
                    raise AIBackendException("QWEN API authentication failed")
            
            if response.status_code != 200:
                logger.error(f"QWEN API error: {response.status_code} - {response.text}")
                raise AIBackendException(f"QWEN API error: {response.status_code}")
            
            # Parse response
            data = response.json()
            
            if "choices" not in data or not data["choices"]:
                logger.error(f"Invalid QWEN response: {data}")
                raise AIBackendException("Invalid response from QWEN API")
            
            ai_response = data["choices"][0].get("message", {}).get("content", "")
            
            if not ai_response or not ai_response.strip():
                logger.warning(f"QWEN returned empty response: {data}")
                raise AIBackendException("QWEN API returned empty response")
            
            # Record last used time
            self.last_used = datetime.now()
            
            logger.info(f"✓ QWEN API success: model={self.model}, response_len={len(ai_response)}")
            logger.debug(f"QWEN response: {ai_response[:100]}")
            
            return ai_response
        
        except AIBackendException:
            raise
        except Exception as e:
            logger.error(f"QWEN API error: {type(e).__name__}: {e}")
            raise AIBackendException(f"QWEN API error: {str(e)}")
    
    def is_configured(self) -> bool:
        """
        Check if QWEN backend is properly configured.
        
        Returns:
            bool: True if credentials are set
        """
        
        # In real mode, need either OAuth tokens or API key
        if self.auth_mode == "oauth":
            return bool(self.refresh_token)
        elif self.auth_mode == "apikey":
            return bool(self.api_key and len(self.api_key) > 0)
        
        return False
    
    def get_status(self) -> Dict:
        """
        Get QWEN backend status.
        
        Returns:
            dict with configuration and status info
        """
        return {
            "backend": "qwen",
            "model": self.model,
            "auth_mode": self.auth_mode,            
            "configured": self.is_configured(),
            "has_refresh_token": bool(self.refresh_token),
            "has_access_token": bool(self.access_token),
            "token_expiry": self.token_expiry.isoformat() if self.token_expiry else None,
            "last_used": self.last_used.isoformat() if self.last_used else None,
        }
