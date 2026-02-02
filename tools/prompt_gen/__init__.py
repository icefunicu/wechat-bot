"""
个性化 Prompt 管理模块。

包含：
    - PROMPT_OVERRIDES: 预加载的个性化 Prompt 字典
    - get_prompt_for_contact: 获取指定联系人的 Prompt
    - reload_prompts: 重新加载 Prompt
    - generate_personalized_prompt: 生成个性化 Prompt（异步）
"""

from .overrides import (
    PROMPT_OVERRIDES,
    get_prompt_for_contact,
    reload_prompts,
    list_contacts,
    get_prompt_stats,
)
from .generator import generate_personalized_prompt

__all__ = [
    # 从 overrides 导出
    "PROMPT_OVERRIDES",
    "get_prompt_for_contact",
    "reload_prompts",
    "list_contacts",
    "get_prompt_stats",
    # 从 generator 导出
    "generate_personalized_prompt",
]
