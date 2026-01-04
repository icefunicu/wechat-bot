"""
核心功能模块。

包含：
    - AIClient: OpenAI 兼容 API 客户端
    - MemoryManager: SQLite 记忆管理器
    - emotion: 情感检测功能
"""

from core.ai_client import AIClient
from core.memory import MemoryManager
from core.emotion import (
    EmotionResult,
    detect_emotion_keywords,
    get_emotion_response_guide,
    get_emotion_analysis_prompt,
    parse_emotion_ai_response,
    get_fact_extraction_prompt,
    parse_fact_extraction_response,
    get_time_period,
    get_time_context,
    get_time_aware_prompt_addition,
    analyze_conversation_style,
    get_style_adaptation_hint,
    analyze_emotion_trend,
    get_emotion_trend_hint,
    get_relationship_evolution_hint,
)

__all__ = [
    # AI 客户端
    "AIClient",
    # 记忆管理
    "MemoryManager",
    # 情感检测
    "EmotionResult",
    "detect_emotion_keywords",
    "get_emotion_response_guide",
    "get_emotion_analysis_prompt",
    "parse_emotion_ai_response",
    "get_fact_extraction_prompt",
    "parse_fact_extraction_response",
    # 人性化增强
    "get_time_period",
    "get_time_context",
    "get_time_aware_prompt_addition",
    "analyze_conversation_style",
    "get_style_adaptation_hint",
    "analyze_emotion_trend",
    "get_emotion_trend_hint",
    "get_relationship_evolution_hint",
]
