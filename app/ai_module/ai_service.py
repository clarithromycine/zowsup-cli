"""
AI Service - Main orchestrator for AI auto-reply processing.

Coordinates:
- Message filtering
- Memory management
- Backend API calls
- Retry logic
"""

import logging
import asyncio
from typing import Optional, Dict
from datetime import datetime, timedelta

from app.ai_module.memory.memory import ConversationMemory
from app.ai_module.filter.message_filter import MessageFilter
from app.ai_module.backend.base import AIBackendBase, AIBackendException
from app.ai_module.backend.glm_backend import GLMBackend
from app.ai_module.backend.qwen_backend import QWENBackend
from app.ai_module.retry.retry_manager import RetryManager

# Import WhatsApp message types for proper extraction
try:
    from core.layers.protocol_messages.protocolentities.message_text import TextMessageProtocolEntity
    from core.layers.protocol_messages.protocolentities.message_extendedtext import ExtendedTextMessageProtocolEntity
except ImportError:
    # Fallback: will check with isinstance() and handle gracefully
    TextMessageProtocolEntity = None
    ExtendedTextMessageProtocolEntity = None

logger = logging.getLogger(__name__)


class AIService:
    """Main AI service orchestrator."""
    
    def __init__(self, db_path: str, config: Dict = None):
        """
        Initialize AI service.
        
        Args:
            db_path: Path to account-specific SQLite database
            config: Configuration dict with LLM settings            
        """
        self.db_path = db_path
        self.config = config or {}        
        
        # Initialize components
        self.memory = ConversationMemory(db_path)
        self.backend = self._init_backend()
        
        # Phase 1.5: Initialize retry manager
        retry_config = config.get('ai_retry', {})
        self.retry_manager = RetryManager(
            memory=self.memory,
            backend=self.backend,
            config=retry_config
        )
        
        # Background retry task
        self._retry_task = None
        self._retry_stop_flag = False  # Flag to stop retry task gracefully
        
        logger.debug(f"AIService initialized: "
                   f"retry_enabled={retry_config.get('enabled', False)}")
    
    def set_send_response_callback(self, callback):
        """
        Set the callback function for sending responses to users.
        
        This should be called by the bot layer after initializing AIService.
        The callback will be used during retry to send responses to users.
        
        Args:
            callback: Async function with signature: async def callback(user_jid: str, ai_response: str)
        """
        self.retry_manager.send_response_callback = callback
        logger.debug("send_response_callback configured for retry manager")
    
    def _init_backend(self) -> AIBackendBase:
        """
        Initialize backend based on configuration.
        
        Flow:
        1. Read 'backend' from AI_LLM_ACTIVE (GLM, QWEN, etc.)
        2. Find corresponding AI_LLM_[BACKEND] section
        3. Read model and auth parameters
        4. Initialize the backend
        
        Returns:
            AIBackendBase: Initialized backend (GLM or QWEN)
        """
        # Get active backend from AI_LLM_ACTIVE
        active_config = self.config.get('ai_llm_active', {})
        backend_name = active_config.get('backend', 'GLM').upper()
        
        try:
            # GLM backend
            if backend_name == 'GLM':
                glm_config = self.config.get('ai_llm_glm', {})
                model = glm_config.get('model', 'glm-4-plus')
                api_key = glm_config.get('api_key', '')
                auth_mode = glm_config.get('auth_mode', 'apikey')
                
                backend = GLMBackend(
                    api_key=api_key,
                    model=model,
                    auth_mode=auth_mode
                )
                logger.info(f"✓ Initialized GLM backend: model={model}, auth_mode={auth_mode}")
                return backend
            
            # QWEN backend
            elif backend_name == 'QWEN':
                qwen_config = self.config.get('ai_llm_qwen', {})
                model = qwen_config.get('model', 'qwen-plus')
                auth_mode = qwen_config.get('auth_mode', 'apikey')
                
                # API key mode
                api_key = qwen_config.get('api_key', '')
                backend = QWENBackend(
                    api_key=api_key,
                    model=model,
                    auth_mode='apikey'
                )
                logger.info(f"Initialized QWEN backend (API Key): model={model}")
                
                return backend
            
            # Unsupported backend
            else:
                logger.warning(f"Backend '{backend_name}' not supported")
                raise ValueError(f"Unsupported backend: {backend_name}")
        
        except Exception as e:
            logger.error(f"Failed to initialize backend '{backend_name}': {e}", exc_info=True)
            # Fallback to GLM mock mode
            return None
    
    async def process_message(self, message_entity, user_jid: str, 
                             bot_id: str = None) -> Optional[str]:
        """
        Main entry point for AI message processing.
        
        Flow:
        1. Check if should process (filter)
        2. Load user's 3-day memory
        3. Send to LLM backend
        4. Store Q&A pair in memory
        5. Return response for sending to user
        
        Phase 1.5: Enhanced error handling and retry logging.
        
        Args:
            message_entity: WhatsApp message protocol entity
            user_jid: Sender's JID
            bot_id: Bot's account ID (optional)
        
        Returns:
            str: AI response text, or None if not processed
        """
        msg_id = message_entity.getId() if hasattr(message_entity, 'getId') else "unknown"
        
        try:
            # Step 1: Check if should process
            if not MessageFilter.should_process(message_entity, bot_id or ""):
                reason = MessageFilter.get_filter_reason(message_entity, bot_id or "")
                logger.debug(f"Message {msg_id} filtered out: {reason}")
                return None
            
            # Trigger daily cleanup check
            self.memory.daily_cleanup(user_jid)
            
            # Step 2: Get memory context and extract user message
            # Handle different message types (text, media captions, etc.)
            user_msg = ""
            msg_type = message_entity.getType() if hasattr(message_entity, 'getType') else "unknown"
            
            # Log message entity details
            logger.debug(f"[MSG EXTRACT] message_entity type: {type(message_entity).__name__}")
            
            # Method 1: Use isinstance() for proper type checking
            if msg_type == 'text':
                if TextMessageProtocolEntity and isinstance(message_entity, TextMessageProtocolEntity):
                    user_msg = message_entity.getBody() or ""
                    logger.debug(f"[MSG EXTRACT] TextMessageProtocolEntity.getBody(): {repr(user_msg[:50])}")
                elif ExtendedTextMessageProtocolEntity and isinstance(message_entity, ExtendedTextMessageProtocolEntity):
                    user_msg = message_entity.text or ""
                    logger.debug(f"[MSG EXTRACT] ExtendedTextMessageProtocolEntity.text: {repr(user_msg[:50])}")
                else:
                    # Fallback for unknown text message types
                    logger.debug(f"[MSG EXTRACT] Unknown text message type, checking attributes...")
                    if hasattr(message_entity, 'getBody'):
                        user_msg = message_entity.getBody() or ""
                        logger.debug(f"[MSG EXTRACT] Using getBody(): {repr(user_msg[:50])}")
                    elif hasattr(message_entity, 'text'):
                        user_msg = message_entity.text or ""
                        logger.debug(f"[MSG EXTRACT] Using .text: {repr(user_msg[:50])}")
            
            # Method 2: Fallback for other message types with captions
            if not user_msg and hasattr(message_entity, 'getCaption'):
                user_msg = message_entity.getCaption() or ""
                logger.debug(f"[MSG EXTRACT] Using getCaption(): {repr(user_msg[:50])}")
            
            memory_context = self.memory.get_recent_memory(user_jid=user_jid)
            
            # Final log after extraction
            logger.debug(f"[MSG EXTRACT] Final result: user_msg={repr(user_msg[:50] if user_msg else user_msg)} (len={len(user_msg)})")
            
            # Early exit: Skip empty messages
            if not user_msg or not user_msg.strip():
                logger.warning(f"Message {msg_id} has no text content (msg_type={msg_type}), "
                              "skipping AI processing")
                return None
            
            # Step 3: Call AI backend with enhanced error handling
            # Initialize call log entry at the start of processing
            self.memory.log_call(msg_id, user_jid)
            
            if not self.backend.is_configured():
                logger.warning("AI backend not configured, skipping processing")
                # Update failed call log with retry scheduling
                next_retry_time = (datetime.now() + timedelta(
                    minutes=self.config.get('ai_retry', {}).get('retry_delay_minutes', 5)
                )).isoformat()
                self.memory._update_call_log(
                    message_id=msg_id,
                    status='retry_scheduled',
                    attempt_count=0,
                    next_retry_time=next_retry_time,
                    error_msg='Backend not configured'
                )
                return None
            
            try:
                response = await self.backend.send_message(user_msg, memory_context)
            except AIBackendException as e:
                # Phase 1.5: Log failure with error details for retry
                error_msg = str(e)
                logger.error(f"AI backend error for {msg_id}: {error_msg}")
                
                # Update with failure details
                next_retry_time = (datetime.now() + timedelta(
                    minutes=self.config.get('ai_retry', {}).get('retry_delay_minutes', 5)
                )).isoformat()
                
                self.memory._update_call_log(
                    message_id=msg_id,
                    status='retry_scheduled',
                    attempt_count=1,
                    next_retry_time=next_retry_time,
                    error_msg=error_msg
                )
                return None
            except Exception as e:
                # Unexpected backend error
                error_msg = f"Unexpected backend error: {str(e)}"
                logger.error(f"Unexpected error for {msg_id}: {error_msg}")
                
                self.memory._update_call_log(
                    message_id=msg_id,
                    status='failed',
                    attempt_count=1,
                    error_msg=error_msg
                )
                return None
            
            if not response:
                logger.warning(f"AI backend returned empty response for {msg_id}")
                # Schedule retry for empty response
                next_retry_time = (datetime.now() + timedelta(
                    minutes=self.config.get('ai_retry', {}).get('retry_delay_minutes', 5)
                )).isoformat()
                self.memory._update_call_log(
                    message_id=msg_id,
                    status='retry_scheduled',
                    attempt_count=0,
                    next_retry_time=next_retry_time,
                    error_msg='Empty backend response'
                )
                return None
            
            # Step 4: Store conversation pair
            msg_type = message_entity.getType() if hasattr(message_entity, 'getType') else 'text'
            self.memory.store_conversation(
                user_jid=user_jid,
                message_type=msg_type,
                user_msg=user_msg,
                ai_response=response
            )
            
            # Mark call as successful
            self.memory._update_call_status(msg_id, 'success')
                        
            return response
        
        except Exception as e:
            # Catch-all for unexpected errors
            logger.error(f"Unexpected error processing message {msg_id}: {e}", exc_info=True)
            return None
    
    def get_status(self) -> Dict:
        """
        Get AI service status information.
        
        Returns:
            dict with status of backends, memory, configuration
        """
        return {
            "enabled": True,
            "backend_status": self.backend.get_status(),            
            "memory_path": self.db_path,
            "retry_enabled": self.config.get('ai_retry', {}).get('enabled', False),
        }
    
    async def start_background_retry_task(self, check_interval_seconds: int = 60):
        """
        Start background task for retry checking.
        
        Phase 1.5: Periodic task to check and retry failed messages.
        Uses _retry_stop_flag for graceful shutdown.
        
        Args:
            check_interval_seconds: How often to check for retry (default 60s)
        """
        retry_config = self.config.get('ai_retry', {})
        if not retry_config.get('enabled', False):
            logger.debug("Retry manager disabled, skipping background task")
            return
        
        logger.debug("Starting background retry task")
        while not self._retry_stop_flag:  # Check stop flag
            try:
                if self._retry_stop_flag:  # Double-check before expensive operation
                    logger.debug("Stop flag set, exiting retry task")
                    break
                
                result = await self.retry_manager.check_and_retry_failed_messages()
                
                if result['retried'] > 0:
                    logger.debug(f"Retry check: checked={result['checked']}, "
                              f"retried={result['retried']}, "
                              f"succeeded={result['succeeded']}, "
                              f"still_failed={result['still_failed']}")
                
                # Sleep in small intervals to check stop flag frequently
                for _ in range(check_interval_seconds):
                    if self._retry_stop_flag:
                        logger.debug("Stop flag set during sleep, exiting retry task")
                        return
                    await asyncio.sleep(1)
            
            except asyncio.CancelledError:
                logger.debug("Retry task cancelled")
                return
            except Exception as e:
                logger.error(f"Error in retry background task: {e}")
                if self._retry_stop_flag:
                    return
                await asyncio.sleep(check_interval_seconds)
    
    def start_retry_task(self, check_interval_seconds: int = 60):
        """
        Create and start the background retry task asyncio task.
        
        Should be called from async context (e.g., in onSuccess callback).
        
        Args:
            check_interval_seconds: How often to check for retry
        """
        if self._retry_task is None or self._retry_task.done():
            # Reset stop flag for new task
            self._retry_stop_flag = False
            
            logger.debug("Creating new retry background task")
            try:
                # Get or create event loop
                loop = asyncio.get_event_loop()
                self._retry_task = loop.create_task(
                    self.start_background_retry_task(check_interval_seconds)
                )
            except RuntimeError:
                # No event loop in current thread, will be started externally
                logger.warning("No event loop available, retry task must be started externally")
    
    def cancel_retry_task(self):
        """
        Stop and cancel the background retry task gracefully.
        
        Phase 1.5: Called when disconnecting to prevent orphaned tasks.
        Uses flag-based approach instead of direct cancel() for clean shutdown.
        """
        logger.debug("Requesting background retry task to stop")
        self._retry_stop_flag = True
        
        if self._retry_task and not self._retry_task.done():
            logger.debug("Task still running, will exit on next flag check")
            self._retry_task.cancel()
        
        self._retry_task = None
        

