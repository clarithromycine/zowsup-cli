"""ai.getconfig command module - Get backend configuration from config.conf."""

from typing import Any, Optional, Dict, List
import logging
from app.zowbot_cmd.base import BotCommand

logger = logging.getLogger(__name__)


class Cmd_Ai_Getconfig(BotCommand):
    """Get backend configuration based on config.conf."""
    
    COMMAND = "ai.getconfig"
    DESCRIPTION = "Get AI backend configuration"
    
    async def execute(self, params, options):
        """
        Show backend configuration.
        
        Usage:
        - ai.getconfig               : Show active backend config
        - ai.getconfig active        : Show AI_LLM_ACTIVE status
        - ai.getconfig glm           : Show GLM backend config
        - ai.getconfig qwen          : Show QWEN backend config
        """
        try:
            ai_service = self.bot.botLayer.ai_service if hasattr(self.bot.botLayer, 'ai_service') else None
            
            if not ai_service:
                return self.fail(error="AI service not initialized")
            
            # Parse parameter (default to empty = show active backend)
            query_type = params[0].lower() if params else "active"
            
            # Get AI_LLM_ACTIVE configuration
            active_config = ai_service.config.get('ai_llm_active', {})
            enabled = active_config.get('enabled', True)
            backend = active_config.get('backend', 'GLM').upper()
            
            if query_type == "active":
                # Show AI_LLM_ACTIVE status
                config = {
                    "status": "enabled" if enabled else "disabled",
                    "active_backend": backend,
                    "backend_config": self._get_backend_config(ai_service, backend)
                }
            
            elif query_type == backend.lower():
                # Show specific backend config (matches active backend)
                config = {
                    "backend": backend,
                    "is_active": True,
                    **self._get_backend_config(ai_service, backend)
                }
            
            elif query_type in ["glm", "qwen"]:
                # Show any backend config (even if not active)
                config = {
                    "backend": query_type.upper(),
                    "is_active": (query_type.upper() == backend),
                    **self._get_backend_config(ai_service, query_type.upper())
                }
            
            elif query_type == "all":
                # Show all backends configuration
                config = {
                    "ai_llm_active": {
                        "enabled": enabled,
                        "backend": backend
                    },
                    "ai_llm_glm": self._get_backend_config(ai_service, "GLM"),
                    "ai_llm_qwen": self._get_backend_config(ai_service, "QWEN")
                }
            
            else:
                return self.fail(
                    error=f"Unknown query type: {query_type}",
                    usage="ai.getconfig [active|glm|qwen|all]"
                )
            
            logger.info(f"AI config retrieved for {query_type}")
            return self.success(config=config)
        
        except Exception as e:
            logger.error(f"ai.getconfig error: {e}", exc_info=True)
            return self.fail(error=str(e))
    
    def _get_backend_config(self, ai_service, backend: str) -> Dict[str, Any]:
        """
        Get configuration for a specific backend from AI_LLM_[BACKEND] section.
        
        Args:
            ai_service: AI service instance
            backend: Backend name (GLM, QWEN, etc.)
        
        Returns:
            Dictionary with backend configuration
        """
        backend_upper = backend.upper()
        config_key = f'ai_llm_{backend_upper.lower()}'
        backend_config = ai_service.config.get(config_key, {})
        
        result = {
            "model": backend_config.get('model', 'N/A'),
            "auth_mode": backend_config.get('auth_mode', 'N/A'),
            "api_key_configured": bool(backend_config.get('api_key'))
        }
        
        # Add backend-specific parameters
        if backend_upper == "QWEN":
            # QWEN might have OAuth tokens
            result["oauth_refresh_token_configured"] = bool(
                backend_config.get('oauth_refresh_token')
            )
            result["oauth_access_token_configured"] = bool(
                backend_config.get('oauth_access_token')
            )
        
        return result
