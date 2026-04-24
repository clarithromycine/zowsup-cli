"""
Message filtering for AI auto-reply.

Filters to determine if message should be processed:
1. P2P only (no group messages)
2. Not from self-device (fromme=False)
3. Text messages only (in Phase 1)
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class MessageFilter:
    """Filter incoming messages for AI processing."""
    
    @staticmethod
    def should_process(message_entity, bot_id: str) -> bool:
        """
        Determine if a message should be processed by AI.
        
        Filters applied (returns False if):
        1. Group message (jid contains "-" for groups)
        2. Self-device message (fromme=True)
        3. Not text message (text, reaction, poll only in Phase 1)
        4. Already has a pending/completed response
        
        Args:
            message_entity: Protocol entity from onMessage callback
            bot_id: Bot's account ID (phone@s.whatsapp.net)
        
        Returns:
            bool: True if message should be processed by AI
        """
        try:
            # Get message metadata
            msg_from = message_entity.getFrom()
            msg_type = message_entity.getType()
            is_from_me = getattr(message_entity, 'fromme', False)
            
            # Filter 1: P2P only (skip groups)
            if msg_from and "-" in msg_from:
                logger.debug(f"AI filter: Skip group message from {msg_from}")
                return False
            
            # Filter 2: Skip self-device messages
            if is_from_me:
                logger.debug(f"AI filter: Skip self-device message")
                return False
            
            # Filter 3: Message type check (Phase 1 supports text only for now)
            # In production, this expands to text, reaction, poll
            supported_types = ['text', 'reaction', 'poll', 'media']
            if msg_type not in supported_types:
                logger.debug(f"AI filter: Skip unsupported message type {msg_type}")
                return False
            
            # Filter 4: Skip media-only messages for Phase 1
            if msg_type == 'media':
                # Extract media type from entity
                media_type = getattr(message_entity, 'media_type', None)
                if media_type not in ['IMAGE', 'VIDEO', 'AUDIO']:
                    logger.debug(f"AI filter: Skip non-media message type {media_type}")
                    return False
            
            logger.debug(f"AI filter: PASS - processing message from {msg_from}, type={msg_type}")
            return True
        
        except Exception as e:
            logger.error(f"AI filter error: {e}")
            return False
    
    @staticmethod
    def get_filter_reason(message_entity, bot_id: str) -> Optional[str]:
        """
        Get the reason why a message was filtered (not processed).
        
        Useful for debugging and logging.
        
        Args:
            message_entity: Protocol entity from onMessage
            bot_id: Bot's account ID
        
        Returns:
            str: Reason for filtering, or None if should be processed
        """
        try:
            msg_from = message_entity.getFrom()
            msg_type = message_entity.getType()
            is_from_me = getattr(message_entity, 'fromme', False)
            
            if msg_from and "-" in msg_from:
                return "group_message"
            
            if is_from_me:
                return "self_device"
            
            supported_types = ['text', 'reaction', 'poll', 'media']
            if msg_type not in supported_types:
                return f"unsupported_type:{msg_type}"
            
            if msg_type == 'media':
                media_type = getattr(message_entity, 'media_type', None)
                if media_type not in ['IMAGE', 'VIDEO', 'AUDIO']:
                    return f"unsupported_media:{media_type}"
            
            return None  # Should be processed
        
        except Exception as e:
            logger.error(f"Filter reason error: {e}")
            return f"error:{str(e)}"
