"""
Command: ai.cleanup - Clear AI module database for testing/debugging.

Phase 1.5: Management command to reset database state.
"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
import sqlite3
from app.zowbot_cmd.base import BotCommand

logger = logging.getLogger(__name__)


class Cmd_Ai_Cleanup(BotCommand):
    """Clear AI module database tables."""
    
    COMMAND = "ai.cleanup"
    DESCRIPTION = "Clear AI memory and call log tables"
    
    async def execute(self, params, options):
        """
        Clear AI database tables.
        
        Clears:
        - ai_memory: All conversation history
        - ai_call_log: All API call logs
        
        Preserves:
        - ai_config: Configuration settings
        
        Returns:
            Status report with counts cleared
        """
        ai_service = self.bot.botLayer.ai_service if hasattr(self.bot.botLayer, 'ai_service') else None
        
        if not ai_service:
            return self.fail(error="AI service not initialized")
        
        memory = ai_service.memory
        
        try:
            import sqlite3
            conn = sqlite3.connect(memory.db_path)
            cursor = conn.cursor()
            
            # Get counts before clearing
            cursor.execute("SELECT COUNT(*) FROM ai_memory")
            memory_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM ai_call_log")
            call_log_count = cursor.fetchone()[0]
            
            # Clear tables
            cursor.execute("DELETE FROM ai_memory")
            cursor.execute("DELETE FROM ai_call_log")
            
            # Reset auto-increment sequences
            cursor.execute("DELETE FROM sqlite_sequence WHERE name='ai_memory'")
            cursor.execute("DELETE FROM sqlite_sequence WHERE name='ai_call_log'")
            
            conn.commit()
            conn.close()
            
            logger.info(f"AI cleanup: cleared {memory_count} memory + {call_log_count} logs")
            return self.success(
                message=f"✅ Cleared {memory_count} memory records and {call_log_count} call logs",
                cleared={
                    "ai_memory": memory_count,
                    "ai_call_log": call_log_count
                }
            )
        
        except Exception as e:
            logger.error(f"AI cleanup error: {e}", exc_info=True)
            return self.fail(error=str(e))
