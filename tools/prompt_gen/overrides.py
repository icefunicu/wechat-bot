"""
个性化 Prompt 覆盖配置模块。

此模块负责加载和管理针对不同联系人的个性化 system_prompt。
支持从 JSON 文件加载、缓存、验证等功能。

使用方法：
    from prompt_overrides import PROMPT_OVERRIDES, get_prompt_for_contact

此文件由 prompt_generator.py 自动生成。
要更新，请重新运行：python prompt_generator.py
"""

import logging
import os
import json
from typing import Dict, Optional, Tuple
from functools import lru_cache

logger = logging.getLogger(__name__)

# 配置常量
SUMMARY_FILE_NAME = "top10_prompts_summary.json"
CHAT_EXPORTS_DIR = "chat_exports"

# 缓存变量
_prompt_cache: Optional[Dict[str, str]] = None
_cache_mtime: float = 0.0


def _get_summary_file_path() -> str:
    """获取 JSON 汇总文件的完整路径。"""
    # 假设 tools/prompt_gen/overrides.py
    # chat_exports 在项目根目录
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(
        project_root,
        CHAT_EXPORTS_DIR,
        SUMMARY_FILE_NAME
    )


def _validate_prompt(prompt: str, contact_name: str) -> Tuple[bool, str]:
    """
    验证 prompt 是否有效。
    
    Returns:
        (is_valid, message) 元组
    """
    if not prompt or not isinstance(prompt, str):
        return False, f"Prompt for {contact_name} is empty or invalid"
    
    # 检查基本结构
    if len(prompt) < 50:
        return False, f"Prompt for {contact_name} is too short ({len(prompt)} chars)"
    
    # 检查必要元素
    required_elements = ["身份", "禁止"]
    missing = [elem for elem in required_elements if elem not in prompt]
    if missing:
        return False, f"Prompt for {contact_name} missing required elements: {missing}"
    
    return True, "Valid"


def _load_from_json(validate: bool = True) -> Dict[str, str]:
    """
    从 top10_prompts_summary.json 加载个性化 prompt。
    
    支持两种 JSON 格式：
    1. 新格式（带 metadata）：{"metadata": {...}, "contacts": {name: {"prompt": ...}}}
    2. 旧格式（直接映射）：{name: {"prompt": ...}}
    
    Args:
        validate: 是否验证 prompt 有效性
        
    Returns:
        联系人名称到 prompt 的映射字典
    """
    summary_file = _get_summary_file_path()
    
    if not os.path.exists(summary_file):
        logger.debug("Prompt 汇总文件未找到：%s", summary_file)
        return {}
    
    try:
        with open(summary_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        logger.error("Prompt JSON 解析失败：%s", e)
        return {}
    except Exception as e:
        logger.error("Prompt 文件加载失败：%s", e)
        return {}
    
    # 解析数据结构
    prompts: Dict[str, str] = {}
    
    # 新格式：带有 contacts 键
    if "contacts" in data:
        contacts = data["contacts"]
        metadata = data.get("metadata", {})
        logger.info(
            "正在加载 Prompt 汇总文件（生成时间：%s）",
            metadata.get("generated_at", "未知")
        )
        for name, info in contacts.items():
            if isinstance(info, dict) and "prompt" in info:
                prompts[name] = info["prompt"]
    else:
        # 旧格式：直接是 {name: {"prompt": ...}} 结构
        for name, info in data.items():
            if isinstance(info, dict) and "prompt" in info:
                prompts[name] = info["prompt"]
    
    # 验证
    if validate and prompts:
        valid_count = 0
        for name, prompt in list(prompts.items()):
            is_valid, msg = _validate_prompt(prompt, name)
            if is_valid:
                valid_count += 1
            else:
                logger.warning("无效的 Prompt：%s", msg)
        logger.info("已加载 %d 个 Prompt（有效 %d 个）", len(prompts), valid_count)
    else:
        logger.info("已加载 %d 个 Prompt（跳过验证）", len(prompts))
    
    return prompts


def reload_prompts(force: bool = False) -> Dict[str, str]:
    """
    重新加载 prompts，支持文件变更检测。
    
    Args:
        force: 强制重新加载，忽略缓存
        
    Returns:
        更新后的 prompt 字典
    """
    global _prompt_cache, _cache_mtime
    
    summary_file = _get_summary_file_path()
    
    try:
        current_mtime = os.path.getmtime(summary_file)
    except OSError:
        current_mtime = 0.0
    
    # 检查是否需要重新加载
    if not force and _prompt_cache is not None and current_mtime <= _cache_mtime:
        return _prompt_cache
    
    # 重新加载
    _prompt_cache = _load_from_json()
    _cache_mtime = current_mtime
    
    return _prompt_cache


def get_prompt_for_contact(contact_name: str) -> Optional[str]:
    """
    获取指定联系人的个性化 prompt。
    
    Args:
        contact_name: 联系人名称
        
    Returns:
        个性化 prompt，如果不存在返回 None
    """
    prompts = reload_prompts()
    return prompts.get(contact_name)


def list_contacts() -> list:
    """获取所有有个性化 prompt 的联系人列表。"""
    prompts = reload_prompts()
    return list(prompts.keys())


def get_prompt_stats() -> Dict[str, any]:
    """
    获取 prompt 统计信息。
    
    Returns:
        包含统计数据的字典
    """
    prompts = reload_prompts()
    
    if not prompts:
        return {"count": 0, "contacts": [], "avg_length": 0}
    
    lengths = [len(p) for p in prompts.values()]
    
    return {
        "count": len(prompts),
        "contacts": list(prompts.keys()),
        "avg_length": sum(lengths) // len(lengths),
        "min_length": min(lengths),
        "max_length": max(lengths),
    }


# 初始化加载
PROMPT_OVERRIDES = _load_from_json(validate=False)

# 如果有日志配置，记录加载状态
if PROMPT_OVERRIDES:
    logger.debug("Initialized with %d prompt overrides", len(PROMPT_OVERRIDES))
