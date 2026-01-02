"""
微信 AI 自动回复机器人（仅支持 Windows）。
安装步骤：
  1) pip install -r requirements.txt
  2) 编辑 config.py（API、白名单等）
  3) python main.py

注意事项：
- 使用 wxauto 驱动已登录的微信 PC 客户端（建议 3.9.x）
- 保持微信已登录且运行中
- 建议先用小号测试，自动化存在风险
"""

from __future__ import annotations

import asyncio
import importlib
import json
import logging
import os
import random
import re
import time
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from typing import Any, Dict, Iterable, List, Optional, Tuple

import ai_client as ai_module
from memory import MemoryManager

AIClient = ai_module.AIClient
try:
    from wxauto import WeChat
except Exception as exc:
    WeChat = None
    _WXAUTO_IMPORT_ERROR = exc
else:
    _WXAUTO_IMPORT_ERROR = None


DEFAULT_SUFFIX = "\n（由AI回复，模型使用{alias}）"
STREAM_PUNCTUATION = set("。！？.!?；;\n")
EMOJI_PLACEHOLDER = "[表情]"
VOICE_PLACEHOLDER = "[语音]"
EMOJI_REPLACEMENTS = {
    "\U0001F602": "[笑哭]",
    "\U0001F923": "[笑哭]",
    "\U0001F60A": "[微笑]",
    "\U0001F604": "[笑]",
    "\U0001F601": "[呲牙]",
    "\U0001F606": "[大笑]",
    "\U0001F605": "[尴尬]",
    "\U0001F609": "[眨眼]",
    "\U0001F60E": "[酷]",
    "\U0001F60D": "[色]",
    "\U0001F62D": "[大哭]",
    "\U0001F622": "[流泪]",
    "\U0001F620": "[发怒]",
    "\U0001F621": "[发怒]",
    "\U0001F914": "[疑问]",
    "\U0001F644": "[白眼]",
    "\U0001F44D": "[强]",
    "\U0001F44E": "[弱]",
    "\U0001F64F": "[合十]",
    "\U0001F4AA": "[拳头]",
    "\U0001F44F": "[鼓掌]",
    "\U0001F525": "[火]",
}
EMOJI_PATTERN = re.compile(
    "["
    "\U0001F300-\U0001F5FF"
    "\U0001F600-\U0001F64F"
    "\U0001F680-\U0001F6FF"
    "\U0001F700-\U0001F77F"
    "\U0001F780-\U0001F7FF"
    "\U0001F800-\U0001F8FF"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FAFF"
    "\U00002600-\U000026FF"
    "\U00002700-\U000027BF"
    "]"
)


@dataclass
class MessageEvent:
    chat_name: str
    sender: str
    content: str
    is_group: bool
    is_at_me: bool
    msg_type: str
    is_self: bool
    chat_type: Optional[str]
    raw_item: Optional[Any] = None


@dataclass
class ReconnectPolicy:
    max_retries: int
    base_delay_sec: float
    max_delay_sec: float


def load_config_py(path: str) -> Dict[str, Any]:
    spec = importlib.util.spec_from_file_location("user_config", path)
    if spec is None or spec.loader is None:
        raise ValueError("无法加载 config.py。")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if hasattr(module, "get_config"):
        config = module.get_config()
    elif hasattr(module, "CONFIG"):
        config = module.CONFIG
    elif hasattr(module, "config"):
        config = module.config
    else:
        raise ValueError("config.py 必须提供 CONFIG 或 get_config()。")
    if not isinstance(config, dict):
        raise ValueError("config.py 中的 CONFIG 必须是字典。")
    return config


def load_config(path: str) -> Dict[str, Any]:
    return load_config_py(path)


def as_int(value: Any, default: int, min_value: Optional[int] = None) -> int:
    try:
        val = int(value)
    except (TypeError, ValueError):
        return default
    if min_value is not None and val < min_value:
        return min_value
    return val


def as_float(value: Any, default: float, min_value: Optional[float] = None) -> float:
    try:
        val = float(value)
    except (TypeError, ValueError):
        return default
    if min_value is not None and val < min_value:
        return min_value
    return val


def as_optional_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def as_optional_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def normalize_system_prompt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple)):
        lines = [str(item).strip() for item in value if str(item).strip()]
        return "\n".join(lines)
    return str(value).strip()


def setup_logging(
    level: str,
    log_file: Optional[str] = None,
    max_bytes: int = 5 * 1024 * 1024,
    backup_count: int = 5,
) -> None:
    handlers: List[logging.Handler] = [logging.StreamHandler()]
    if log_file:
        log_path = os.path.abspath(log_file)
        log_dir = os.path.dirname(log_path)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        handlers.append(
            RotatingFileHandler(
                log_path,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
            )
        )
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=handlers,
        force=True,
    )


def get_file_mtime(path: str) -> Optional[float]:
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


async def reload_ai_module(ai_client: Optional[AIClient] = None) -> None:
    global ai_module, AIClient
    if ai_client and hasattr(ai_client, "close"):
        await ai_client.close()
    ai_module = importlib.reload(ai_module)
    AIClient = ai_module.AIClient


def compute_api_signature(api_cfg: Dict[str, Any]) -> str:
    try:
        return json.dumps(api_cfg, sort_keys=True, ensure_ascii=False)
    except Exception:
        return str(api_cfg)


def get_logging_settings(config: Dict[str, Any]) -> Tuple[str, Optional[str], int, int]:
    logging_cfg = config.get("logging", {})
    level = str(logging_cfg.get("level", "INFO"))
    log_file = logging_cfg.get("file")
    max_bytes = as_int(
        logging_cfg.get("max_bytes", 5 * 1024 * 1024),
        5 * 1024 * 1024,
        min_value=1024,
    )
    backup_count = as_int(logging_cfg.get("backup_count", 5), 5, min_value=0)
    return level, log_file, max_bytes, backup_count


def get_log_behavior(config: Dict[str, Any]) -> Tuple[bool, bool]:
    logging_cfg = config.get("logging", {})
    log_message_content = bool(logging_cfg.get("log_message_content", True))
    log_reply_content = bool(logging_cfg.get("log_reply_content", True))
    return log_message_content, log_reply_content


def get_reconnect_policy(bot_cfg: Dict[str, Any]) -> ReconnectPolicy:
    max_retries = as_int(bot_cfg.get("reconnect_max_retries", 3), 3, min_value=0)
    base_delay = as_float(
        bot_cfg.get("reconnect_backoff_sec", 2.0), 2.0, min_value=0.5
    )
    max_delay = as_float(
        bot_cfg.get("reconnect_max_delay_sec", 20.0), 20.0, min_value=1.0
    )
    return ReconnectPolicy(
        max_retries=max_retries,
        base_delay_sec=base_delay,
        max_delay_sec=max_delay,
    )


async def reconnect_wechat(reason: str, policy: ReconnectPolicy) -> Optional["WeChat"]:
    if WeChat is None:
        return None
    logging.warning("准备重连微信：%s", reason)
    for attempt in range(policy.max_retries + 1):
        try:
            wx = WeChat()
            logging.info("微信重连成功。")
            return wx
        except Exception as exc:
            wait = min(policy.max_delay_sec, policy.base_delay_sec * (1.5**attempt))
            logging.warning(
                "微信重连失败（第 %s 次）：%s，%s 秒后重试",
                attempt + 1,
                exc,
                round(wait, 2),
            )
            await asyncio.sleep(wait)
    logging.error("微信重连多次失败，请检查客户端状态。")
    return None


def apply_ai_runtime_settings(
    ai_client: AIClient,
    api_cfg: Dict[str, Any],
    bot_cfg: Dict[str, Any],
    allow_api_override: bool,
) -> None:
    if allow_api_override:
        ai_client.base_url = str(api_cfg.get("base_url") or ai_client.base_url).rstrip("/")
        ai_client.api_key = str(api_cfg.get("api_key") or ai_client.api_key)
        ai_client.model = str(api_cfg.get("model") or ai_client.model)
        if api_cfg.get("alias"):
            ai_client.model_alias = str(api_cfg.get("alias") or ai_client.model_alias)
    ai_client.timeout_sec = min(
        as_float(api_cfg.get("timeout_sec", ai_client.timeout_sec), ai_client.timeout_sec),
        10.0,
    )
    ai_client.max_retries = min(
        as_int(api_cfg.get("max_retries", ai_client.max_retries), ai_client.max_retries, min_value=0),
        2,
    )
    ai_client.temperature = api_cfg.get("temperature", ai_client.temperature)
    ai_client.max_tokens = api_cfg.get("max_tokens", ai_client.max_tokens)
    max_completion_tokens = api_cfg.get(
        "max_completion_tokens", ai_client.max_completion_tokens
    )
    ai_client.max_completion_tokens = as_optional_int(max_completion_tokens)
    ai_client.reasoning_effort = as_optional_str(
        api_cfg.get("reasoning_effort", ai_client.reasoning_effort)
    )
    ai_client.context_rounds = as_int(
        bot_cfg.get("context_rounds", ai_client.context_rounds),
        ai_client.context_rounds,
        min_value=0,
    )
    context_max_tokens = bot_cfg.get(
        "context_max_tokens", ai_client.context_max_tokens
    )
    ai_client.context_max_tokens = as_optional_int(context_max_tokens)
    ai_client.history_max_chats = as_int(
        bot_cfg.get("history_max_chats", ai_client.history_max_chats),
        ai_client.history_max_chats,
        min_value=1,
    )
    history_ttl = bot_cfg.get("history_ttl_sec", ai_client.history_ttl_sec)
    if history_ttl is None:
        ai_client.history_ttl_sec = None
    else:
        ai_client.history_ttl_sec = as_float(history_ttl, 0.0, min_value=0.0) or None
    ai_client.system_prompt = normalize_system_prompt(
        bot_cfg.get("system_prompt", ai_client.system_prompt)
    )


def iter_items(obj: Any) -> Iterable[Any]:
    if isinstance(obj, (list, tuple)):
        return obj
    return [obj]


def split_group_message(text: str) -> Tuple[Optional[str], str]:
    # 常见群聊格式是“发送者:\\n消息”或“发送者: 消息”。
    for sep in (":\n", "：\n", ": ", "： "):
        if sep in text:
            head, tail = text.split(sep, 1)
            if head.strip() and tail.strip():
                return head.strip(), tail.strip()
    return None, text


def is_text_message(msg_type: Optional[str], content: str) -> bool:
    if not content or not isinstance(content, str):
        return False
    if msg_type is None:
        return True
    text_type = str(msg_type).lower()
    non_text_markers = (
        "image",
        "pic",
        "voice",
        "audio",
        "video",
        "file",
        "gif",
        "emoji",
        "system",
        "location",
        "link",
        "merge",
        "card",
        "note",
        "tickle",
    )
    if any(marker in text_type for marker in non_text_markers):
        return False
    return True


def is_voice_message(msg_type: Optional[str]) -> bool:
    if msg_type is None:
        return False
    text_type = str(msg_type).lower()
    return any(marker in text_type for marker in ("voice", "audio"))


def parse_voice_to_text_result(result: Any) -> Tuple[Optional[str], Optional[str]]:
    if result is None:
        return None, "empty"
    if isinstance(result, dict):
        message = result.get("message") or result.get("error") or ""
        message = str(message).strip() if message else ""
        return None, message or "unknown"
    text = str(result).strip()
    if not text:
        return None, "empty"
    return text, None


def is_at_me(text: str, self_name: str) -> bool:
    if not self_name:
        return False
    markers = [f"@{self_name}\u2005", f"@{self_name} ", f"@{self_name}"]
    return any(marker in text for marker in markers)


def strip_at_text(text: str, self_name: str) -> str:
    if not self_name:
        return text
    markers = [f"@{self_name}\u2005", f"@{self_name} ", f"@{self_name}"]
    for marker in markers:
        if text.startswith(marker):
            return text[len(marker) :].strip()
    return text


def build_reply_suffix(template: str, model: str, alias: str) -> str:
    try:
        return template.format(model=model, alias=alias)
    except Exception:
        logging.warning("reply_suffix 模板错误，已回退默认值。")
        return DEFAULT_SUFFIX.format(alias=alias or model, model=model)


def get_model_alias(ai_client: AIClient) -> str:
    alias = getattr(ai_client, "model_alias", "")
    return alias or ai_client.model


def resolve_system_prompt(event: MessageEvent, bot_cfg: Dict[str, Any]) -> str:
    base_prompt = normalize_system_prompt(bot_cfg.get("system_prompt", ""))
    overrides = bot_cfg.get("system_prompt_overrides")
    if isinstance(overrides, dict):
        override = overrides.get(event.chat_name)
        if override:
            return normalize_system_prompt(override)
    return base_prompt


def format_user_text(event: MessageEvent, bot_cfg: Dict[str, Any]) -> str:
    if event.is_group and bot_cfg.get("group_include_sender", True) and event.sender:
        return f"{event.sender}: {event.content}"
    return event.content


def build_seed_messages(
    raw_messages: Iterable[Any],
    is_group: bool,
    self_name: str,
    group_include_sender: bool,
) -> List[dict]:
    messages: List[dict] = []
    for msg in raw_messages:
        if not (hasattr(msg, "content") and hasattr(msg, "type")):
            continue
        attr = getattr(msg, "attr", None)
        if attr not in ("friend", "self"):
            continue
        content = getattr(msg, "content", "") or ""
        msg_type = getattr(msg, "type", None)
        if not is_text_message(msg_type, content):
            continue
        content = str(content).strip()
        if not content:
            continue
        if is_group:
            content = strip_at_text(content, self_name)
            if group_include_sender and attr == "friend":
                sender = (
                    getattr(msg, "sender", None)
                    or getattr(msg, "sender_remark", None)
                    or ""
                )
                sender = str(sender).strip()
                if sender:
                    content = f"{sender}: {content}"
        role = "assistant" if attr == "self" else "user"
        messages.append({"role": role, "content": content})
    return messages


def trim_seed_messages(
    messages: List[dict],
    limit: int,
    current_user_text: Optional[str],
) -> List[dict]:
    if not messages:
        return []
    trimmed = messages
    current_text = str(current_user_text or "").strip()
    if (
        current_text
        and trimmed
        and trimmed[-1].get("role") == "user"
        and trimmed[-1].get("content") == current_text
    ):
        trimmed = trimmed[:-1]
    if limit > 0 and len(trimmed) > limit:
        trimmed = trimmed[-limit:]
    return trimmed


def fetch_recent_chat_messages(
    wx: "WeChat",
    chat_name: str,
    bot_cfg: Dict[str, Any],
    load_more_count: int,
    load_more_interval_sec: float,
) -> List[Any]:
    if not chat_name:
        return []
    result = wx.ChatWith(
        chat_name,
        exact=bool(bot_cfg.get("send_exact_match", False)),
    )
    if not result:
        return []
    for _ in range(load_more_count):
        if not wx.LoadMoreMessage(interval=load_more_interval_sec):
            break
    return wx.GetAllMessage() or []


def build_history_context_text(messages: List[dict]) -> str:
    if not messages:
        return ""
    lines: List[str] = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role = str(msg.get("role", "") or "").strip()
        content = str(msg.get("content", "") or "").strip()
        if not role or not content:
            continue
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def truncate_text(text: str, max_len: int = 120) -> str:
    if text is None:
        return ""
    text = str(text).replace("\n", " ").strip()
    return text if len(text) <= max_len else text[:max_len] + "..."


def format_log_text(text: str, enabled: bool, max_len: int = 120) -> str:
    if not enabled:
        return "[hidden]"
    return truncate_text(text, max_len=max_len)


def estimate_exchange_tokens(
    ai_client: AIClient, user_text: str, reply_text: str
) -> Tuple[int, int, int]:
    user_tokens = ai_client._estimate_message_tokens(
        {"role": "user", "content": user_text or ""}
    )
    reply_tokens = ai_client._estimate_message_tokens(
        {"role": "assistant", "content": reply_text or ""}
    )
    return user_tokens, reply_tokens, user_tokens + reply_tokens


def sanitize_reply_text(
    text: str, policy: str, replacements: Optional[Dict[str, str]] = None
) -> str:
    if not text:
        return text
    mode = (policy or "").strip().lower()
    if mode in ("keep", "raw", "none"):
        return text

    if mode in ("strip", "remove"):
        text = text.replace("\uFE0F", "").replace("\uFE0E", "").replace("\u200D", "")
        return EMOJI_PATTERN.sub("", text)

    emoji_map = dict(EMOJI_REPLACEMENTS)
    custom_replacements: Dict[str, str] = {}
    if isinstance(replacements, dict):
        for key, value in replacements.items():
            if isinstance(key, str) and isinstance(value, str) and key:
                emoji_map[key] = value
                custom_replacements[key] = value

    if custom_replacements:
        for key in sorted(custom_replacements, key=len, reverse=True):
            text = text.replace(key, custom_replacements[key])

    if mode in ("mixed", "wechat_mixed", "wechat-keep"):
        text = text.replace("\uFE0F", "").replace("\uFE0E", "").replace("\u200D", "")

        def repl_mixed(match: re.Match) -> str:
            ch = match.group(0)
            return emoji_map.get(ch, ch)

        return EMOJI_PATTERN.sub(repl_mixed, text)

    text = text.replace("\uFE0F", "").replace("\uFE0E", "").replace("\u200D", "")

    def repl_wechat(match: re.Match) -> str:
        ch = match.group(0)
        return emoji_map.get(ch, EMOJI_PLACEHOLDER)

    return EMOJI_PATTERN.sub(repl_wechat, text)


def split_reply_chunks(text: str, max_len: int) -> List[str]:
    if not text:
        return []
    if max_len <= 0 or len(text) <= max_len:
        if not text.strip():
            return []
        return [text.rstrip()]
    chunks: List[str] = []
    start = 0
    text_len = len(text)
    while start < text_len:
        end = min(text_len, start + max_len)
        split_at = None
        for idx in range(end - 1, start, -1):
            if text[idx] in STREAM_PUNCTUATION:
                split_at = idx + 1
                break
        if split_at is None or split_at <= start:
            split_at = end
        chunk = text[start:split_at].rstrip()
        if chunk.strip():
            chunks.append(chunk)
        start = split_at
    return chunks


def get_setting(preset: Dict[str, Any], api_cfg: Dict[str, Any], key: str, default: Any) -> Any:
    if key in preset:
        return preset.get(key)
    return api_cfg.get(key, default)


def is_placeholder_key(api_key: str) -> bool:
    key = (api_key or "").strip()
    if not key:
        return True
    if set(key) == {"*"}:
        return True
    upper = key.upper()
    if upper.startswith(("YOUR_", "YOUR-", "YOUR ")):
        return True
    if upper in ("YOURAPIKEY", "YOUR_API_KEY", "API_KEY"):
        return True
    return False


def build_api_candidates(api_cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    presets = api_cfg.get("presets") or []
    candidates: List[Dict[str, Any]] = []

    if isinstance(presets, list) and presets:
        active_name = api_cfg.get("active_preset")
        ordered = presets
        if active_name:
            preferred = [
                p for p in presets if isinstance(p, dict) and p.get("name") == active_name
            ]
            others = [
                p for p in presets if not (isinstance(p, dict) and p.get("name") == active_name)
            ]
            ordered = preferred + others

        for idx, preset in enumerate(ordered):
            if not isinstance(preset, dict):
                continue
            name = preset.get("name") or f"preset-{idx + 1}"
            candidates.append(
                {
                    "name": name,
                    "base_url": get_setting(preset, api_cfg, "base_url", ""),
                    "api_key": get_setting(preset, api_cfg, "api_key", ""),
                    "model": get_setting(preset, api_cfg, "model", ""),
                    "alias": get_setting(preset, api_cfg, "alias", ""),
                    "timeout_sec": get_setting(preset, api_cfg, "timeout_sec", 30),
                    "max_retries": get_setting(preset, api_cfg, "max_retries", 2),
                    "temperature": get_setting(preset, api_cfg, "temperature", None),
                    "max_tokens": get_setting(preset, api_cfg, "max_tokens", None),
                    "max_completion_tokens": get_setting(
                        preset, api_cfg, "max_completion_tokens", None
                    ),
                    "reasoning_effort": get_setting(
                        preset, api_cfg, "reasoning_effort", None
                    ),
                    "allow_empty_key": get_setting(preset, api_cfg, "allow_empty_key", False),
                }
            )
        return candidates

    if any(api_cfg.get(key) for key in ("base_url", "model", "api_key")):
        candidates.append(
            {
                "name": api_cfg.get("active_preset") or "default",
                "base_url": api_cfg.get("base_url", ""),
                "api_key": api_cfg.get("api_key", ""),
                "model": api_cfg.get("model", ""),
                "alias": api_cfg.get("alias", ""),
                "timeout_sec": api_cfg.get("timeout_sec", 30),
                "max_retries": api_cfg.get("max_retries", 2),
                "temperature": api_cfg.get("temperature"),
                "max_tokens": api_cfg.get("max_tokens"),
                "max_completion_tokens": api_cfg.get("max_completion_tokens"),
                "reasoning_effort": api_cfg.get("reasoning_effort"),
                "allow_empty_key": api_cfg.get("allow_empty_key", False),
            }
        )
    return candidates


def build_ai_client(settings: Dict[str, Any], bot_cfg: Dict[str, Any]) -> AIClient:
    history_ttl_raw = bot_cfg.get("history_ttl_sec", 24 * 60 * 60)
    if history_ttl_raw is None:
        history_ttl_sec = None
    else:
        history_ttl_sec = as_float(
            history_ttl_raw,
            24 * 60 * 60,
            min_value=0.0,
        ) or None

    client = AIClient(
        base_url=str(settings.get("base_url") or "").strip(),
        api_key=str(settings.get("api_key") or "").strip(),
        model=str(settings.get("model") or "").strip(),
        timeout_sec=as_float(
            settings.get("timeout_sec", 10),
            10.0,
            min_value=0.0,
        ),
        max_retries=as_int(settings.get("max_retries", 2), 2, min_value=0),
        context_rounds=as_int(bot_cfg.get("context_rounds", 5), 5, min_value=0),
        context_max_tokens=as_optional_int(bot_cfg.get("context_max_tokens")),
        system_prompt=normalize_system_prompt(bot_cfg.get("system_prompt", "")),
        temperature=settings.get("temperature"),
        max_tokens=settings.get("max_tokens"),
        max_completion_tokens=as_optional_int(
            settings.get("max_completion_tokens")
        ),
        reasoning_effort=as_optional_str(settings.get("reasoning_effort")),
        model_alias=settings.get("alias"),
        history_max_chats=as_int(
            bot_cfg.get("history_max_chats", 200), 200, min_value=1
        ),
        history_ttl_sec=history_ttl_sec,
    )
    client.model_alias = str(settings.get("alias") or "").strip()
    return client


async def select_ai_client(
    api_cfg: Dict[str, Any], bot_cfg: Dict[str, Any]
) -> Tuple[Optional[AIClient], Optional[str]]:
    candidates = build_api_candidates(api_cfg)
    if not candidates:
        logging.error("未找到可用的 API 配置。")
        return None, None

    for settings in candidates:
        name = settings.get("name", "preset")
        base_url = str(settings.get("base_url") or "").strip()
        model = str(settings.get("model") or "").strip()
        api_key = settings.get("api_key")
        if api_key is None:
            api_key = ""
        else:
            api_key = str(api_key).strip()
        allow_empty_key = bool(settings.get("allow_empty_key", False))

        if not base_url or not model:
            logging.warning("跳过预设 %s：缺少 base_url 或 model", name)
            continue
        if is_placeholder_key(api_key) and not allow_empty_key:
            logging.warning("跳过预设 %s：api_key 未配置或为占位符", name)
            continue

        settings = dict(settings)
        settings["base_url"] = base_url
        settings["model"] = model
        settings["api_key"] = api_key

        client = build_ai_client(settings, bot_cfg)
        logging.info("正在探测预设：%s", name)
        if await client.probe():
            logging.info("已选择预设：%s", name)
            return client, name
        logging.warning("预设 %s 不可用，尝试下一个...", name)

    logging.error("没有可用的预设，请检查 API 配置。")
    return None, None


def normalize_new_messages(raw: Any, self_name: str) -> List[MessageEvent]:
    events: List[MessageEvent] = []
    if not raw:
        return events

    # 微信自动化库返回格式：{"会话名": "...", "会话类型": "...", "消息": [...]}
    if isinstance(raw, dict) and "chat_name" in raw and "msg" in raw:
        chat_name = str(raw.get("chat_name", "")).strip()
        chat_type = str(raw.get("chat_type", "")).strip()
        for item in iter_items(raw.get("msg", [])):
            event = normalize_message_item(chat_name, item, self_name, chat_type)
            if event:
                events.append(event)
        return events

    # 兼容旧格式：{会话名: [消息1, 消息2, ...]}
    if isinstance(raw, dict):
        for chat_name, items in raw.items():
            chat_name = str(chat_name).strip()
            for item in iter_items(items):
                event = normalize_message_item(chat_name, item, self_name, None)
                if event:
                    events.append(event)
        return events

    # 部分版本会返回消息字典列表。
    if isinstance(raw, list):
        for item in raw:
            event = normalize_message_item_from_list(item, self_name)
            if event:
                events.append(event)
        return events

    logging.debug("未知消息结构：%s", type(raw))
    return events


def normalize_message_item(
    chat_name: str, item: Any, self_name: str, chat_type: Optional[str]
) -> Optional[MessageEvent]:
    chat_type_norm = str(chat_type).lower() if chat_type else None
    is_group = chat_type_norm == "group"
    is_self = False
    chat_name = str(chat_name).strip()

    if hasattr(item, "content") and hasattr(item, "type"):
        content = getattr(item, "content", "") or ""
        sender = (
            getattr(item, "sender", None)
            or getattr(item, "sender_remark", None)
            or chat_name
        )
        msg_type = getattr(item, "type", None)
        attr = getattr(item, "attr", None)
        if (not content) and hasattr(item, "info"):
            info = getattr(item, "info", None)
            if isinstance(info, dict):
                content = info.get("content", content) or content
                msg_type = info.get("type", msg_type)
                attr = info.get("attr", attr)
        is_self = attr == "self"
        if attr in ("system", "time", "tickle"):
            return None
    elif isinstance(item, dict):
        content = item.get("msg") or item.get("content") or item.get("text") or ""
        sender = item.get("sender") or item.get("from") or item.get("nickname") or chat_name
        msg_type = item.get("type") or item.get("msg_type") or "text"
        is_group = is_group or bool(item.get("is_group") or item.get("group"))
        is_self = bool(item.get("is_self"))
    elif isinstance(item, str):
        content = item
        sender = chat_name
        msg_type = "text"
        is_group = is_group or False
    else:
        return None

    content = content.strip()
    if is_voice_message(msg_type):
        if not content:
            content = VOICE_PLACEHOLDER
    elif not is_text_message(msg_type, content):
        return None

    if is_group and (not sender or sender == chat_name):
        sender_from_text, clean = split_group_message(content)
        if sender_from_text:
            sender = sender_from_text
            content = clean

    at_me = is_group and is_at_me(content, self_name)
    if is_group:
        content = strip_at_text(content, self_name)

    return MessageEvent(
        chat_name=chat_name,
        sender=sender,
        content=content,
        is_group=is_group,
        is_at_me=at_me,
        msg_type=str(msg_type),
        is_self=is_self,
        chat_type=chat_type_norm,
        raw_item=item,
    )


def normalize_message_item_from_list(item: Any, self_name: str) -> Optional[MessageEvent]:
    # 列表结构的兜底解析。
    if not isinstance(item, dict):
        return None

    chat_name = (
        item.get("chat")
        or item.get("who")
        or item.get("group")
        or item.get("from")
        or item.get("sender")
        or ""
    )
    if not chat_name:
        return None

    return normalize_message_item(chat_name, item, self_name, item.get("chat_type"))


def should_reply(event: MessageEvent, config: Dict[str, Any]) -> bool:
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


def parse_send_result(result: Any) -> Tuple[bool, Optional[str]]:
    if isinstance(result, dict):
        if result.get("success") is False:
            return False, result.get("message") or result.get("error")
        if "code" in result and result.get("code") not in (0, "0", None):
            return False, result.get("message") or result.get("error")
        return True, result.get("message")
    if result:
        return True, None
    return False, "SendMsg returned falsy"


async def transcribe_voice_message(
    event: MessageEvent,
    bot_cfg: Dict[str, Any],
    wx_lock: asyncio.Lock,
) -> Tuple[Optional[str], Optional[str]]:
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


def get_random_delay_range(
    bot_cfg: Dict[str, Any], default_range: Tuple[float, float]
) -> Tuple[float, float]:
    value = bot_cfg.get("random_delay_range_sec")
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        low = as_float(value[0], default_range[0], min_value=0.0)
        high = as_float(value[1], default_range[1], min_value=0.0)
        if high < low:
            low, high = high, low
        return low, high
    return default_range


async def maybe_sleep_random(delay_range: Tuple[float, float]) -> None:
    if not delay_range:
        return
    low, high = delay_range
    if high <= 0:
        return
    await asyncio.sleep(random.uniform(low, high))


def send_message(
    wx: "WeChat", chat_name: str, text: str, bot_cfg: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    result = wx.SendMsg(
        text,
        chat_name,
        exact=bool(bot_cfg.get("send_exact_match", False)),
    )
    ok, err_msg = parse_send_result(result)
    if not ok and bot_cfg.get("send_fallback_current_chat", True):
        logging.warning(
            "发送失败，尝试当前聊天窗口重试 | 会话=%s",
            chat_name,
        )
        result = wx.SendMsg(text)
        ok, err_msg = parse_send_result(result)
    return ok, err_msg


async def send_reply_chunks(
    wx: "WeChat",
    chat_name: str,
    text: str,
    bot_cfg: Dict[str, Any],
    chunk_size: int,
    chunk_delay_sec: float,
    min_reply_interval: float,
    last_reply_ts: Dict[str, float],
    wx_lock: asyncio.Lock,
) -> Tuple[bool, Optional[str]]:
    chunks = split_reply_chunks(text, chunk_size)
    for idx, chunk in enumerate(chunks):
        if not chunk:
            continue
        async with wx_lock:
            elapsed = time.time() - last_reply_ts.get("ts", 0.0)
            if elapsed < min_reply_interval:
                await asyncio.sleep(min_reply_interval - elapsed)
            ok, err_msg = await asyncio.to_thread(
                send_message, wx, chat_name, chunk, bot_cfg
            )
            if not ok:
                return False, err_msg
            last_reply_ts["ts"] = time.time()
        if idx < len(chunks) - 1 and chunk_delay_sec > 0:
            await asyncio.sleep(chunk_delay_sec)
    return True, None


async def main() -> None:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(base_dir, "config.py")
    if not os.path.exists(config_path):
        logging.error("未找到 config.py，请检查路径。")
        return
    setup_logging("INFO")
    try:
        config = load_config(config_path)
    except (FileNotFoundError, SyntaxError, ValueError) as exc:
        logging.error("加载 config.py 失败：%s", exc)
        return

    log_level, log_file, log_max_bytes, log_backup_count = get_logging_settings(config)
    setup_logging(log_level, log_file, log_max_bytes, log_backup_count)
    log_message_content, log_reply_content = get_log_behavior(config)

    if WeChat is None:
        logging.error("导入 wxauto 失败，请检查依赖安装。")
        logging.error("导入错误：%s", _WXAUTO_IMPORT_ERROR)
        return

    bot_cfg = config.get("bot", {})
    api_cfg = config.get("api", {})
    memory_context_limit = as_int(
        bot_cfg.get("memory_context_limit", 20), 20, min_value=0
    )
    memory_seed_on_first_reply = bool(
        bot_cfg.get("memory_seed_on_first_reply", True)
    )
    memory_seed_limit = as_int(
        bot_cfg.get("memory_seed_limit", 50), 50, min_value=0
    )
    memory_seed_load_more = as_int(
        bot_cfg.get("memory_seed_load_more", 0), 0, min_value=0
    )
    memory_seed_load_more_interval_sec = as_float(
        bot_cfg.get("memory_seed_load_more_interval_sec", 0.3),
        0.3,
        min_value=0.0,
    )
    memory_seed_group = bool(bot_cfg.get("memory_seed_group", False))
    memory_db_path = bot_cfg.get("memory_db_path") or os.path.join(
        base_dir, "chat_history.db"
    )
    memory: Optional[MemoryManager] = None
    try:
        memory = MemoryManager(str(memory_db_path))
    except Exception as exc:
        logging.warning("memory init failed: %s", exc)
    reconnect_policy = get_reconnect_policy(bot_cfg)
    keepalive_idle_sec = as_float(
        bot_cfg.get("keepalive_idle_sec", 180.0), 180.0, min_value=0.0
    )

    ai_client, preset_name = await select_ai_client(api_cfg, bot_cfg)
    if ai_client is None:
        return
    if preset_name:
        logging.info(
            "当前预设为%s，模型 %s，别名 %s。",
            preset_name,
            ai_client.model,
            get_model_alias(ai_client),
        )

    api_signature = compute_api_signature(api_cfg)
    config_mtime = get_file_mtime(config_path)
    config_check_ts = 0.0
    config_reload_sec = as_float(
        bot_cfg.get("config_reload_sec", 2.0), 2.0, min_value=0.0
    )
    reload_ai_client_on_change = bool(
        bot_cfg.get("reload_ai_client_on_change", True)
    )
    reload_ai_client_module = bool(
        bot_cfg.get("reload_ai_client_module", False)
    )
    ai_module_path = os.path.join(base_dir, "ai_client.py")
    ai_module_mtime = get_file_mtime(ai_module_path)

    poll_interval_min = as_float(
        bot_cfg.get("poll_interval_min_sec", 0.05), 0.05, min_value=0.01
    )
    poll_interval_max = as_float(
        bot_cfg.get("poll_interval_max_sec", 1.0), 1.0, min_value=poll_interval_min
    )
    poll_interval = as_float(
        bot_cfg.get("poll_interval_sec", poll_interval_min),
        poll_interval_min,
        min_value=poll_interval_min,
    )
    poll_backoff = as_float(
        bot_cfg.get("poll_interval_backoff_factor", 1.2), 1.2, min_value=1.0
    )
    min_reply_interval = as_float(
        bot_cfg.get("min_reply_interval_sec", 0.2), 0.2, min_value=0.0
    )
    reply_chunk_size = as_int(
        bot_cfg.get("reply_chunk_size", 500), 500, min_value=1
    )
    reply_chunk_delay_sec = as_float(
        bot_cfg.get("reply_chunk_delay_sec", 0.0), 0.0, min_value=0.0
    )
    stream_reply = bool(bot_cfg.get("stream_reply", False))
    stream_buffer_chars = as_int(
        bot_cfg.get("stream_buffer_chars", 40), 40, min_value=1
    )
    stream_chunk_max_chars = as_int(
        bot_cfg.get("stream_chunk_max_chars", reply_chunk_size),
        reply_chunk_size,
        min_value=1,
    )
    history_log_interval_sec = as_float(
        bot_cfg.get("history_log_interval_sec", 300.0), 300.0, min_value=0.0
    )
    next_history_log_ts = (
        time.time() + history_log_interval_sec
        if history_log_interval_sec > 0
        else 0.0
    )
    random_delay_range = get_random_delay_range(bot_cfg, (0.0, 0.0))
    merge_user_messages_sec = as_float(
        bot_cfg.get("merge_user_messages_sec", 0.0), 0.0, min_value=0.0
    )
    merge_user_messages_max_wait_sec = as_float(
        bot_cfg.get("merge_user_messages_max_wait_sec", 0.0), 0.0, min_value=0.0
    )
    max_concurrency = as_int(bot_cfg.get("max_concurrency", 5), 5, min_value=1)

    logging.info("启动配置如下...")
    logging.info("白名单启用：%s", bot_cfg.get("whitelist_enabled", False))
    logging.info("群聊仅在被 @ 时回复：%s", bot_cfg.get("group_reply_only_when_at", True))
    logging.info("群聊回复包含发送者：%s", bot_cfg.get("group_include_sender", True))
    if bot_cfg.get("group_reply_only_when_at", False) and not bot_cfg.get("self_name"):
        logging.warning("self_name 未设置，@ 检测可能不准确。")

    wx = await reconnect_wechat("初始化", reconnect_policy)
    if wx is None:
        logging.error("微信连接失败。")
        logging.error("wxauto 仅支持 3.9.x，不支持 4.x。")
        logging.error("请到 https://pc.weixin.qq.com 下载 3.9.x。")
        return
    last_reply_ts: Dict[str, float] = {"ts": 0.0}
    last_poll_ok_ts = time.time()
    wx_lock = asyncio.Lock()
    sem = asyncio.Semaphore(max_concurrency)
    pending_tasks: set = set()
    pending_merge_messages: Dict[str, List[str]] = {}
    pending_merge_events: Dict[str, MessageEvent] = {}
    pending_merge_tasks: Dict[str, asyncio.Task] = {}
    pending_merge_first_ts: Dict[str, float] = {}
    pending_merge_lock = asyncio.Lock()

    async def handle_event(
        event: MessageEvent,
        user_text_override: Optional[str] = None,
        message_log_override: Optional[str] = None,
    ) -> None:
        async with sem:
            reply_preview = ""
            try:
                log_text = (
                    message_log_override
                    if message_log_override is not None
                    else event.content
                )
                message_log = format_log_text(log_text, log_message_content)
                logging.debug(
                    "收到消息 | 会话=%s | 发送者=%s | 群聊=%s | 自己=%s | 类型=%s | 内容=%s",
                    event.chat_name,
                    event.sender,
                    event.is_group,
                    event.is_self,
                    event.msg_type,
                    message_log,
                )
                if not should_reply(event, config):
                    return

                emoji_policy = str(bot_cfg.get("emoji_policy", "wechat"))
                emoji_replacements = bot_cfg.get("emoji_replacements")
                if is_voice_message(event.msg_type) and user_text_override is None:
                    voice_text, voice_err = await transcribe_voice_message(
                        event, bot_cfg, wx_lock
                    )
                    if not voice_text:
                        fail_reply = str(
                            bot_cfg.get("voice_to_text_fail_reply", "")
                        ).strip()
                        if fail_reply:
                            await maybe_sleep_random(random_delay_range)
                            sanitized_fail = sanitize_reply_text(
                                fail_reply, emoji_policy, emoji_replacements
                            )
                            ok, err_msg = await send_reply_chunks(
                                wx,
                                event.chat_name,
                                sanitized_fail,
                                bot_cfg,
                                reply_chunk_size,
                                reply_chunk_delay_sec,
                                min_reply_interval,
                                last_reply_ts,
                                wx_lock,
                            )
                            if not ok:
                                logging.error(
                                    "发送失败 | 会话=%s | 错误=%s",
                                    event.chat_name,
                                    err_msg or "unknown",
                                )
                        logging.warning(
                            "语音转文字失败 | 会话=%s | 发送者=%s | 原因=%s",
                            event.chat_name,
                            event.sender,
                            voice_err or "unknown",
                        )
                        return
                    event.content = voice_text
                    if message_log_override is None:
                        message_log = format_log_text(
                            event.content, log_message_content
                        )

                user_text = (
                    user_text_override
                    if user_text_override is not None
                    else format_user_text(event, bot_cfg)
                )
                chat_id = (
                    f"group:{event.chat_name}"
                    if event.is_group
                    else f"friend:{event.chat_name}"
                )
                recent_context: List[dict] = []
                if (
                    memory
                    and user_text.strip()
                    and memory_seed_on_first_reply
                    and memory_seed_limit > 0
                    and (not event.is_group or memory_seed_group)
                ):
                    has_history = False
                    try:
                        has_history = memory.has_messages(chat_id)
                    except Exception as exc:
                        logging.warning("memory check failed: %s", exc)
                        has_history = True
                    if not has_history:
                        try:
                            async with wx_lock:
                                raw_history = await asyncio.to_thread(
                                    fetch_recent_chat_messages,
                                    wx,
                                    event.chat_name,
                                    bot_cfg,
                                    memory_seed_load_more,
                                    memory_seed_load_more_interval_sec,
                                )
                            seed_messages = build_seed_messages(
                                raw_history,
                                event.is_group,
                                str(bot_cfg.get("self_name", "") or ""),
                                bool(
                                    bot_cfg.get("group_include_sender", True)
                                ),
                            )
                            seed_messages = trim_seed_messages(
                                seed_messages, memory_seed_limit, user_text
                            )
                            if seed_messages:
                                inserted = memory.add_messages(
                                    chat_id, seed_messages
                                )
                                logging.info(
                                    "已录入历史条数=%s | 会话=%s",
                                    inserted,
                                    event.chat_name,
                                )
                        except Exception as exc:
                            logging.warning("memory seed failed: %s", exc)
                if memory and user_text.strip():
                    try:
                        memory.add_message(chat_id, "user", user_text)
                    except Exception as exc:
                        logging.warning("memory write failed: %s", exc)
                if memory and memory_context_limit > 0:
                    try:
                        recent_context = memory.get_recent_context(
                            chat_id, limit=memory_context_limit
                        )
                    except Exception as exc:
                        logging.warning("memory load failed: %s", exc)
                memory_context = recent_context
                history_context_text = build_history_context_text(recent_context)
                system_prompt = resolve_system_prompt(event, bot_cfg)
                if "{history_context}" in system_prompt:
                    system_prompt = system_prompt.replace(
                        "{history_context}", history_context_text
                    )
                    memory_context = []
                reply_suffix_template = bot_cfg.get("reply_suffix")
                reply_suffix = ""
                if reply_suffix_template is not None:
                    reply_suffix_template = str(reply_suffix_template)
                    if reply_suffix_template:
                        reply_suffix = build_reply_suffix(
                            reply_suffix_template,
                            ai_client.model,
                            get_model_alias(ai_client),
                        )
                reply_tokens_text = ""

                used_stream = False
                stream_sent_any = False

                if stream_reply:
                    stream_iter = await ai_client.generate_reply_stream(
                        chat_id,
                        user_text,
                        system_prompt,
                        memory_context=memory_context,
                    )
                    if stream_iter:
                        used_stream = True
                        buffer = ""
                        full_reply = ""
                        first_send = True
                        pending_chunk = ""
                        async for piece in stream_iter:
                            full_reply += piece
                            buffer += piece
                            should_flush = False
                            if len(buffer) >= stream_chunk_max_chars:
                                should_flush = True
                            elif (
                                len(buffer) >= stream_buffer_chars
                                and buffer[-1] in STREAM_PUNCTUATION
                            ):
                                should_flush = True
                            if should_flush:
                                if reply_suffix:
                                    if pending_chunk.strip():
                                        if first_send:
                                            await maybe_sleep_random(
                                                random_delay_range
                                            )
                                            first_send = False
                                        sanitized = sanitize_reply_text(
                                            pending_chunk,
                                            emoji_policy,
                                            emoji_replacements,
                                        )
                                        ok, err_msg = await send_reply_chunks(
                                            wx,
                                            event.chat_name,
                                            sanitized,
                                            bot_cfg,
                                            stream_chunk_max_chars,
                                            reply_chunk_delay_sec,
                                            min_reply_interval,
                                            last_reply_ts,
                                            wx_lock,
                                        )
                                        stream_sent_any = stream_sent_any or ok
                                        if not ok:
                                            logging.error(
                                                "发送失败 | 会话=%s | 错误=%s",
                                                event.chat_name,
                                                err_msg or "unknown",
                                            )
                                            return
                                    pending_chunk = buffer
                                else:
                                    if first_send:
                                        await maybe_sleep_random(
                                            random_delay_range
                                        )
                                        first_send = False
                                    sanitized = sanitize_reply_text(
                                        buffer, emoji_policy, emoji_replacements
                                    )
                                    ok, err_msg = await send_reply_chunks(
                                        wx,
                                        event.chat_name,
                                        sanitized,
                                        bot_cfg,
                                        stream_chunk_max_chars,
                                        reply_chunk_delay_sec,
                                        min_reply_interval,
                                        last_reply_ts,
                                        wx_lock,
                                    )
                                    stream_sent_any = stream_sent_any or ok
                                    if not ok:
                                        logging.error(
                                            "发送失败 | 会话=%s | 错误=%s",
                                            event.chat_name,
                                            err_msg or "unknown",
                                        )
                                        return
                                buffer = ""
                        if full_reply:
                            tail = buffer
                            if tail.strip():
                                if reply_suffix:
                                    if pending_chunk.strip():
                                        if first_send:
                                            await maybe_sleep_random(
                                                random_delay_range
                                            )
                                            first_send = False
                                        sanitized = sanitize_reply_text(
                                            pending_chunk,
                                            emoji_policy,
                                            emoji_replacements,
                                        )
                                        ok, err_msg = await send_reply_chunks(
                                            wx,
                                            event.chat_name,
                                            sanitized,
                                            bot_cfg,
                                            stream_chunk_max_chars,
                                            reply_chunk_delay_sec,
                                            min_reply_interval,
                                            last_reply_ts,
                                            wx_lock,
                                        )
                                        stream_sent_any = stream_sent_any or ok
                                        if not ok:
                                            logging.error(
                                                "发送失败 | 会话=%s | 错误=%s",
                                                event.chat_name,
                                                err_msg or "unknown",
                                            )
                                            return
                                    pending_chunk = tail
                                else:
                                    if first_send:
                                        await maybe_sleep_random(
                                            random_delay_range
                                        )
                                        first_send = False
                                    sanitized_tail = sanitize_reply_text(
                                        tail, emoji_policy, emoji_replacements
                                    )
                                    ok, err_msg = await send_reply_chunks(
                                        wx,
                                        event.chat_name,
                                        sanitized_tail,
                                        bot_cfg,
                                        stream_chunk_max_chars,
                                        reply_chunk_delay_sec,
                                        min_reply_interval,
                                        last_reply_ts,
                                        wx_lock,
                                    )
                                    stream_sent_any = stream_sent_any or ok
                                    if not ok:
                                        logging.error(
                                            "发送失败 | 会话=%s | 错误=%s",
                                            event.chat_name,
                                            err_msg or "unknown",
                                        )
                                        return
                            if reply_suffix:
                                final_text = (
                                    pending_chunk + reply_suffix
                                    if pending_chunk
                                    else reply_suffix
                                )
                                if final_text.strip():
                                    if first_send:
                                        await maybe_sleep_random(
                                            random_delay_range
                                        )
                                        first_send = False
                                    sanitized_final = sanitize_reply_text(
                                        final_text,
                                        emoji_policy,
                                        emoji_replacements,
                                    )
                                    ok, err_msg = await send_reply_chunks(
                                        wx,
                                        event.chat_name,
                                        sanitized_final,
                                        bot_cfg,
                                        stream_chunk_max_chars,
                                        reply_chunk_delay_sec,
                                        min_reply_interval,
                                        last_reply_ts,
                                        wx_lock,
                                    )
                                    stream_sent_any = stream_sent_any or ok
                                    if not ok:
                                        logging.error(
                                            "发送失败 | 会话=%s | 错误=%s",
                                            event.chat_name,
                                            err_msg or "unknown",
                                        )
                                        return
                            reply_preview = sanitize_reply_text(
                                f"{full_reply}{reply_suffix}",
                                emoji_policy,
                                emoji_replacements,
                            )
                            reply_tokens_text = full_reply
                        if not full_reply and not stream_sent_any:
                            used_stream = False

                if not used_stream:
                    reply = await ai_client.generate_reply(
                        chat_id,
                        user_text,
                        system_prompt,
                        memory_context=memory_context,
                    )
                    if not reply:
                        return

                    reply_tokens_text = reply
                    reply_text = (
                        f"{reply}{reply_suffix}" if reply_suffix else reply
                    )
                    full_reply = sanitize_reply_text(
                        reply_text, emoji_policy, emoji_replacements
                    )
                    reply_preview = full_reply
                    await maybe_sleep_random(random_delay_range)
                    ok, err_msg = await send_reply_chunks(
                        wx,
                        event.chat_name,
                        full_reply,
                        bot_cfg,
                        reply_chunk_size,
                        reply_chunk_delay_sec,
                        min_reply_interval,
                        last_reply_ts,
                        wx_lock,
                    )
                    if not ok:
                        logging.error(
                            "发送失败 | 会话=%s | 错误=%s",
                            event.chat_name,
                            err_msg or "unknown",
                        )
                        return

                if memory and reply_tokens_text:
                    try:
                        memory.add_message(chat_id, "assistant", reply_tokens_text)
                    except Exception as exc:
                        logging.warning("memory write failed: %s", exc)
                user_tokens, reply_tokens, exchange_tokens = estimate_exchange_tokens(
                    ai_client, user_text, reply_tokens_text
                )
                history_tokens = ai_client.get_history_stats().get("tokens", 0)
                logging.info(
                    "回复完成 | 时间=%s | 发送者=%s | 消息=%s | 会话=%s | 回复=%s | tokens=%s(用户=%s,回复=%s) | 历史tokens=%s",
                    time.strftime("%Y-%m-%d %H:%M:%S"),
                    event.sender,
                    message_log,
                    event.chat_name,
                    format_log_text(reply_preview, log_reply_content),
                    exchange_tokens,
                    user_tokens,
                    reply_tokens,
                    history_tokens,
                )
            except Exception as exc:
                logging.exception(
                    "消息处理异常 | 时间=%s | 发送者=%s | 消息=%s | 会话=%s | 回复=%s | 错误=%s",
                    time.strftime("%Y-%m-%d %H:%M:%S"),
                    event.sender,
                    format_log_text(
                        message_log_override
                        if message_log_override is not None
                        else event.content,
                        log_message_content,
                    ),
                    event.chat_name,
                    format_log_text(reply_preview, log_reply_content),
                    exc,
                )

    async def schedule_merged_reply(event: MessageEvent) -> None:
        if is_voice_message(event.msg_type):
            await handle_event(event)
            return
        if not should_reply(event, config):
            return
        user_text = format_user_text(event, bot_cfg)
        chat_id = (
            f"group:{event.chat_name}"
            if event.is_group
            else f"friend:{event.chat_name}"
        )
        now = time.time()
        async with pending_merge_lock:
            first_ts = pending_merge_first_ts.get(chat_id)
            if first_ts is None:
                first_ts = now
                pending_merge_first_ts[chat_id] = first_ts
            pending_merge_messages.setdefault(chat_id, []).append(user_text)
            pending_merge_events[chat_id] = event
            existing_task = pending_merge_tasks.get(chat_id)
            if existing_task and not existing_task.done():
                existing_task.cancel()
            delay = merge_user_messages_sec
            if merge_user_messages_max_wait_sec > 0:
                remaining = merge_user_messages_max_wait_sec - (now - first_ts)
                if remaining <= 0:
                    delay = 0.0
                else:
                    delay = min(delay, remaining)
            task = asyncio.create_task(wait_and_reply(chat_id, delay))
            pending_merge_tasks[chat_id] = task
            pending_tasks.add(task)
            task.add_done_callback(pending_tasks.discard)

    async def wait_and_reply(chat_id: str, delay: float) -> None:
        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            return
        async with pending_merge_lock:
            messages = pending_merge_messages.pop(chat_id, [])
            event = pending_merge_events.pop(chat_id, None)
            pending_merge_tasks.pop(chat_id, None)
            pending_merge_first_ts.pop(chat_id, None)
        combined_text = "\n".join(messages).strip()
        if not event or not combined_text:
            return
        await handle_event(
            event,
            user_text_override=combined_text,
            message_log_override=combined_text,
        )

    while True:
        try:
            now = time.time()
            if config_reload_sec > 0 and now - config_check_ts >= config_reload_sec:
                config_check_ts = now
                new_mtime = get_file_mtime(config_path)
                if new_mtime and new_mtime != config_mtime:
                    try:
                        new_config = load_config(config_path)
                    except (SyntaxError, ValueError) as exc:
                        logging.warning("配置重载失败：%s", exc)
                    else:
                        config = new_config
                        bot_cfg = config.get("bot", {})
                        api_cfg = config.get("api", {})
                        (
                            log_level,
                            log_file,
                            log_max_bytes,
                            log_backup_count,
                        ) = get_logging_settings(config)
                        setup_logging(
                            log_level, log_file, log_max_bytes, log_backup_count
                        )
                        log_message_content, log_reply_content = get_log_behavior(
                            config
                        )
                        reconnect_policy = get_reconnect_policy(bot_cfg)
                        keepalive_idle_sec = as_float(
                            bot_cfg.get("keepalive_idle_sec", keepalive_idle_sec),
                            keepalive_idle_sec,
                            min_value=0.0,
                        )

                        config_mtime = new_mtime
                        config_reload_sec = as_float(
                            bot_cfg.get("config_reload_sec", config_reload_sec),
                            config_reload_sec,
                            min_value=0.0,
                        )
                        reload_ai_client_on_change = bool(
                            bot_cfg.get("reload_ai_client_on_change", True)
                        )
                        reload_ai_client_module = bool(
                            bot_cfg.get("reload_ai_client_module", False)
                        )

                        new_signature = compute_api_signature(api_cfg)
                        if reload_ai_client_on_change and new_signature != api_signature:
                            new_client, new_preset = await select_ai_client(
                                api_cfg, bot_cfg
                            )
                            if new_client:
                                if hasattr(ai_client, "close"):
                                    await ai_client.close()
                                ai_client = new_client
                                preset_name = new_preset
                                api_signature = new_signature
                                logging.info(
                                    "已重新选择预设%s，模型 %s，别名 %s。",
                                    preset_name,
                                    ai_client.model,
                                    get_model_alias(ai_client),
                                )
                            else:
                                logging.warning(
                                    "配置变更后未找到可用预设，继续使用当前配置。"
                                )
                        else:
                            has_presets = bool(api_cfg.get("presets"))
                            apply_ai_runtime_settings(
                                ai_client,
                                api_cfg,
                                bot_cfg,
                                allow_api_override=not has_presets,
                            )
                            api_signature = new_signature

                        poll_interval_min = as_float(
                            bot_cfg.get("poll_interval_min_sec", poll_interval_min),
                            poll_interval_min,
                            min_value=0.01,
                        )
                        poll_interval_max = as_float(
                            bot_cfg.get("poll_interval_max_sec", poll_interval_max),
                            poll_interval_max,
                            min_value=poll_interval_min,
                        )
                        poll_interval = as_float(
                            bot_cfg.get("poll_interval_sec", poll_interval),
                            poll_interval,
                            min_value=poll_interval_min,
                        )
                        poll_interval = min(
                            poll_interval_max,
                            max(poll_interval, poll_interval_min),
                        )
                        poll_backoff = as_float(
                            bot_cfg.get(
                                "poll_interval_backoff_factor", poll_backoff
                            ),
                            poll_backoff,
                            min_value=1.0,
                        )
                        min_reply_interval = as_float(
                            bot_cfg.get("min_reply_interval_sec", min_reply_interval),
                            min_reply_interval,
                            min_value=0.0,
                        )
                        reply_chunk_size = as_int(
                            bot_cfg.get("reply_chunk_size", reply_chunk_size),
                            reply_chunk_size,
                            min_value=1,
                        )
                        reply_chunk_delay_sec = as_float(
                            bot_cfg.get(
                                "reply_chunk_delay_sec", reply_chunk_delay_sec
                            ),
                            reply_chunk_delay_sec,
                            min_value=0.0,
                        )
                        stream_reply = bool(bot_cfg.get("stream_reply", stream_reply))
                        stream_buffer_chars = as_int(
                            bot_cfg.get("stream_buffer_chars", stream_buffer_chars),
                            stream_buffer_chars,
                            min_value=1,
                        )
                        stream_chunk_max_chars = as_int(
                            bot_cfg.get(
                                "stream_chunk_max_chars", stream_chunk_max_chars
                            ),
                            stream_chunk_max_chars,
                            min_value=1,
                        )
                        history_log_interval_sec = as_float(
                            bot_cfg.get(
                                "history_log_interval_sec", history_log_interval_sec
                            ),
                            history_log_interval_sec,
                            min_value=0.0,
                        )
                        next_history_log_ts = (
                            time.time() + history_log_interval_sec
                            if history_log_interval_sec > 0
                            else 0.0
                        )
                        random_delay_range = get_random_delay_range(
                            bot_cfg, random_delay_range
                        )
                        merge_user_messages_sec = as_float(
                            bot_cfg.get(
                                "merge_user_messages_sec", merge_user_messages_sec
                            ),
                            merge_user_messages_sec,
                            min_value=0.0,
                        )
                        merge_user_messages_max_wait_sec = as_float(
                            bot_cfg.get(
                                "merge_user_messages_max_wait_sec",
                                merge_user_messages_max_wait_sec,
                            ),
                            merge_user_messages_max_wait_sec,
                            min_value=0.0,
                        )
                        memory_context_limit = as_int(
                            bot_cfg.get(
                                "memory_context_limit", memory_context_limit
                            ),
                            memory_context_limit,
                            min_value=0,
                        )
                        memory_seed_on_first_reply = bool(
                            bot_cfg.get(
                                "memory_seed_on_first_reply",
                                memory_seed_on_first_reply,
                            )
                        )
                        memory_seed_limit = as_int(
                            bot_cfg.get("memory_seed_limit", memory_seed_limit),
                            memory_seed_limit,
                            min_value=0,
                        )
                        memory_seed_load_more = as_int(
                            bot_cfg.get(
                                "memory_seed_load_more", memory_seed_load_more
                            ),
                            memory_seed_load_more,
                            min_value=0,
                        )
                        memory_seed_load_more_interval_sec = as_float(
                            bot_cfg.get(
                                "memory_seed_load_more_interval_sec",
                                memory_seed_load_more_interval_sec,
                            ),
                            memory_seed_load_more_interval_sec,
                            min_value=0.0,
                        )
                        memory_seed_group = bool(
                            bot_cfg.get(
                                "memory_seed_group", memory_seed_group
                            )
                        )
                        max_concurrency = as_int(
                            bot_cfg.get("max_concurrency", max_concurrency),
                            max_concurrency,
                            min_value=1,
                        )
                        sem = asyncio.Semaphore(max_concurrency)
                        logging.info("配置已更新")

                if reload_ai_client_module:
                    new_ai_mtime = get_file_mtime(ai_module_path)
                    if new_ai_mtime and new_ai_mtime != ai_module_mtime:
                        await reload_ai_module(ai_client)
                        ai_module_mtime = new_ai_mtime
                        logging.info("ai_client.py 已重载")
                        if reload_ai_client_on_change:
                            new_client, new_preset = await select_ai_client(
                                api_cfg, bot_cfg
                            )
                            if new_client:
                                if hasattr(ai_client, "close"):
                                    await ai_client.close()
                                ai_client = new_client
                                preset_name = new_preset
                                logging.info(
                                    "已重新选择预设%s，模型 %s，别名 %s。",
                                    preset_name,
                                    ai_client.model,
                                    get_model_alias(ai_client),
                                )

            if keepalive_idle_sec > 0 and (
                time.time() - last_poll_ok_ts > keepalive_idle_sec
            ):
                wx = await reconnect_wechat("keepalive 超时", reconnect_policy)
                if wx is None:
                    await asyncio.sleep(reconnect_policy.base_delay_sec)
                    continue
                last_poll_ok_ts = time.time()

            if history_log_interval_sec > 0 and now >= next_history_log_ts:
                ai_client.prune_histories()
                stats = ai_client.get_history_stats()
                logging.info(
                    "历史统计 | 会话=%s | 消息=%s | tokens=%s",
                    stats.get("chats", 0),
                    stats.get("messages", 0),
                    stats.get("tokens", 0),
                )
                next_history_log_ts = now + history_log_interval_sec

            try:
                async with wx_lock:
                    raw = await asyncio.to_thread(
                        wx.GetNextNewMessage,
                        filter_mute=bool(bot_cfg.get("filter_mute", False)),
                    )
                last_poll_ok_ts = time.time()
            except Exception as exc:
                logging.exception("获取消息异常：%s", exc)
                wx = await reconnect_wechat("GetNextNewMessage 异常", reconnect_policy)
                if wx is None:
                    await asyncio.sleep(reconnect_policy.base_delay_sec)
                poll_interval = min(poll_interval_max, poll_interval * poll_backoff)
                continue

            events = normalize_new_messages(raw, bot_cfg.get("self_name", ""))

            if events:
                poll_interval = poll_interval_min
            else:
                poll_interval = min(poll_interval_max, poll_interval * poll_backoff)

            for event in events:
                if merge_user_messages_sec > 0:
                    task = asyncio.create_task(schedule_merged_reply(event))
                else:
                    task = asyncio.create_task(handle_event(event))
                pending_tasks.add(task)
                task.add_done_callback(pending_tasks.discard)

        except KeyboardInterrupt:
            logging.info("收到退出信号")
            break
        except Exception as exc:
            logging.exception("主循环异常：%s", exc)
            await asyncio.sleep(2)

        await asyncio.sleep(poll_interval)

    for task in pending_tasks:
        task.cancel()
    if pending_tasks:
        await asyncio.gather(*pending_tasks, return_exceptions=True)

    if hasattr(ai_client, "close"):
        await ai_client.close()


if __name__ == "__main__":
    asyncio.run(main())
