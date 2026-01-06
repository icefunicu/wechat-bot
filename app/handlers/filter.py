"""
消息过滤器模块 - 负责判断是否回复消息。
"""

import logging
from typing import Any, Dict



from ..types import MessageEvent
from ..utils.common import iter_items

__all__ = ["should_reply"]


def should_reply(event: MessageEvent, config: Dict[str, Any]) -> bool:
    """
    判断是否应该回复该消息。
    
    规则：
    1. 忽略空消息、自己发送的消息
    2. 忽略公众号/服务号通知（可配置）
    3. 忽略黑名单（名称/关键词）
    4. 群聊仅在被 @ 时回复（可配置）
    5. 群聊白名单过滤（可配置）
    """
    bot_cfg = config.get("bot", {})
    self_name = bot_cfg.get("self_name", "")

    if not event.content.strip():
        logging.debug("跳过空消息：%s", event.chat_name)
        return False
    if event.is_self:
        logging.debug("跳过自己发送的消息：%s", event.chat_name)
        return False
    if self_name and event.sender == self_name:
        logging.debug("跳过发送人等于自己昵称：%s", event.chat_name)
        return False

    if bot_cfg.get("ignore_official", True) and event.chat_type == "official":
        logging.debug("跳过公众号：%s", event.chat_name)
        return False
    if bot_cfg.get("ignore_service", True) and event.chat_type == "service":
        logging.debug("跳过服务号：%s", event.chat_name)
        return False

    ignore_names = [
        str(name).strip()
        for name in iter_items(bot_cfg.get("ignore_names", []))
        if str(name).strip()
    ]
    ignore_keywords = [
        str(keyword).strip()
        for keyword in iter_items(bot_cfg.get("ignore_keywords", []))
        if str(keyword).strip()
    ]
    if ignore_names or ignore_keywords:
        chat_name_norm = event.chat_name.strip().lower()
        ignore_name_set = {name.lower() for name in ignore_names}
        if chat_name_norm in ignore_name_set:
            logging.debug("跳过忽略会话：%s", event.chat_name)
            return False
        for keyword in ignore_keywords:
            if keyword in event.chat_name:
                logging.debug(
                    "跳过会话：%s（命中忽略关键词：%s）",
                    event.chat_name,
                    keyword,
                )
                return False

    if bot_cfg.get("group_reply_only_when_at", False) and event.is_group:
        if not event.is_at_me:
            logging.debug("群聊未被 @，跳过：%s", event.chat_name)
            return False

    if bot_cfg.get("whitelist_enabled", False) and event.is_group:
        whitelist = set(bot_cfg.get("whitelist", []))
        if event.chat_name not in whitelist:
            logging.debug("群聊不在白名单，跳过：%s", event.chat_name)
            return False

    return True
