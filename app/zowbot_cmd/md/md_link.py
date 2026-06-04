"""md.link command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import asyncio
import logging
from app.zowbot_cmd.base import BotCommand
from core.layers.protocol_iq.protocolentities import MultiDevicePairDeviceIqProtocolEntity
from common.utils import Utils
from core.layers.protocol_iq.protocolentities import MultiDevicePairDeviceResultIqProtocolEntity

logger = logging.getLogger(__name__)



class Cmd_Md_Link(BotCommand):
    COMMAND = "md.link"
    DESCRIPTION = "Multi-device link"


    async def execute(self, params, options):

        bot = self.bot

        await bot.botLayer.resetSync(params, options)        
        profile = bot.botLayer.getStack().getProp("profile")
        qr_str = params[0]
        if "#" in qr_str:
            qr_str = qr_str.split("#", 1)[1].strip()
        ref, pubKey, deviceIdentity, keyIndexList = Utils.generateMultiDeviceParamsFromQrCode(qr_str, profile)
        

        try:
            entity = MultiDevicePairDeviceIqProtocolEntity(
                ref=ref,
                pubKey=pubKey,
                deviceIdentity=deviceIdentity,
                keyIndexList=keyIndexList
            )

            result = await self.send_iq_expect(entity, MultiDevicePairDeviceResultIqProtocolEntity)
            companionJid = result.deviceJid
            deviceIdx = int(companionJid.split("@")[0].split(":")[1])
            profile.config.add_device_to_list(deviceIdx)
            profile.write_config(profile.config)
            
            bot.botLayer.getStack().setProp("pair-companion-jid", companionJid)
            logger.info(f"Device paired: {companionJid}")

            sync_future = asyncio.get_running_loop().create_future()
            bot.botLayer.getStack().setProp("md-link-sync-future", sync_future)
            try:
                wait_seconds = int(options.get("mdlinkwait", 180)) if options else 180
                logger.info("Waiting for md.link account sync to complete")
                await asyncio.wait_for(sync_future, timeout=wait_seconds)
                logger.info("md.link account sync completed")
            finally:
                bot.botLayer.getStack().setProp("md-link-sync-future", None)

            return self.success(
                deviceJid = result.deviceJid,
            )
                
        except Exception as e:
            logger.error(f"{self.COMMAND} error: {e}")
            return self.fail(error=str(e))
        


