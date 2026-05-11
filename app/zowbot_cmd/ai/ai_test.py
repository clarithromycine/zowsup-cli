"""ai.test command module - Test AI backend connectivity."""

import logging
from app.zowbot_cmd.base import BotCommand

logger = logging.getLogger(__name__)


class Cmd_Ai_Test(BotCommand):
    """Test AI backend connectivity."""
    
    COMMAND = "ai.test"
    DESCRIPTION = "Test AI backend in mock mode"
    
    async def execute(self, params, options):
        """Test the AI backend with a mock message."""
        try:
            ai_service = self.bot.botLayer.ai_service if hasattr(self.bot.botLayer, 'ai_service') else None
            
            if not ai_service:
                return self.fail(error="AI service not initialized")
            
            # Create mock message entity for testing
            test_entity = _MockMessageEntity("你好")
            test_response = await ai_service.process_message(
                test_entity,
                user_jid="test@s.whatsapp.net",
                bot_id=self.bot.botId
            )
            
            if test_response:
                logger.info(f"AI test succeeded: {test_response}")
                return self.success(
                    test_message="你好",
                    response=test_response.response,
                    backend=ai_service.backend.get_status()
                )
            else:
                logger.warning("AI test returned no response")
                return self.fail(                    
                    error="Processing complete but no response",
                    backend=ai_service.backend.get_status()
                )
        
        except Exception as e:
            logger.error(f"ai.test error: {e}")
            return self.fail(error=str(e))


class _MockMessageEntity:
    """Mock WhatsApp message entity for testing."""
    
    def __init__(self, body: str = "test", msg_from: str = "test@s.whatsapp.net"):
        self.body = body
        self.msg_from = msg_from
        self.msg_type = "text"
        self.msg_id = "mock_msg_id"
        self.fromme = False
    
    def getBody(self):
        return self.body
    
    def getFrom(self):
        return self.msg_from
    
    def getType(self):
        return self.msg_type
    
    def getId(self):
        return self.msg_id
