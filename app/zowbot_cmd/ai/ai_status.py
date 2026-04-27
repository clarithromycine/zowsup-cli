"""ai.status command module - Show AI auto-reply module status."""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
from app.zowbot_cmd.base import BotCommand

logger = logging.getLogger(__name__)


class Cmd_Ai_Status(BotCommand):
    """Show AI module status."""
    
    COMMAND = "ai.status"
    DESCRIPTION = "Show AI auto-reply module status"
    
    async def execute(self, params, options):
        """Display AI module status including backend and mock mode."""
        try:
            ai_service = self.bot.botLayer.ai_service if hasattr(self.bot.botLayer, 'ai_service') else None
            
            if not ai_service:
                return self.fail(
                    error="AI service not initialized"
                )
            
            status = ai_service.get_status()
            status["enabled"] = True
            status["phase"] = "Phase 1.5 (Retry Manager)"
            status["commands"] = [
                "ai.status",
                "ai.setbackend <model>",
                "ai.getconfig <backend>",
                "ai.test",
                "ai.persist",
                "ai.cleanup"
            ]
            
            logger.info(f"AI status requested")
            return self.success(
                status=status
            )
        
        except Exception as e:
            logger.error(f"ai.status error: {e}")
            return self.fail(error=str(e))
