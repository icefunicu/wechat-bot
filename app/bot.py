import asyncio
import logging
import os
import random
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from .core.ai_client import AIClient
from .core.memory import MemoryManager
from .core.emotion import (
    EmotionResult,
    detect_emotion_keywords,
    get_emotion_analysis_prompt,
    parse_emotion_ai_response,
    get_fact_extraction_prompt,
    parse_fact_extraction_response,
    get_relationship_evolution_hint,
)
from .core.bot_control import (
    parse_control_command,
    is_command_message,
    should_respond,
)
from .core.factory import (
    select_ai_client,
    get_reconnect_policy,
    reconnect_wechat,
    apply_ai_runtime_settings,
    compute_api_signature,
    reload_ai_module,
)

from .types import MessageEvent, ReconnectPolicy
from .handlers.filter import should_reply
from .handlers.sender import send_message, send_reply_chunks
from .handlers.converters import normalize_new_messages
from .utils.common import as_float, as_int, get_file_mtime
from .utils.config import load_config, get_model_alias, resolve_system_prompt
from .utils.logging import (
    setup_logging,
    get_logging_settings,
    get_log_behavior,
    format_log_text,
)
from .utils.message import (
    is_voice_message,
    build_reply_suffix,
    sanitize_reply_text,
    split_reply_naturally,
    STREAM_PUNCTUATION,
)
from .utils.tools import transcribe_voice_message, estimate_exchange_tokens


class WeChatBot:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config: Dict[str, Any] = {}
        self.bot_cfg: Dict[str, Any] = {}
        self.api_cfg: Dict[str, Any] = {}
        self.ai_client: Optional[AIClient] = None
        self.memory: Optional[MemoryManager] = None
        self.wx_lock = asyncio.Lock()
        self.sem: Optional[asyncio.Semaphore] = None

        self.last_reply_ts: Dict[str, float] = {"ts": 0.0}
        self.pending_tasks: Set[asyncio.Task] = set()
        
        # 合并消息状态
        self.pending_merge_messages: Dict[str, List[str]] = {}
        self.pending_merge_events: Dict[str, MessageEvent] = {}
        self.pending_merge_first_event: Dict[str, MessageEvent] = {}
        self.pending_merge_tasks: Dict[str, asyncio.Task] = {}
        self.pending_merge_first_ts: Dict[str, float] = {}
        self.pending_merge_lock = asyncio.Lock()

        # 配置监控
        self.config_mtime: Optional[float] = None
        self.ai_module_mtime: Optional[float] = None
        self.api_signature: str = ""
        
        # 日志标志
        self.log_message_content: bool = True
        self.log_reply_content: bool = True

    async def initialize(self) -> Optional["WeChat"]:
        try:
            self.config_mtime = get_file_mtime(self.config_path)
            self.config = load_config(self.config_path)
        except Exception as exc:
            logging.error("无法加载配置文件: %s", exc)
            return None

        self._apply_config()
        
        # 初始化记忆模块
        self.memory = MemoryManager(self.bot_cfg.get("sqlite_db_path", "data/chat_memory.db"))
        
        # 初始化 AI 客户端
        self.ai_client, preset_name = await select_ai_client(self.api_cfg, self.bot_cfg)
        if self.ai_client:
            self.api_signature = compute_api_signature(self.api_cfg)
            logging.info("AI 客户端初始化成功，使用预设: %s", preset_name)
        else:
            logging.warning("AI 客户端初始化失败，未能选择有效预设")

        # 初始化微信客户端
        reconnect_policy = get_reconnect_policy(self.bot_cfg)
        wx = await reconnect_wechat("初始化", reconnect_policy)
        if wx is None:
            logging.error("微信初始化失败")
            return None
            
        return wx

    def _apply_config(self) -> None:
        self.bot_cfg = self.config.get("bot", {})
        self.api_cfg = self.config.get("api", {})
        
        level, log_file, max_bytes, backup_count = get_logging_settings(self.config)
        setup_logging(level, log_file, max_bytes, backup_count)
        
        self.log_message_content, self.log_reply_content = get_log_behavior(self.config)
        
        max_concurrency = as_int(self.bot_cfg.get("max_concurrency", 5), 5, min_value=1)
        self.sem = asyncio.Semaphore(max_concurrency)

    async def run(self) -> None:
        from wxauto import WeChat  # 延迟导入以避免顶层依赖问题
        
        wx = await self.initialize()
        if not wx:
            return

        logging.info("机器人主循环启动")
        
        # 主循环变量
        poll_interval_min = as_float(self.bot_cfg.get("poll_interval_min_sec", 0.05), 0.05)
        poll_interval_max = as_float(self.bot_cfg.get("poll_interval_max_sec", 1.0), 1.0)
        poll_interval = poll_interval_min
        poll_backoff = as_float(self.bot_cfg.get("poll_interval_backoff_factor", 1.2), 1.2)
        
        config_reload_sec = as_float(self.bot_cfg.get("config_reload_sec", 2.0), 2.0)
        config_check_ts = 0.0
        
        last_poll_ok_ts = time.time()
        
        while True:
            try:
                now = time.time()
                
                # 检查配置重载
                if config_reload_sec > 0 and now - config_check_ts >= config_reload_sec:
                    config_check_ts = now
                    await self._check_config_reload(now)
                    # 更新本地变量以适应配置变更
                    poll_interval_min = as_float(self.bot_cfg.get("poll_interval_min_sec", 0.05), 0.05)
                    poll_interval_max = as_float(self.bot_cfg.get("poll_interval_max_sec", 1.0), 1.0)
                    poll_backoff = as_float(self.bot_cfg.get("poll_interval_backoff_factor", 1.2), 1.2)
                    config_reload_sec = as_float(self.bot_cfg.get("config_reload_sec", 2.0), 2.0)

                # 心跳保活检查
                keepalive_idle_sec = as_float(self.bot_cfg.get("keepalive_idle_sec", 0.0), 0.0)
                if keepalive_idle_sec > 0 and (now - last_poll_ok_ts > keepalive_idle_sec):
                    reconnect_policy = get_reconnect_policy(self.bot_cfg)
                    wx = await reconnect_wechat("keepalive 超时", reconnect_policy)
                    if wx is None:
                        await asyncio.sleep(reconnect_policy.base_delay_sec)
                        continue
                    last_poll_ok_ts = time.time()

                # 轮询消息
                try:
                    async with self.wx_lock:
                        raw = await asyncio.to_thread(
                            wx.GetNextNewMessage,
                            filter_mute=bool(self.bot_cfg.get("filter_mute", False)),
                        )
                    last_poll_ok_ts = time.time()
                except Exception as exc:
                    logging.exception("获取消息异常：%s", exc)
                    reconnect_policy = get_reconnect_policy(self.bot_cfg)
                    wx = await reconnect_wechat("GetNextNewMessage 异常", reconnect_policy)
                    if wx is None:
                        await asyncio.sleep(reconnect_policy.base_delay_sec)
                    poll_interval = min(poll_interval_max, poll_interval * poll_backoff)
                    continue

                events = normalize_new_messages(raw, self.bot_cfg.get("self_name", ""))
                
                if events:
                    poll_interval = poll_interval_min
                else:
                    poll_interval = min(poll_interval_max, poll_interval * poll_backoff)

                merge_sec = as_float(self.bot_cfg.get("merge_user_messages_sec", 0.0), 0.0)
                for event in events:
                    if merge_sec > 0:
                        task = asyncio.create_task(self.schedule_merged_reply(wx, event))
                    else:
                        task = asyncio.create_task(self.handle_event(wx, event))
                    self.pending_tasks.add(task)
                    task.add_done_callback(self.pending_tasks.discard)

            except KeyboardInterrupt:
                logging.info("收到退出信号")
                break
            except Exception as exc:
                logging.exception("主循环异常：%s", exc)
                await asyncio.sleep(2)
            
            await asyncio.sleep(poll_interval)

        # 清理资源
        if self.pending_tasks:
            for task in self.pending_tasks:
                task.cancel()
            await asyncio.gather(*self.pending_tasks, return_exceptions=True)
            
        if self.ai_client and hasattr(self.ai_client, "close"):
            await self.ai_client.close()
        
        if self.memory:
            self.memory.close()

    async def _check_config_reload(self, now: float) -> None:
        new_mtime = get_file_mtime(self.config_path)
        if new_mtime and new_mtime != self.config_mtime:
            try:
                new_config = load_config(self.config_path)
            except Exception as exc:
                logging.warning("配置重载失败: %s", exc)
                return

            self.config = new_config
            self._apply_config()
            self.config_mtime = new_mtime
            
            # 重新检查 AI 客户端
            if self.bot_cfg.get("reload_ai_client_on_change", True):
                new_signature = compute_api_signature(self.api_cfg)
                if new_signature != self.api_signature:
                    new_client, new_preset = await select_ai_client(self.api_cfg, self.bot_cfg)
                    if new_client:
                        if self.ai_client and hasattr(self.ai_client, "close"):
                            await self.ai_client.close()
                        self.ai_client = new_client
                        self.api_signature = new_signature
                        logging.info("配置更新，已重新加载 AI 客户端: %s", new_preset)

    async def schedule_merged_reply(self, wx: "WeChat", event: MessageEvent) -> None:
        if is_voice_message(event.msg_type):
            await self.handle_event(wx, event)
            return

        if not should_reply(event, self.config):
            return

        chat_id = f"group:{event.chat_name}" if event.is_group else f"friend:{event.chat_name}"
        now = time.time()
        
        async with self.pending_merge_lock:
            if chat_id not in self.pending_merge_first_ts:
                self.pending_merge_first_ts[chat_id] = now
                self.pending_merge_first_event[chat_id] = event
            
            self.pending_merge_messages.setdefault(chat_id, []).append(event.content)
            self.pending_merge_events[chat_id] = event
            
            if chat_id in self.pending_merge_tasks:
                task = self.pending_merge_tasks[chat_id]
                if not task.done():
                    task.cancel()
            
            merge_sec = as_float(self.bot_cfg.get("merge_user_messages_sec", 0.0), 0.0)
            max_wait = as_float(self.bot_cfg.get("merge_user_messages_max_wait_sec", 0.0), 0.0)
            
            delay = merge_sec
            if max_wait > 0:
                elapsed = now - self.pending_merge_first_ts[chat_id]
                remaining = max_wait - elapsed
                delay = min(delay, max(0.0, remaining))
            
            task = asyncio.create_task(self.wait_and_reply(wx, chat_id, delay))
            self.pending_merge_tasks[chat_id] = task
            self.pending_tasks.add(task)
            task.add_done_callback(self.pending_tasks.discard)

    async def wait_and_reply(self, wx: "WeChat", chat_id: str, delay: float) -> None:
        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            return

        async with self.pending_merge_lock:
            messages = self.pending_merge_messages.pop(chat_id, [])
            event = self.pending_merge_events.pop(chat_id, None)
            first_event = self.pending_merge_first_event.pop(chat_id, None)
            self.pending_merge_tasks.pop(chat_id, None)
            self.pending_merge_first_ts.pop(chat_id, None)
        
        combined_text = "\n".join(messages).strip()
        if not event or not combined_text:
            return
            
        if first_event and first_event.raw_item:
            event.raw_item = first_event.raw_item
            
        await self.handle_event(
            wx,
            event,
            user_text_override=combined_text,
            message_log_override=combined_text,
        )

    async def handle_event(
        self,
        wx: "WeChat",
        event: MessageEvent,
        user_text_override: Optional[str] = None,
        message_log_override: Optional[str] = None
    ) -> None:
        async with self.sem:
            try:
                # 1. 记录日志
                log_text = message_log_override if message_log_override is not None else event.content
                message_log = format_log_text(log_text, self.log_message_content)
                logging.debug(
                    "收到消息 | 会话=%s | 发送者=%s | 类型=%s | 内容=%s",
                    event.chat_name, event.sender, event.msg_type, message_log
                )

                # 2. 控制命令
                if self.bot_cfg.get("control_commands_enabled", True):
                    if await self._handle_control_command(wx, event):
                        return

                # 3. 响应检查 (暂停/静默)
                can_respond, quiet_reply = should_respond(self.bot_cfg)
                if not can_respond:
                    if quiet_reply:
                        async with self.wx_lock:
                            await asyncio.to_thread(
                                send_message, wx, event.chat_name, quiet_reply, self.bot_cfg
                            )
                    return

                if not should_reply(event, self.config):
                    return

                # 4. 语音转文字
                if is_voice_message(event.msg_type) and user_text_override is None:
                    voice_text, err = await transcribe_voice_message(event, self.bot_cfg, self.wx_lock)
                    if not voice_text:
                        logging.warning("语音转文字失败: %s", err)
                        return
                    event.content = voice_text
                    if message_log_override is None:
                        message_log = format_log_text(event.content, self.log_message_content)

                # 5. 核心处理
                await self._process_and_reply(
                    wx, 
                    event,
                    user_text_override or event.content,
                    message_log
                )
                
            except Exception as exc:
                logging.exception("消息处理异常: %s", exc)

    async def _handle_control_command(self, wx: "WeChat", event: MessageEvent) -> bool:
        cmd_prefix = self.bot_cfg.get("control_command_prefix", "/")
        if not is_command_message(event.content, cmd_prefix):
            return False
            
        allowed = self.bot_cfg.get("control_allowed_users", [])
        result = parse_control_command(event.content, cmd_prefix, allowed, event.sender)
        
        if result and result.should_reply:
            if self.bot_cfg.get("control_reply_visible", True):
                 async with self.wx_lock:
                    await asyncio.to_thread(
                        send_message, wx, event.chat_name, result.response, self.bot_cfg
                    )
            logging.info("执行控制命令: %s", result.command)
            return True
        return False

    async def _process_and_reply(
        self,
        wx: "WeChat",
        event: MessageEvent,
        user_text: str,
        message_log: str
    ) -> None:
        chat_id = f"group:{event.chat_name}" if event.is_group else f"friend:{event.chat_name}"
        
        # 记忆与上下文
        memory_context = []
        user_profile = None
        
        if self.memory:
            self.memory.add_message(chat_id, "user", user_text)
            
            if self.bot_cfg.get("personalization_enabled", False):
                user_profile = self.memory.get_user_profile(chat_id)
                self.memory.increment_message_count(chat_id)

            limit = as_int(self.bot_cfg.get("memory_context_limit", 5), 5)
            if limit > 0:
                memory_context = self.memory.get_recent_context(chat_id, limit)

        # 情感分析
        current_emotion = None
        if self.bot_cfg.get("emotion_detection_enabled", False):
            current_emotion = await self._analyze_emotion(chat_id, user_text)
            if self.memory and current_emotion:
                self.memory.update_emotion(chat_id, current_emotion.emotion)

        # 系统提示词
        system_prompt = resolve_system_prompt(
            event, self.bot_cfg, user_profile, current_emotion, memory_context
        )
        
        # 生成回复
        if not self.ai_client:
            return

        reply_text = await self.ai_client.generate_reply(
            chat_id, user_text, system_prompt, memory_context
        )
        
        if not reply_text:
            return

        # 后处理与发送
        await self._send_smart_reply(wx, event, reply_text)
        
        # 更新记忆（助手）
        if self.memory:
            self.memory.add_message(chat_id, "assistant", reply_text)
            
        # 事实提取（后台）
        if user_profile and self.bot_cfg.get("remember_facts_enabled", False):
            # 发后即忘的任务
            pass 

    async def _analyze_emotion(self, chat_id: str, text: str) -> Optional[EmotionResult]:
        mode = str(self.bot_cfg.get("emotion_detection_mode", "keywords")).lower()
        if mode == "ai" and self.ai_client:
            prompt = get_emotion_analysis_prompt(text)
            resp = await self.ai_client.generate_reply(
                f"__emotion__{chat_id}", 
                prompt,
                system_prompt="你是一个情感分析助手，只返回 JSON 格式的分析结果。"
            )
            if resp:
                result = parse_emotion_ai_response(resp)
                if result:
                    return result
        
        return detect_emotion_keywords(text)

    async def _send_smart_reply(self, wx: "WeChat", event: MessageEvent, reply_text: str) -> None:
        chunk_size = as_int(self.bot_cfg.get("reply_chunk_size", 500), 500)
        delay_sec = as_float(self.bot_cfg.get("reply_chunk_delay_sec", 0.0), 0.0)
        min_interval = as_float(self.bot_cfg.get("min_reply_interval_sec", 0.2), 0.2)
        
        emoji_policy = str(self.bot_cfg.get("emoji_policy", "wechat"))
        replacements = self.bot_cfg.get("emoji_replacements")
        
        sanitized_reply = sanitize_reply_text(reply_text, emoji_policy, replacements)
        
        # 自然分段逻辑
        if self.bot_cfg.get("natural_split_enabled", False):
            segments = split_reply_naturally(sanitized_reply)
            for idx, seg in enumerate(segments):
                await send_reply_chunks(
                    wx, event.chat_name, seg, self.bot_cfg,
                    chunk_size, delay_sec, min_interval,
                    self.last_reply_ts, self.wx_lock
                )
                if idx < len(segments) - 1:
                    await asyncio.sleep(random.uniform(0.8, 2.0))
        else:
            await send_reply_chunks(
                wx, event.chat_name, sanitized_reply, self.bot_cfg,
                chunk_size, delay_sec, min_interval,
                self.last_reply_ts, self.wx_lock
            )
