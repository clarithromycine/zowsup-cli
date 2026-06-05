"""md.link command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import asyncio
import logging,base64
import hashlib
from app.zowbot_cmd.base import BotCommand
from core.layers.protocol_iq.protocolentities import MultiDevicePairDeviceIqProtocolEntity
from common.utils import Utils
from core.layers.protocol_iq.protocolentities import MultiDevicePairDeviceResultIqProtocolEntity

logger = logging.getLogger(__name__)


def _qr_code_meta(qr_code: str) -> dict:
    value = qr_code or ""
    return {
        "qr_len": len(value),
        "qr_sha": hashlib.sha256(value.encode("utf-8")).hexdigest()[:12] if value else "",
        "qr_url": value.startswith(("https://", "http://")),
    }



class Cmd_Md_Link(BotCommand):
    COMMAND = "md.link"
    DESCRIPTION = "Multi-device link"


    async def execute(self, params, options):

        bot = self.bot

        qr_str = params[0]
        meta = _qr_code_meta(qr_str)
        logger.info(
            "md.link command start bot_id=%s qr_len=%d qr_sha=%s qr_url=%s",
            getattr(bot, "botId", None),
            meta["qr_len"],
            meta["qr_sha"],
            meta["qr_url"],
        )
        await bot.botLayer.resetSync(params, options)        
        profile = bot.botLayer.getStack().getProp("profile")

        if qr_str.startswith("https://") or qr_str.startswith("http://"):
            qr_str = qr_str.split("#")[1]            

        ref, pubKey, deviceIdentity, keyIndexList = Utils.generateMultiDeviceParamsFromQrCode(qr_str, profile)
        logger.info(
            "md.link command parsed QR bot_id=%s ref_len=%d key_index_count=%d",
            getattr(bot, "botId", None),
            len(ref) if ref is not None else 0,
            len(keyIndexList) if keyIndexList is not None else 0,
        )
        
        try:
            entity = MultiDevicePairDeviceIqProtocolEntity(
                ref=ref,
                pubKey=pubKey,
                deviceIdentity=deviceIdentity,
                keyIndexList=keyIndexList
            )

            logger.info("md.link command sending pair-device IQ bot_id=%s", getattr(bot, "botId", None))
            result = await self.send_iq_expect(entity, MultiDevicePairDeviceResultIqProtocolEntity)
            companionJid = result.deviceJid
            deviceIdx = int(companionJid.split("@")[0].split(":")[1])
            profile.config.add_device_to_list(deviceIdx)
            profile.write_config(profile.config)
            
            bot.botLayer.getStack().setProp("pair-companion-jid", companionJid)
            logger.info("md.link command device paired bot_id=%s companion_jid=%s device_idx=%s", getattr(bot, "botId", None), companionJid, deviceIdx)
            return self.success(
                deviceJid = result.deviceJid,
                companionProps = Utils.b64str(result.companionProps)
            )
                
        except Exception as e:
            logger.error("%s error bot_id=%s qr_sha=%s error=%s", self.COMMAND, getattr(bot, "botId", None), meta["qr_sha"], e, exc_info=True)
            return self.fail(error=str(e))
        


