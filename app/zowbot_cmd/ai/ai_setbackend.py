"""ai.setbackend command module - Set active LLM backend."""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
from app.zowbot_cmd.base import BotCommand

logger = logging.getLogger(__name__)


class Cmd_Ai_Setbackend(BotCommand):
    """Set active LLM backend."""
    
    COMMAND = "ai.setbackend"
    DESCRIPTION = "Set active LLM backend model"
    
    async def execute(self, params, options):
        """Set the active LLM backend model."""
        try:
            if not params:
                return self.fail(error="Model name required. Usage: ai.setbackend glm-4-plus")
            
            model_name = params[0].lower()
            
            # Validate model
            valid_models = ["glm-4-plus", "glm-4", "glm-3.5-turbo"]
            if model_name not in valid_models:
                return self.fail(
                    error=f"Model '{model_name}' not supported in Phase 1",
                    supported_models=valid_models
                )
            
            ai_service = self.bot.botLayer.ai_service if hasattr(self.bot.botLayer, 'ai_service') else None
            if ai_service:
                ai_service.config['ai_llm_active'] = {'model': model_name}
                ai_service.backend = ai_service._init_backend()
            
            logger.info(f"AI backend set to {model_name}")
            return self.success(backend=model_name, status="ok", message=f"Backend set to {model_name} (mock mode)")
        
        except Exception as e:
            logger.error(f"ai.setbackend error: {e}")
            return self.fail(error=str(e))
