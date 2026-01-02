"""
OpenAI 兼容 /chat/completions 的 AI 客户端封装。
说明：
- 使用 httpx 异步调用接口（不依赖官方 SDK）。
- 按会话在内存中保留最近 N 轮对话。
- 失败时简单重试并退避。
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import OrderedDict, deque
from typing import AsyncIterator, Deque, Dict, Iterable, List, Optional

import httpx


DEFAULT_TIMEOUT_SEC = 10.0
MAX_TIMEOUT_SEC = 10.0
MAX_RETRIES = 2

_shared_client: Optional[httpx.AsyncClient] = None


def _get_shared_client() -> httpx.AsyncClient:
    global _shared_client
    if _shared_client is None or _shared_client.is_closed:
        _shared_client = httpx.AsyncClient(timeout=DEFAULT_TIMEOUT_SEC)
    return _shared_client


def _coerce_timeout(value: float) -> float:
    try:
        val = float(value)
    except (TypeError, ValueError):
        val = DEFAULT_TIMEOUT_SEC
    if val <= 0:
        val = DEFAULT_TIMEOUT_SEC
    return min(val, MAX_TIMEOUT_SEC)


def _coerce_retries(value: int) -> int:
    try:
        val = int(value)
    except (TypeError, ValueError):
        val = MAX_RETRIES
    if val < 0:
        val = 0
    return min(val, MAX_RETRIES)


class AIClient:
    """OpenAI 兼容聊天接口的轻量封装。"""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout_sec: float = DEFAULT_TIMEOUT_SEC,
        max_retries: int = MAX_RETRIES,
        context_rounds: int = 5,
        context_max_tokens: Optional[int] = None,
        system_prompt: str = "",
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        max_completion_tokens: Optional[int] = None,
        reasoning_effort: Optional[str] = None,
        model_alias: Optional[str] = None,
        history_max_chats: int = 200,
        history_ttl_sec: Optional[float] = 24 * 60 * 60,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.model_alias = model_alias or ""
        self.timeout_sec = _coerce_timeout(timeout_sec)
        self.max_retries = _coerce_retries(max_retries)
        self.context_rounds = context_rounds
        if context_max_tokens is None:
            self.context_max_tokens = None
        else:
            self.context_max_tokens = max(1, int(context_max_tokens))
        self.system_prompt = system_prompt
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.max_completion_tokens = max_completion_tokens
        self.reasoning_effort = reasoning_effort
        self.history_max_chats = max(1, int(history_max_chats))
        if history_ttl_sec is None:
            self.history_ttl_sec = None
        else:
            self.history_ttl_sec = float(history_ttl_sec)
            if self.history_ttl_sec <= 0:
                self.history_ttl_sec = None

        self._histories: "OrderedDict[str, Deque[dict]]" = OrderedDict()
        self._history_timestamps: Dict[str, float] = {}
        self._chat_locks: Dict[str, asyncio.Lock] = {}

    def _build_headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _get_chat_lock(self, chat_id: str) -> asyncio.Lock:
        lock = self._chat_locks.get(chat_id)
        if lock is None:
            lock = asyncio.Lock()
            self._chat_locks[chat_id] = lock
        return lock

    async def probe(self) -> bool:
        """探测接口是否可用、模型是否可调用。"""
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 1,
            "temperature": 0,
        }
        if self.max_completion_tokens is not None:
            payload.pop("max_tokens", None)
            payload["max_completion_tokens"] = 1
        client = _get_shared_client()
        try:
            resp = await client.post(
                url,
                headers=self._build_headers(),
                json=payload,
                timeout=self.timeout_sec,
            )
            if resp.status_code >= 400:
                logging.warning(
                    "探测失败（HTTP %s）：%s", resp.status_code, resp.text[:200]
                )
                return False
            try:
                data = resp.json()
            except ValueError:
                logging.warning("探测失败：返回内容不是 JSON。")
                return False
            if not data.get("choices"):
                logging.warning("探测失败：返回内容缺少 choices。")
                return False
            return True
        except Exception as exc:
            logging.warning("探测失败：%s", exc)
            return False

    async def generate_reply(
        self,
        chat_id: str,
        user_text: str,
        system_prompt: Optional[str] = None,
        memory_context: Optional[Iterable[dict]] = None,
    ) -> Optional[str]:
        """调用模型并返回回复文本，失败返回 None。"""
        lock = self._get_chat_lock(chat_id)
        async with lock:
            messages = self._build_messages(
                chat_id, user_text, system_prompt, memory_context
            )
            payload = {
                "model": self.model,
                "messages": messages,
            }
            if self.temperature is not None:
                payload["temperature"] = self.temperature
            if self.max_completion_tokens is not None:
                payload["max_completion_tokens"] = self.max_completion_tokens
            elif self.max_tokens is not None:
                payload["max_tokens"] = self.max_tokens
            if self.reasoning_effort:
                payload["reasoning_effort"] = self.reasoning_effort

            url = f"{self.base_url}/chat/completions"
            headers = self._build_headers()
            client = _get_shared_client()

            last_error: Optional[Exception] = None
            for attempt in range(self.max_retries + 1):
                try:
                    resp = await client.post(
                        url, headers=headers, json=payload, timeout=self.timeout_sec
                    )
                    if resp.status_code >= 400:
                        raise RuntimeError(
                            f"HTTP {resp.status_code}：{resp.text[:200]}"
                        )

                    try:
                        data = resp.json()
                    except ValueError as exc:
                        raise RuntimeError(
                            f"响应不是 JSON：{resp.text[:200]}"
                        ) from exc
                    if data.get("error"):
                        raise RuntimeError(f"接口错误：{data.get('error')}")
                    reply = (
                        data.get("choices", [{}])[0]
                        .get("message", {})
                        .get("content", "")
                    )
                    reply = reply.strip()
                    if not reply:
                        raise RuntimeError("AI 返回内容为空。")

                    self._append_history(chat_id, user_text, reply)
                    return reply
                except Exception as exc:
                    last_error = exc
                    wait = 0.6 * (1.5**attempt)
                    logging.warning("AI 请求失败（第 %s 次）：%s", attempt + 1, exc)
                    if attempt < self.max_retries:
                        await asyncio.sleep(wait)

            logging.error("AI 请求多次失败：%s", last_error)
            return None

    async def generate_reply_stream(
        self,
        chat_id: str,
        user_text: str,
        system_prompt: Optional[str] = None,
        memory_context: Optional[Iterable[dict]] = None,
    ) -> Optional[AsyncIterator[str]]:
        """流式调用模型，返回分段内容迭代器，失败返回 None。"""
        lock = self._get_chat_lock(chat_id)
        url = f"{self.base_url}/chat/completions"
        headers = self._build_headers()
        client = _get_shared_client()

        async def _stream() -> AsyncIterator[str]:
            async with lock:
                messages = self._build_messages(
                    chat_id, user_text, system_prompt, memory_context
                )
                payload = {
                    "model": self.model,
                    "messages": messages,
                    "stream": True,
                }
                if self.temperature is not None:
                    payload["temperature"] = self.temperature
                if self.max_completion_tokens is not None:
                    payload["max_completion_tokens"] = self.max_completion_tokens
                elif self.max_tokens is not None:
                    payload["max_tokens"] = self.max_tokens
                if self.reasoning_effort:
                    payload["reasoning_effort"] = self.reasoning_effort

                last_error: Optional[Exception] = None
                sent_any = False
                for attempt in range(self.max_retries + 1):
                    reply_parts: List[str] = []
                    try:
                        async with client.stream(
                            "POST",
                            url,
                            headers=headers,
                            json=payload,
                            timeout=self.timeout_sec,
                        ) as resp:
                            if resp.status_code >= 400:
                                error_text = (await resp.aread())[:200]
                                raise RuntimeError(
                                    f"HTTP {resp.status_code}：{error_text}"
                                )
                            async for raw_line in resp.aiter_lines():
                                if not raw_line:
                                    continue
                                line = raw_line.strip()
                                if not line.startswith("data:"):
                                    continue
                                data_text = line[5:].strip()
                                if data_text == "[DONE]":
                                    break
                                try:
                                    data = json.loads(data_text)
                                except ValueError:
                                    continue
                                delta = data.get("choices", [{}])[0].get("delta", {})
                                chunk = delta.get("content")
                                if chunk is None:
                                    chunk = (
                                        data.get("choices", [{}])[0]
                                        .get("message", {})
                                        .get("content")
                                    )
                                if not chunk:
                                    continue
                                reply_parts.append(chunk)
                                sent_any = True
                                yield chunk

                        reply = "".join(reply_parts).strip()
                        if not reply:
                            raise RuntimeError("AI 返回内容为空。")
                        self._append_history(chat_id, user_text, reply)
                        return
                    except Exception as exc:
                        last_error = exc
                        if sent_any:
                            partial_reply = "".join(reply_parts).strip()
                            if partial_reply:
                                self._append_history(chat_id, user_text, partial_reply)
                            logging.warning(
                                "AI 流式请求中断，已输出部分内容，停止重试：%s", exc
                            )
                            return
                        wait = 0.6 * (1.5**attempt)
                        logging.warning(
                            "AI 流式请求失败（第 %s 次）：%s", attempt + 1, exc
                        )
                        if attempt < self.max_retries:
                            await asyncio.sleep(wait)

                logging.error("AI 流式请求多次失败：%s", last_error)
                return

        return _stream()

    def _normalize_memory_context(
        self, memory_context: Optional[Iterable[dict]]
    ) -> List[dict]:
        if not memory_context:
            return []
        cleaned: List[dict] = []
        for msg in memory_context:
            if not isinstance(msg, dict):
                continue
            role = str(msg.get("role", "") or "").strip().lower()
            content = msg.get("content")
            if not role or content is None:
                continue
            content = str(content).strip()
            if not content:
                continue
            if role not in ("user", "assistant", "system"):
                role = "user"
            cleaned.append({"role": role, "content": content})
        return cleaned

    def _build_messages(
        self,
        chat_id: str,
        user_text: str,
        system_prompt: Optional[str] = None,
        memory_context: Optional[Iterable[dict]] = None,
    ) -> List[dict]:
        self._prune_histories()
        history = list(self._histories.get(chat_id, deque()))
        if history:
            self._touch_history(chat_id)
        prompt = self.system_prompt if system_prompt is None else system_prompt
        memory_messages = self._normalize_memory_context(memory_context)
        memory_header = None
        if memory_messages:
            memory_header = {
                "role": "system",
                "content": "Previous conversation memory (from local db):",
            }
        if self.context_max_tokens:
            prompt_tokens = 0
            if prompt:
                prompt_tokens = self._estimate_message_tokens(
                    {"role": "system", "content": prompt}
                )
            user_tokens = self._estimate_message_tokens(
                {"role": "user", "content": user_text}
            )
            budget = max(0, self.context_max_tokens - prompt_tokens - user_tokens)
            if memory_header:
                header_tokens = self._estimate_message_tokens(memory_header)
                budget = max(0, budget - header_tokens)
            if memory_messages:
                memory_messages = self._trim_history_by_tokens(
                    memory_messages, budget
                )
                memory_tokens = self._estimate_messages_tokens(memory_messages)
                budget = max(0, budget - memory_tokens)
            history = self._trim_history_by_tokens(history, budget)
        messages: List[dict] = []
        if prompt:
            messages.append({"role": "system", "content": prompt})
        if memory_messages:
            if memory_header:
                messages.append(memory_header)
            messages.extend(memory_messages)
        messages.extend(history)
        messages.append({"role": "user", "content": user_text})
        return messages

    def _append_history(self, chat_id: str, user_text: str, reply: str) -> None:
        max_messages = max(1, self.context_rounds) * 2
        history = self._histories.get(chat_id)
        if history is None or history.maxlen != max_messages:
            history = deque(history or [], maxlen=max_messages)
        history.append({"role": "user", "content": user_text})
        history.append({"role": "assistant", "content": reply})

        if self.context_max_tokens:
            trimmed = self._trim_history_by_tokens(list(history), self.context_max_tokens)
            history = deque(trimmed, maxlen=max_messages)

        self._histories[chat_id] = history
        self._touch_history(chat_id)
        self._prune_histories()

    def _touch_history(self, chat_id: str) -> None:
        if chat_id in self._histories:
            self._histories.move_to_end(chat_id)
        self._history_timestamps[chat_id] = time.time()

    def _prune_histories(self) -> None:
        if self.history_ttl_sec:
            cutoff = time.time() - self.history_ttl_sec
            expired = [
                chat_id
                for chat_id, ts in self._history_timestamps.items()
                if ts < cutoff
            ]
            for chat_id in expired:
                self._history_timestamps.pop(chat_id, None)
                self._histories.pop(chat_id, None)
                self._chat_locks.pop(chat_id, None)

        while len(self._histories) > self.history_max_chats:
            oldest_chat_id, _ = self._histories.popitem(last=False)
            self._history_timestamps.pop(oldest_chat_id, None)
            self._chat_locks.pop(oldest_chat_id, None)

    def _estimate_text_tokens(self, text: str) -> int:
        if not text:
            return 0
        cjk = 0
        for ch in text:
            if "\u4e00" <= ch <= "\u9fff":
                cjk += 1
        ascii_count = max(0, len(text) - cjk)
        ascii_tokens = max(1, ascii_count // 4) if ascii_count else 0
        return cjk + ascii_tokens

    def _estimate_message_tokens(self, message: dict) -> int:
        content = str(message.get("content", "") or "")
        return self._estimate_text_tokens(content) + 4

    def _estimate_messages_tokens(self, messages: List[dict]) -> int:
        return sum(self._estimate_message_tokens(msg) for msg in messages)

    def _trim_history_by_tokens(
        self, history: List[dict], max_tokens: int
    ) -> List[dict]:
        if not history or max_tokens <= 0:
            return []
        total = 0
        kept: List[dict] = []
        for msg in reversed(history):
            msg_tokens = self._estimate_message_tokens(msg)
            if total + msg_tokens > max_tokens and kept:
                break
            kept.append(msg)
            total += msg_tokens
            if total >= max_tokens:
                break
        return list(reversed(kept))

    def prune_histories(self) -> None:
        self._prune_histories()

    def get_history_stats(self) -> Dict[str, int]:
        total_messages = sum(len(history) for history in self._histories.values())
        total_tokens = sum(
            self._estimate_messages_tokens(list(history))
            for history in self._histories.values()
        )
        return {
            "chats": len(self._histories),
            "messages": total_messages,
            "tokens": total_tokens,
        }

    async def close(self) -> None:
        global _shared_client
        if _shared_client is None:
            return
        try:
            await _shared_client.aclose()
        except Exception:
            pass
        _shared_client = None
