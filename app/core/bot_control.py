"""
机器人控制命令与状态管理模块。

功能:
- 控制命令处理 (/pause, /resume, /status)
- 静默时段管理
- 用量追踪与告警
"""

from __future__ import annotations

import logging
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════════════
#                               机器人状态管理
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class BotState:
    """机器人运行状态"""
    is_paused: bool = False
    pause_reason: str = ""
    pause_time: Optional[float] = None
    start_time: float = field(default_factory=time.time)
    total_replies: int = 0
    today_replies: int = 0
    today_date: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    
    # 用量追踪
    today_tokens: int = 0
    total_tokens: int = 0
    
    def reset_daily_stats(self) -> None:
        """重置每日统计"""
        today = datetime.now().strftime("%Y-%m-%d")
        if self.today_date != today:
            self.today_date = today
            self.today_replies = 0
            self.today_tokens = 0
    
    def add_reply(self, tokens: int = 0) -> None:
        """记录一次回复"""
        self.reset_daily_stats()
        self.total_replies += 1
        self.today_replies += 1
        self.today_tokens += tokens
        self.total_tokens += tokens
    
    def get_uptime_str(self) -> str:
        """获取运行时长字符串"""
        elapsed = int(time.time() - self.start_time)
        hours, remainder = divmod(elapsed, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours > 0:
            return f"{hours}小时{minutes}分钟"
        elif minutes > 0:
            return f"{minutes}分钟{seconds}秒"
        else:
            return f"{seconds}秒"
    
    def get_status_text(self) -> str:
        """获取状态摘要文本"""
        self.reset_daily_stats()
        status = "⏸️ 已暂停" if self.is_paused else "✅ 运行中"
        lines = [
            f"状态: {status}",
            f"运行时长: {self.get_uptime_str()}",
            f"今日回复: {self.today_replies}",
            f"今日 Token: {self.today_tokens:,}",
        ]
        if self.is_paused and self.pause_reason:
            lines.append(f"暂停原因: {self.pause_reason}")
        return "\n".join(lines)


# 全局状态实例
_bot_state: Optional[BotState] = None


def get_bot_state() -> BotState:
    """获取机器人状态单例"""
    global _bot_state
    if _bot_state is None:
        _bot_state = BotState()
    return _bot_state


def reset_bot_state() -> None:
    """重置机器人状态"""
    global _bot_state
    _bot_state = BotState()


# ═══════════════════════════════════════════════════════════════════════════════
#                               控制命令处理
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class ControlCommand:
    """控制命令解析结果"""
    command: str           # 命令名（如 pause, resume, status）
    args: List[str]        # 命令参数
    is_valid: bool         # 是否有效命令
    response: str          # 响应文本
    should_reply: bool     # 是否应该发送回复


def parse_control_command(
    text: str,
    prefix: str = "/",
    allowed_users: Optional[List[str]] = None,
    sender: Optional[str] = None,
) -> Optional[ControlCommand]:
    """
    解析控制命令。
    
    Args:
        text: 消息文本
        prefix: 命令前缀
        allowed_users: 允许使用命令的用户列表，None或空列表表示所有人
        sender: 发送者名称
    
    Returns:
        ControlCommand 或 None（非命令消息）
    """
    text = text.strip()
    if not text.startswith(prefix):
        return None
    
    # 解析命令和参数
    parts = text[len(prefix):].split(maxsplit=1)
    if not parts:
        return None
    
    command = parts[0].lower()
    args = parts[1].split() if len(parts) > 1 else []
    
    # 权限检查
    if allowed_users and sender and sender not in allowed_users:
        return ControlCommand(
            command=command,
            args=args,
            is_valid=False,
            response="",
            should_reply=False,
        )
    
    state = get_bot_state()
    
    # 处理各种命令
    if command == "pause":
        if state.is_paused:
            return ControlCommand(
                command=command,
                args=args,
                is_valid=True,
                response="机器人已经是暂停状态",
                should_reply=True,
            )
        state.is_paused = True
        state.pause_time = time.time()
        state.pause_reason = " ".join(args) if args else "手动暂停"
        return ControlCommand(
            command=command,
            args=args,
            is_valid=True,
            response="⏸️ 机器人已暂停\n发送 /resume 恢复",
            should_reply=True,
        )
    
    elif command == "resume":
        if not state.is_paused:
            return ControlCommand(
                command=command,
                args=args,
                is_valid=True,
                response="机器人已经在运行中",
                should_reply=True,
            )
        state.is_paused = False
        state.pause_reason = ""
        state.pause_time = None
        return ControlCommand(
            command=command,
            args=args,
            is_valid=True,
            response="▶️ 机器人已恢复运行",
            should_reply=True,
        )
    
    elif command == "status":
        return ControlCommand(
            command=command,
            args=args,
            is_valid=True,
            response=f"🤖 机器人状态\n{state.get_status_text()}",
            should_reply=True,
        )
    
    elif command == "help":
        help_text = """🤖 可用命令:
/pause [原因] - 暂停自动回复
/resume - 恢复自动回复
/status - 查看运行状态
/help - 显示此帮助"""
        return ControlCommand(
            command=command,
            args=args,
            is_valid=True,
            response=help_text,
            should_reply=True,
        )
    
    # 未知命令
    return None


def is_command_message(text: str, prefix: str = "/") -> bool:
    """检查是否为命令消息"""
    text = text.strip()
    if not text.startswith(prefix):
        return False
    cmd = text[len(prefix):].split()[0].lower() if text[len(prefix):] else ""
    return cmd in ("pause", "resume", "status", "help")


# ═══════════════════════════════════════════════════════════════════════════════
#                               静默时段
# ═══════════════════════════════════════════════════════════════════════════════


def parse_time(time_str: str) -> Tuple[int, int]:
    """解析 HH:MM 格式时间"""
    try:
        parts = time_str.strip().split(":")
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
        return hour, minute
    except (ValueError, IndexError):
        return 0, 0


def is_in_quiet_hours(
    start_time: str = "23:00",
    end_time: str = "07:00",
) -> bool:
    """
    检查当前是否在静默时段内。
    
    支持跨午夜的时段，如 23:00 - 07:00
    """
    now = datetime.now()
    current_minutes = now.hour * 60 + now.minute
    
    start_h, start_m = parse_time(start_time)
    end_h, end_m = parse_time(end_time)
    
    start_minutes = start_h * 60 + start_m
    end_minutes = end_h * 60 + end_m
    
    if start_minutes <= end_minutes:
        # 不跨午夜，如 09:00 - 18:00
        return start_minutes <= current_minutes < end_minutes
    else:
        # 跨午夜，如 23:00 - 07:00
        return current_minutes >= start_minutes or current_minutes < end_minutes


def should_respond(bot_cfg: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    检查机器人是否应该响应消息。
    
    Returns:
        (should_respond, quiet_reply)
        - should_respond: 是否应该响应
        - quiet_reply: 静默期间的自动回复（如果有）
    """
    state = get_bot_state()
    
    # 检查手动暂停
    if state.is_paused:
        return False, None
    
    # 检查静默时段
    if bot_cfg.get("quiet_hours_enabled", False):
        start = bot_cfg.get("quiet_hours_start", "23:00")
        end = bot_cfg.get("quiet_hours_end", "07:00")
        if is_in_quiet_hours(start, end):
            quiet_reply = bot_cfg.get("quiet_hours_reply", "")
            return False, quiet_reply.strip() if quiet_reply else None
    
    return True, None


# ═══════════════════════════════════════════════════════════════════════════════
#                               用量追踪
# ═══════════════════════════════════════════════════════════════════════════════


class UsageTracker:
    """Token 用量追踪器"""
    
    def __init__(self, db_path: str = "usage_history.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self) -> None:
        """初始化数据库"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS usage_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    date TEXT NOT NULL,
                    chat_id TEXT,
                    model TEXT,
                    prompt_tokens INTEGER DEFAULT 0,
                    completion_tokens INTEGER DEFAULT 0,
                    total_tokens INTEGER DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_usage_date 
                ON usage_log(date)
            """)
            conn.commit()
    
    def log_usage(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        chat_id: str = "",
        model: str = "",
    ) -> None:
        """记录一次 API 调用"""
        now = time.time()
        date = datetime.now().strftime("%Y-%m-%d")
        total = prompt_tokens + completion_tokens
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO usage_log 
                (timestamp, date, chat_id, model, prompt_tokens, completion_tokens, total_tokens)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (now, date, chat_id, model, prompt_tokens, completion_tokens, total),
            )
            conn.commit()
        
        # 更新全局状态
        state = get_bot_state()
        state.add_reply(total)
    
    def get_daily_usage(self, date: Optional[str] = None) -> Dict[str, int]:
        """获取每日用量"""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT 
                    COALESCE(SUM(prompt_tokens), 0),
                    COALESCE(SUM(completion_tokens), 0),
                    COALESCE(SUM(total_tokens), 0),
                    COUNT(*)
                FROM usage_log WHERE date = ?
                """,
                (date,),
            ).fetchone()
        
        return {
            "prompt_tokens": row[0],
            "completion_tokens": row[1],
            "total_tokens": row[2],
            "request_count": row[3],
        }
    
    def check_limit(
        self,
        daily_limit: int,
        warning_threshold: float = 0.8,
    ) -> Tuple[bool, bool, float]:
        """
        检查是否超出限制。
        
        Returns:
            (exceeded, warning, usage_ratio)
        """
        if daily_limit <= 0:
            return False, False, 0.0
        
        usage = self.get_daily_usage()
        total = usage["total_tokens"]
        ratio = total / daily_limit
        
        exceeded = ratio >= 1.0
        warning = ratio >= warning_threshold
        
        return exceeded, warning, ratio


# 全局用量追踪器实例
_usage_tracker: Optional[UsageTracker] = None


def get_usage_tracker(db_path: str = "usage_history.db") -> UsageTracker:
    """获取用量追踪器单例"""
    global _usage_tracker
    if _usage_tracker is None:
        _usage_tracker = UsageTracker(db_path)
    return _usage_tracker
