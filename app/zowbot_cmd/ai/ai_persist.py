"""
Command: ai.persist - Check message persistence and retry status.

Phase 1.5: Verify stored messages and failed retry queue.
"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
from app.zowbot_cmd.base import BotCommand

logger = logging.getLogger(__name__)


class Cmd_Ai_Persist(BotCommand):
    """Check AI message persistence in database."""
    
    COMMAND = "ai.persist"
    DESCRIPTION = "Check message persistence and retry status"
    
    async def execute(self, params, options):
        """
        Check AI persistence status.
        
        Returns:
            Status report with table counts and failed messages
        """
        ai_service = self.bot.botLayer.ai_service if hasattr(self.bot.botLayer, 'ai_service') else None
        
        if not ai_service:
            return self.fail(error="AI service not initialized")
        
        memory = ai_service.memory
        
        try:
            # Get database stats
            stats = {
                'ai_memory_count': 0,
                'ai_call_log_count': 0,
                'failed_count': 0,
                'pending_count': 0,
            }
            
            # Query counts
            import sqlite3
            conn = sqlite3.connect(memory.db_path)
            cursor = conn.cursor()
            
            # Count ai_memory records
            cursor.execute("SELECT COUNT(*) FROM ai_memory")
            stats['ai_memory_count'] = cursor.fetchone()[0]
            
            # Count ai_call_log records
            cursor.execute("SELECT COUNT(*) FROM ai_call_log")
            stats['ai_call_log_count'] = cursor.fetchone()[0]
            
            # Count failed records
            cursor.execute("""
                SELECT COUNT(*) FROM ai_call_log 
                WHERE status IN ('failed', 'retry_scheduled')
            """)
            stats['failed_count'] = cursor.fetchone()[0]
            
            # Count pending records
            cursor.execute("""
                SELECT COUNT(*) FROM ai_call_log 
                WHERE status = 'pending'
            """)
            stats['pending_count'] = cursor.fetchone()[0]
            
            # Get recent memory sample (last 3 records)
            cursor.execute("""
                SELECT user_jid, user_message, ai_response, created_at
                FROM ai_memory
                ORDER BY created_at DESC
                LIMIT 3
            """)
            recent_memory = cursor.fetchall()
            
            # Get failed messages for retry
            cursor.execute("""
                SELECT message_id, user_jid, status, attempt_count, error_msg, next_retry_time
                FROM ai_call_log
                WHERE status IN ('failed', 'retry_scheduled', 'pending')
                ORDER BY created_at DESC
                LIMIT 5
            """)
            failed_messages = cursor.fetchall()
            
            conn.close()
            
            # Build response
            response = "📊 **AI Persistence Status**\n\n"
            response += f"**Storage Stats:**\n"
            response += f"• ai_memory records: {stats['ai_memory_count']}\n"
            response += f"• ai_call_log records: {stats['ai_call_log_count']}\n"
            response += f"• Failed/Retry: {stats['failed_count']}\n"
            response += f"• Pending: {stats['pending_count']}\n\n"
            
            if recent_memory:
                response += "**Recent Memory (Last 3):**\n"
                for i, (jid, user_msg, ai_resp, created) in enumerate(recent_memory, 1):
                    user_msg_preview = user_msg[:30] + "..." if len(user_msg) > 30 else user_msg
                    ai_resp_preview = ai_resp[:30] + "..." if len(ai_resp) > 30 else ai_resp
                    response += f"{i}. {jid}\n"
                    response += f"   Q: {user_msg_preview}\n"
                    response += f"   A: {ai_resp_preview}\n"
                    response += f"   Time: {created[:16]}\n"
            
            if failed_messages:
                response += f"\n**Retry Queue ({len(failed_messages)}):**\n"
                for msg_id, jid, status, attempts, error, retry_time in failed_messages:
                    error_preview = error[:40] + "..." if error and len(error) > 40 else error
                    response += f"• {msg_id[:8]}... | {status} | attempts={attempts}\n"
                    if error:
                        response += f"  Error: {error_preview}\n"
                    if retry_time:
                        response += f"  Retry at: {retry_time[:16]}\n"
            else:
                response += "\n✅ No failed messages in queue\n"
            
            response += f"\n**Retry Settings:**\n"
            ai_config = self.bot.botLayer._load_ai_config() if hasattr(self.bot.botLayer, '_load_ai_config') else {}
            retry_config = ai_config.get('ai_retry', {})
            response += f"• Enabled: {retry_config.get('enabled', False)}\n"
            response += f"• Delay: {retry_config.get('retry_delay_minutes', 5)} min\n"
            response += f"• Max attempts: {retry_config.get('max_retry_attempts', 1)}\n"
            
            logger.info(f"AI persistence status requested: {stats}")
            return self.success(
                message=response.replace("**", "").replace("*", ""),  # Remove markdown
                stats=stats,
                retry_queue_size=len(failed_messages)
            )
        
        except Exception as e:
            logger.error(f"Failed to get persistence status: {e}", exc_info=True)
            return self.fail(error=str(e))
