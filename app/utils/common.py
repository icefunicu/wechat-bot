"""
通用工具模块 - 提供基础的类型转换和工具函数。
"""

import os
from typing import Any, Iterable, Optional, List, Tuple

__all__ = [
    "as_int",
    "as_float",
    "as_optional_int",
    "as_optional_str",
    "iter_items",
    "truncate_text",
    "get_file_mtime",
]


def as_int(value: Any, default: int, min_value: Optional[int] = None) -> int:
    """如果转换失败则返回默认值，支持可选的最小值限制。"""
    try:
        val = int(value)
    except (TypeError, ValueError):
        return default
    if min_value is not None and val < min_value:
        return min_value
    return val


def as_float(value: Any, default: float, min_value: Optional[float] = None) -> float:
    """如果转换失败则返回默认值，支持可选的最小值限制。"""
    try:
        val = float(value)
    except (TypeError, ValueError):
        return default
    if min_value is not None and val < min_value:
        return min_value
    return val


def as_optional_int(value: Any) -> Optional[int]:
    """尝试转换为整数，失败或为 None 则返回 None。"""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def as_optional_str(value: Any) -> Optional[str]:
    """去除空白字符后，如果为空字符串则返回 None。"""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def iter_items(obj: Any) -> Iterable[Any]:
    """将单个对象或列表统一转换为可迭代对象。"""
    if isinstance(obj, (list, tuple)):
        return obj
    return [obj]


def truncate_text(text: str, max_len: int = 50) -> str:
    """截断文本，超出部分用省略号表示。"""
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def get_file_mtime(filepath: str) -> Optional[float]:
    """获取文件修改时间，文件不存在返回 None。"""
    try:
        return os.path.getmtime(filepath)
    except OSError:
        return None
