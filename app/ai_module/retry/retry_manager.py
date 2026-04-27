"""
AI Retry Manager - Handle failed API calls with retry logic.

Manages retry attempts for messages that failed to get AI responses.
"""

import logging
import asyncio
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)


class RetryManager:
    """Manages retry logic for failed AI API calls."""
    
    def __init__(self, memory, backend, config: Dict, send_response_callback=None):
        """
        Initialize retry manager.
        
        Args:
            memory: ConversationMemory instance
            backend: AIBackendBase instance
            config: Retry configuration with keys:
                - retry_delay_minutes: Minutes to wait before retry
                - max_retry_attempts: Maximum retry attempts
                - enabled: Whether retries are enabled
            send_response_callback: Optional async function to send response to user
                Should accept (user_jid: str, ai_response: str) parameters
        """
        self.memory = memory
        self.backend = backend
        self.retry_delay_minutes = config.get('retry_delay_minutes', 5)
        self.max_retry_attempts = config.get('max_retry_attempts', 1)
        self.enabled = config.get('enabled', True)
        self.send_response_callback = send_response_callback
        
        logger.debug(f"RetryManager initialized: delay={self.retry_delay_minutes}min, "
                     f"max_attempts={self.max_retry_attempts}, enabled={self.enabled}, "
                     f"send_callback={'configured' if send_response_callback else 'not configured'}")
    
    async def check_and_retry_failed_messages(self) -> Dict[str, int]:
        """
        Check for failed messages and retry them if conditions are met.
        
        Returns:
            dict with keys:
                - checked: Number of failed messages checked
                - retried: Number of messages actually retried
                - succeeded: Number of successful retries
                - still_failed: Number of still-failed messages
        """
        if not self.enabled:
            logger.debug("Retry manager disabled, skipping check")
            return {"checked": 0, "retried": 0, "succeeded": 0, "still_failed": 0}
        
        try:
            # Query failed messages from database
            failed_messages = self.memory._get_failed_messages()
            
            if not failed_messages:
                logger.debug("No failed messages to retry")
                return {"checked": 0, "retried": 0, "succeeded": 0, "still_failed": 0}
            
            logger.info(f"Found {len(failed_messages)} failed messages to check")
            
            checked = len(failed_messages)
            retried = 0
            succeeded = 0
            still_failed = 0
            
            current_time = datetime.now()
            
            for message_record in failed_messages:
                msg_id = message_record['message_id']
                user_jid = message_record['user_jid']
                attempt_count = message_record['attempt_count']
                next_retry_time_str = message_record['next_retry_time']
                error_msg = message_record['error_msg']
                
                # Parse retry time (handle None case for backward compatibility)
                try:
                    if next_retry_time_str is None:
                        # If no retry time set and no attempts yet, retry immediately
                        if attempt_count == 0:
                            next_retry_time = datetime.now()
                            logger.debug(f"Message {msg_id} has no retry time but 0 attempts, retrying immediately")
                        else:
                            logger.warning(f"Message {msg_id} has no retry time set, skipping")
                            continue
                    else:
                        next_retry_time = datetime.fromisoformat(next_retry_time_str)
                except Exception as parse_err:
                    logger.warning(f"Invalid retry time format for {msg_id}: {next_retry_time_str}, error: {parse_err}")
                    continue
                
                # Check if it's time to retry
                if current_time < next_retry_time:
                    logger.debug(f"Message {msg_id} not ready for retry yet (in {(next_retry_time - current_time).seconds}s)")
                    continue
                
                # Check if max attempts exceeded
                if attempt_count >= self.max_retry_attempts:
                    logger.warning(f"Message {msg_id} max retry attempts ({attempt_count}) exceeded. "
                                 f"Last error: {error_msg}")
                    still_failed += 1
                    # Update status to "failed_permanent"
                    self.memory._update_call_status(msg_id, "failed_permanent")
                    continue
                
                # Attempt retry
                retried += 1
                try:
                    logger.info(f"Retrying message {msg_id} (attempt {attempt_count + 1})")
                    
                    # Get user message from memory
                    user_message = message_record.get('user_message', '[retry]')
                    memory_context = self.memory.get_recent_memory(user_jid)
                    
                    # Call backend
                    ai_response = await self.backend.send_message(user_message, memory_context)
                    
                    if ai_response:
                        logger.info(f"Retry succeeded for message {msg_id}")
                        # Store successful response (use 'text' as default message_type)
                        self.memory.store_conversation(
                            user_jid=user_jid,
                            message_type='text',
                            user_msg=user_message,
                            ai_response=ai_response
                        )
                        # Update call log to success
                        self.memory._update_call_status(msg_id, "success")
                        succeeded += 1
                        
                        # Send response to user if callback is configured
                        if self.send_response_callback:
                            try:
                                await self.send_response_callback(user_jid, ai_response)
                                logger.info(f"Successfully sent retry response to {user_jid}")
                            except Exception as send_err:
                                logger.error(f"Failed to send retry response to {user_jid}: {send_err}")
                        else:
                            logger.warning(f"No send_response_callback configured, response not sent to {user_jid}")
                    else:
                        logger.warning(f"Retry returned empty response for message {msg_id}")
                        # Schedule next retry
                        self._schedule_next_retry(msg_id, attempt_count + 1, "Empty response")
                        still_failed += 1
                
                except Exception as retry_err:
                    logger.error(f"Retry failed for message {msg_id}: {retry_err}")
                    # Schedule next retry
                    self._schedule_next_retry(msg_id, attempt_count + 1, str(retry_err))
                    still_failed += 1
            
            result = {
                "checked": checked,
                "retried": retried,
                "succeeded": succeeded,
                "still_failed": still_failed
            }
            logger.info(f"Retry check complete: {result}")
            return result
        
        except Exception as e:
            logger.error(f"Error in check_and_retry_failed_messages: {e}", exc_info=True)
            return {"checked": 0, "retried": 0, "succeeded": 0, "still_failed": 0}
    
    def _schedule_next_retry(self, message_id: str, new_attempt_count: int, error_msg: str):
        """Schedule the next retry time for a failed message."""
        try:
            next_retry_time = datetime.now() + timedelta(minutes=self.retry_delay_minutes)
            self.memory._update_call_log(
                message_id=message_id,
                status="retry_scheduled",
                attempt_count=new_attempt_count,
                next_retry_time=next_retry_time.isoformat(),
                error_msg=error_msg
            )
            logger.debug(f"Next retry scheduled for {message_id} at {next_retry_time}")
        except Exception as e:
            logger.error(f"Failed to schedule next retry: {e}")
    
    async def start_background_retry_task(self, check_interval_seconds: int = 60):
        """
        Start a background task that periodically checks for failed messages.
        
        Args:
            check_interval_seconds: How often to check for failed messages
        """
        logger.info(f"Starting background retry task (check every {check_interval_seconds}s)")
        
        try:
            while True:
                await asyncio.sleep(check_interval_seconds)
                await self.check_and_retry_failed_messages()
        except asyncio.CancelledError:
            logger.info("Background retry task cancelled")
        except Exception as e:
            logger.error(f"Background retry task error: {e}", exc_info=True)
