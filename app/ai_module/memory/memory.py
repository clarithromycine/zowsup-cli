"""
Conversation memory management with SQLite persistence.

Per-account database: ~/.zowsup/accounts/<phone>_<device_id>/db.db

Tables:
- ai_memory: Store Q&A pairs (user_message, ai_response)
- ai_call_log: Track API calls for retries (status, retry_time)
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class ConversationMemory:
    """Manage per-user conversation history with SQLite persistence."""
    
    # SQL Schema
    SCHEMA_AI_MEMORY = """
    CREATE TABLE IF NOT EXISTS ai_memory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_jid TEXT NOT NULL,
        message_type TEXT DEFAULT 'text',
        user_message TEXT NOT NULL,
        ai_response TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    
    SCHEMA_AI_CALL_LOG = """
    CREATE TABLE IF NOT EXISTS ai_call_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message_id TEXT UNIQUE NOT NULL,
        user_jid TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        attempt_count INTEGER DEFAULT 0,
        next_retry_time TIMESTAMP,
        error_msg TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_attempt_at TIMESTAMP
    );
    """
    
    def __init__(self, db_path: str):
        """
        Initialize memory manager with account-specific database.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._ensure_connection()
        self._ensure_schema()
        logger.info(f"ConversationMemory initialized at {db_path}")
    
    def _ensure_connection(self):
        """Ensure database file exists and is accessible."""
        db_file = Path(self.db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Create connection to test access
        try:
            conn = sqlite3.connect(self.db_path)
            conn.close()
            logger.debug(f"Database connection verified: {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to access database {self.db_path}: {e}")
            raise
    
    def _ensure_schema(self):
        """Create tables and indexes if they don't exist."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create tables
            cursor.execute(self.SCHEMA_AI_MEMORY)
            cursor.execute(self.SCHEMA_AI_CALL_LOG)
            
            # Create indexes for ai_memory table
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_ai_memory_user_jid ON ai_memory (user_jid)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_ai_memory_created_at ON ai_memory (created_at)"
            )
            
            # Create indexes for ai_call_log table
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_ai_call_log_message_id ON ai_call_log (message_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_ai_call_log_status ON ai_call_log (status)"
            )
            
            conn.commit()
            logger.debug("Database schema initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database schema: {e}")
            raise
        finally:
            conn.close()
    
    def get_recent_memory(self, user_jid: str, days: int = 3) -> List[Dict]:
        """
        Get conversation history for past N days.
        
        Args:
            user_jid: User's JID (e.g., "1234567890@s.whatsapp.net")
            days: Number of days to look back (default 3)
        
        Returns:
            List of dicts with keys: user_message, ai_response, created_at
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cutoff_time = datetime.now() - timedelta(days=days)
            cutoff_str = cutoff_time.isoformat()
            
            query = """
                SELECT user_message, ai_response, created_at
                FROM ai_memory
                WHERE user_jid = ? AND created_at >= ?
                ORDER BY created_at ASC
            """
            
            cursor.execute(query, (user_jid, cutoff_str))
            rows = cursor.fetchall()
            
            result = [dict(row) for row in rows]
            logger.debug(f"Retrieved {len(result)} memory records for {user_jid}")
            
            return result
        except Exception as e:
            logger.error(f"Failed to get recent memory: {e}")
            return []
        finally:
            conn.close()
    
    def store_conversation(self, user_jid: str, message_type: str,
                          user_msg: str, ai_response: str) -> bool:
        """
        Store Q&A pair immediately after successful AI response.
        
        Args:
            user_jid: User's JID
            message_type: Type of message (e.g., 'text', 'reaction', 'poll')
            user_msg: User's original message
            ai_response: AI's response
        
        Returns:
            bool: True if stored successfully, False otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            query = """
                INSERT INTO ai_memory (user_jid, message_type, user_message, ai_response)
                VALUES (?, ?, ?, ?)
            """
            
            cursor.execute(query, (user_jid, message_type, user_msg, ai_response))
            conn.commit()
            
            logger.debug(f"Stored conversation for {user_jid}")
            return True
        except Exception as e:
            logger.error(f"Failed to store conversation: {e}")
            return False
        finally:
            conn.close()
    
    def daily_cleanup(self, user_jid: str = None) -> int:
        """
        Phase 1.5: Perform daily cleanup of old records.
        
        Deletes ai_memory records older than 3 days to prevent database bloat.
        Keeps ai_call_log indefinitely (for retry history).
        
        Args:
            user_jid: Optional specific user, or None for global cleanup
        
        Returns:
            int: Number of records deleted
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cutoff_time = datetime.now() - timedelta(days=3)
            cutoff_str = cutoff_time.isoformat()
            
            if user_jid:
                # Delete old records for specific user
                delete_query = """
                    DELETE FROM ai_memory
                    WHERE user_jid = ? AND created_at < ?
                """
                cursor.execute(delete_query, (user_jid, cutoff_str))
                
                # Get count of remaining records in window
                count_query = """
                    SELECT COUNT(*) FROM ai_memory
                    WHERE user_jid = ? AND created_at >= ?
                """
                cursor.execute(count_query, (user_jid, cutoff_str))
            else:
                # Delete old records globally
                delete_query = """
                    DELETE FROM ai_memory
                    WHERE created_at < ?
                """
                cursor.execute(delete_query, (cutoff_str,))
                
                # Get total remaining records in window
                count_query = """
                    SELECT COUNT(*) FROM ai_memory
                    WHERE created_at >= ?
                """
                cursor.execute(count_query, (cutoff_str,))
            
            deleted = cursor.rowcount
            result = cursor.fetchone()
            remaining = result[0] if result else 0
            
            conn.commit()
            conn.close()
            
            if deleted > 0:
                logger.info(f"Daily cleanup: deleted {deleted} records, {remaining} remain in window")
            
            return deleted
        except Exception as e:
            logger.error(f"Failed to perform daily cleanup: {e}")
            return 0
    
    def log_call(self, message_id: str, user_jid: str, 
                 status: str = 'pending', error_msg: str = None) -> bool:
        """
        Log an AI API call for tracking and retry purposes.
        
        Phase 1.5: Initialize with next_retry_time immediately for faster retries.
        
        Args:
            message_id: WhatsApp message ID
            user_jid: User's JID
            status: Initial status (default 'pending')
            error_msg: Optional error message
        
        Returns:
            bool: True if logged successfully
        """
        try:
            from datetime import datetime, timedelta
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Set initial next_retry_time to now (for immediate retry attempt)
            next_retry_time = datetime.now().isoformat()
            
            query = """
                INSERT INTO ai_call_log (message_id, user_jid, status, next_retry_time, error_msg)
                VALUES (?, ?, ?, ?, ?)
            """
            
            cursor.execute(query, (message_id, user_jid, status, next_retry_time, error_msg))
            conn.commit()
            
            logger.debug(f"Logged AI call for message {message_id}: status={status}")
            return True
        except Exception as e:
            logger.error(f"Failed to log call: {e}")
            return False
        finally:
            conn.close()
    
    def _get_failed_messages(self) -> List[Dict]:
        """
        Get all messages that failed and are pending retry.
        
        Returns:
            list: List of dicts with failed message records
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Return rows as dicts
            cursor = conn.cursor()
            
            query = """
                SELECT 
                    cl.message_id, cl.user_jid, cl.attempt_count,
                    cl.next_retry_time, cl.error_msg,
                    am.user_message
                FROM ai_call_log cl
                LEFT JOIN ai_memory am ON am.id = (
                    SELECT id FROM ai_memory WHERE user_jid = cl.user_jid 
                    ORDER BY created_at DESC LIMIT 1
                )
                WHERE cl.status IN ('pending', 'retry_scheduled', 'failed')
                ORDER BY cl.next_retry_time ASC
            """
            
            cursor.execute(query)
            rows = cursor.fetchall()
            
            result = [dict(row) for row in rows]
            logger.debug(f"Retrieved {len(result)} failed messages for retry")
            
            conn.close()
            return result
        except Exception as e:
            logger.error(f"Failed to get failed messages: {e}")
            return []
    
    def _update_call_status(self, message_id: str, status: str) -> bool:
        """
        Update the status of a logged call.
        
        Args:
            message_id: Message ID to update
            status: New status (e.g., 'success', 'failed_permanent')
        
        Returns:
            bool: True if updated successfully
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            query = """
                UPDATE ai_call_log
                SET status = ?, last_attempt_at = CURRENT_TIMESTAMP
                WHERE message_id = ?
            """
            
            cursor.execute(query, (status, message_id))
            conn.commit()
            
            logger.debug(f"Updated message {message_id} status to {status}")
            return True
        except Exception as e:
            logger.error(f"Failed to update call status: {e}")
            return False
        finally:
            conn.close()
    
    def _update_call_log(self, message_id: str, status: str, attempt_count: int,
                        next_retry_time: str = None, error_msg: str = None) -> bool:
        """
        Update the complete call log record.
        
        Args:
            message_id: Message ID
            status: Call status
            attempt_count: Number of attempts
            next_retry_time: ISO format datetime string for next retry
            error_msg: Error message if any
        
        Returns:
            bool: True if updated successfully
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            query = """
                UPDATE ai_call_log
                SET status = ?, attempt_count = ?, next_retry_time = ?,
                    error_msg = ?, last_attempt_at = CURRENT_TIMESTAMP
                WHERE message_id = ?
            """
            
            cursor.execute(query, (status, attempt_count, next_retry_time, error_msg, message_id))
            conn.commit()
            
            logger.debug(f"Updated call log for message {message_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to update call log: {e}")
            return False
        finally:
            conn.close()
