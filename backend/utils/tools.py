"""
杂项工具模块 - 提供语音转换、Token 估算等特定功能。
"""

import asyncio
from typing import Any, Dict, Optional, Tuple, TYPE_CHECKING
from ..types import MessageEvent
from ..utils.message import is_voice_message, parse_voice_to_text_result

if TYPE_CHECKING:
    from ..core.ai_client import AIClient

__all__ = [
    "transcribe_voice_message",
    "estimate_exchange_tokens",
]


async def transcribe_voice_message(
    event: MessageEvent,
    bot_cfg: Dict[str, Any],
    wx_lock: asyncio.Lock,
) -> Tuple[Optional[str], Optional[str]]:
    """
    调用微信接口将语音消息转换为文本。
    
    Returns:
        (text, error): 成功返回 (文本, None)，失败返回 (None, 错误原因)
    """
    if not is_voice_message(event.msg_type):
        return event.content, None
    if not bot_cfg.get("voice_to_text", True):
        return None, "disabled"
    raw_item = event.raw_item
    if raw_item is None or not hasattr(raw_item, "to_text"):
        return None, "unsupported"
    try:
        async with wx_lock:
            result = await asyncio.to_thread(raw_item.to_text)
    except Exception as exc:
        return None, str(exc)
    return parse_voice_to_text_result(result)


def estimate_exchange_tokens(
    ai_client: "AIClient", user_text: str, reply_text: str
) -> Tuple[int, int, int]:
    """
    估算单轮对话的 Token 消耗。
    
    Returns:
        (user_tokens, reply_tokens, total_tokens)
    """
    # 注意：这里使用了 AIClient 的内部方法 _estimate_message_tokens
    # 如果 AIClient 接口变更，这里也需要调整
    if hasattr(ai_client, "_estimate_message_tokens"):
        user_tokens = ai_client._estimate_message_tokens(
            {"role": "user", "content": user_text or ""}
        )
        reply_tokens = ai_client._estimate_message_tokens(
            {"role": "assistant", "content": reply_text or ""}
        )
    else:
        # 简单估算兜底
        user_tokens = len(user_text or "")
        reply_tokens = len(reply_text or "")
        
    return user_tokens, reply_tokens, user_tokens + reply_tokens
