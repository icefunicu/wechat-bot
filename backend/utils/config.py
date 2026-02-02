"""
配置工具模块 - 负责相关配置的加载、解析和规范化。
"""

import importlib.util
import logging
from typing import Any, Dict, List, Optional

from .common import as_int, as_float, as_optional_int, as_optional_str, iter_items
from backend.config_schemas import AppConfig

__all__ = [
    "normalize_system_prompt",
    "load_config_py",
    "load_config",
    "get_setting",
    "is_placeholder_key",
    "build_api_candidates",
    "get_model_alias",
    "resolve_system_prompt",
]


def normalize_system_prompt(value: Any) -> str:
    """
    规范化 system_prompt 配置。
    支持字符串或字符串列表（自动合并）。
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return "\n".join(str(v).strip() for v in value if v)
    return str(value).strip()


def load_config_py(path: str) -> Dict[str, Any]:
    """动态加载 .py 配置文件，返回 CONFIG 字典。"""
    spec = importlib.util.spec_from_file_location("config_module", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load config from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, "CONFIG", {})


def load_config(path: str) -> Dict[str, Any]:
    """加载配置文件（目前仅支持 .py），并使用 Pydantic 验证。"""
    raw_config = load_config_py(path)
    
    # 验证并规范化
    try:
        # Pydantic 验证
        app_config = AppConfig(**raw_config)
        # 转换回字典，使用 mode='json' 确保枚举等类型被序列化为基本类型
        validated_config = app_config.model_dump(mode='json')
        return validated_config
    except Exception as e:
        logging.error(f"配置验证失败: {e}。将使用原始配置。")
        return raw_config


def get_setting(
    settings: Dict[str, Any], key: str, default: Any = None, type_func: Any = None
) -> Any:
    """安全获取配置项，支持类型转换。"""
    val = settings.get(key, default)
    if type_func and val is not None:
        return type_func(val)
    return val


def is_placeholder_key(key: Optional[str]) -> bool:
    """检查 API Key 是否为占位符。"""
    if not key:
        return True
    k = key.strip()
    return k.startswith("YOUR_") or "KEY" in k and len(k) < 10


def build_api_candidates(api_cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    """构建 API 候选列表，支持多预设。"""
    # 按照 active_preset > presets 顺序构建候选列表
    candidates = []
    
    active_name = str(api_cfg.get("active_preset") or "").strip()
    presets_data = api_cfg.get("presets", [])
    
    # 统一转换为字典映射 {name: config}
    presets_map = {}
    if isinstance(presets_data, list):
        for p in presets_data:
            if isinstance(p, dict) and p.get("name"):
                presets_map[str(p["name"])] = p
    elif isinstance(presets_data, dict):
        presets_map = presets_data
    
    # 1. Active Preset (只取匹配的一个)
    if active_name and active_name in presets_map:
        candidate = dict(presets_map[active_name])
        # 确保 name 字段存在
        if "name" not in candidate:
            candidate["name"] = active_name
        candidates.append(candidate)

    # 2. 根配置 (作为后备或旧版本兼容)
    # 只有当 api_key 不是占位符时才添加，或者是 root_config 模式
    # 这里我们宽松一点，只要 base_url 存在就添加，后续由 validate 过滤
    root_candidate = {
        "name": "root_config",
        "base_url": api_cfg.get("base_url"),
        "api_key": api_cfg.get("api_key"),
        "model": api_cfg.get("model"),
        "timeout_sec": api_cfg.get("timeout_sec"),
        "max_retries": api_cfg.get("max_retries"),
        "temperature": api_cfg.get("temperature"),
        "max_tokens": api_cfg.get("max_tokens"),
        "alias": api_cfg.get("alias"),
    }
    
    # 防止重复：如果 active_preset 就是 root_config 并不存在(name不同)，所以通常不冲突
    # 但如果 root config 非常不完整，可以跳过
    if root_candidate.get("base_url"):
        candidates.append(root_candidate)

    # 3. 其他预设 (仅当未指定 active_preset 或需要自动故障转移时)
    # 目前简单逻辑：优先 active，失败后尝试 root。
    # 如果未来支持自动故障转移到其他预设，可以在这里添加逻辑
    # for name, cfg in presets_map.items():
    #     if name == active_name:
    #         continue
    #     candidate = dict(cfg)
    #     candidate["name"] = name
    #     candidates.append(candidate)

    return candidates


def get_model_alias(ai_client: Any) -> str:
    """获取 AI 客户端的模型别名或名称。"""
    if hasattr(ai_client, "model_alias") and ai_client.model_alias:
        return str(ai_client.model_alias)
    if hasattr(ai_client, "model"):
        return str(ai_client.model)
    return "unknown"


def resolve_system_prompt(
    event: Any,
    bot_cfg: Dict[str, Any],
    user_profile: Optional[Dict[str, Any]],
    emotion: Optional[Any],
    context: List[Any],
) -> str:
    """
    解析最终的 System Prompt。
    
    支持逻辑：
    1. 特定会话覆盖 (Overrides)
    2. 基础 Prompt 规范化
    3. 注入用户画像 (如果启用)
    4. 注入当前情绪 (如果启用)
    """
    base_prompt = bot_cfg.get("system_prompt", "")
    overrides = bot_cfg.get("system_prompt_overrides", {})
    
    # 1. 覆盖检查
    # 匹配精确名称或简单部分匹配（暂时保持简单）
    chat_name = getattr(event, "chat_name", "")
    if chat_name in overrides:
        base_prompt = overrides[chat_name]
    
    # 2. 规范化
    system_prompt = normalize_system_prompt(base_prompt)
    
    # 3. 注入用户画像 (目前仅简单追加)
    if user_profile and isinstance(user_profile, dict):
        profile_text = "\n".join(f"- {k}: {v}" for k, v in user_profile.items())
        if profile_text:
            system_prompt += f"\n\n[User Profile]\n{profile_text}"
            
    # 4. 注入情绪状态
    if emotion:
        # 假设 emotion 是包含 'emotion' (str) 和 'confidence' (float) 的对象
        emotion_str = getattr(emotion, "emotion", str(emotion))
        system_prompt += f"\n\n[Current Emotion]\n{emotion_str}"

    return system_prompt
