"""
日志工具模块 - 负责日志配置和格式化。
"""

import logging
import os
import json
import traceback
from logging.handlers import RotatingFileHandler
from typing import Dict, List, Optional, Tuple, Any, Literal

from .common import as_int


__all__ = [
    "setup_logging",
    "get_logging_settings",
    "get_log_behavior",
    "format_log_text",
    "JSONFormatter",
]


class JSONFormatter(logging.Formatter):
    """JSON 格式日志格式化器"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            # "path": record.pathname,
            # "line": record.lineno,
        }
        
        if record.exc_info:
            # 格式化异常信息
            log_obj["exception"] = "".join(traceback.format_exception(*record.exc_info))
            
        # 合并 extra 字段 (如果存在)
        if hasattr(record, "extra_data"):
            log_obj.update(record.extra_data)
            
        return json.dumps(log_obj, ensure_ascii=False)


def setup_logging(
    level: str,
    log_file: Optional[str] = None,
    max_bytes: int = 5 * 1024 * 1024,
    backup_count: int = 5,
    format_type: Literal['text', 'json'] = 'text',
) -> None:
    """
    配置全局日志系统。
    
    支持同时输出到控制台和回滚文件日志。
    """
    # 移除现有 handlers 以避免重复
    root = logging.getLogger()
    if root.handlers:
        for handler in root.handlers:
            root.removeHandler(handler)
            
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
        
    # 设置格式化器
    if format_type == 'json':
        formatter = JSONFormatter("%Y-%m-%d %H:%M:%S")
    else:
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        
    for handler in handlers:
        handler.setFormatter(formatter)
        
    logging.basicConfig(
        level=level.upper(),
        handlers=handlers,
        force=True,
    )


def get_logging_settings(config: Dict[str, Any]) -> Tuple[str, Optional[str], int, int, str]:
    """从配置字典中提取日志相关设置。"""
    logging_cfg = config.get("logging", {})
    level = str(logging_cfg.get("level", "INFO"))
    log_file = logging_cfg.get("file")
    max_bytes = as_int(
        logging_cfg.get("max_bytes", 5 * 1024 * 1024),
        5 * 1024 * 1024,
        min_value=1024,
    )
    backup_count = as_int(logging_cfg.get("backup_count", 5), 5, min_value=0)
    format_type = str(logging_cfg.get("format", "text"))
    return level, log_file, max_bytes, backup_count, format_type


def get_log_behavior(config: Dict[str, Any]) -> Tuple[bool, bool]:
    """获取日志记录行为配置（是否记录消息内容/回复内容）。"""
    logging_cfg = config.get("logging", {})
    log_message_content = bool(logging_cfg.get("log_message_content", True))
    log_reply_content = bool(logging_cfg.get("log_reply_content", True))
    return log_message_content, log_reply_content


def format_log_text(text: str, enabled: bool, max_len: int = 120) -> str:
    """格式化日志文本，支持脱敏/隐藏和截断。"""
    from .common import truncate_text
    if not enabled:
        return "[hidden]"
    return truncate_text(text, max_len=max_len)
