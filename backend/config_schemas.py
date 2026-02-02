from typing import List, Dict, Optional, Any, Union, Literal
from pydantic import BaseModel, Field, validator

class PresetConfig(BaseModel):
    name: str
    alias: str
    base_url: str
    api_key: str
    model: str
    timeout_sec: int = 10
    max_retries: int = 2
    temperature: float = 0.6
    max_tokens: int = 512
    max_completion_tokens: Optional[int] = None
    reasoning_effort: Optional[str] = None
    allow_empty_key: bool = False

class ApiConfig(BaseModel):
    base_url: str = 'https://api.openai.com/v1'
    api_key: str = "YOUR_API_KEY"
    model: str = 'gpt-4o-mini'
    alias: str = '小欧'
    timeout_sec: int = 8
    max_retries: int = 1
    temperature: float = 0.6
    max_tokens: int = 512
    max_completion_tokens: Optional[int] = None
    reasoning_effort: Optional[str] = None
    allow_empty_key: bool = False
    active_preset: str = 'Doubao'
    presets: List[PresetConfig] = Field(default_factory=list)

class BotConfig(BaseModel):
    # Identity
    self_name: str = '知有'
    system_prompt: str = ""
    system_prompt_overrides: Dict[str, str] = Field(default_factory=dict)
    
    # Reply format
    reply_suffix: str = "\n （🤖💬 AI代言中～）"
    emoji_policy: Literal['wechat', 'strip', 'keep', 'mixed'] = 'mixed'
    emoji_replacements: Dict[str, str] = Field(default_factory=dict)
    
    # Quoting
    reply_quote_mode: Literal['wechat', 'text', 'none'] = "wechat"
    reply_quote_template: str = "引用：{content}\n"
    reply_quote_max_chars: int = 120
    reply_quote_timeout_sec: float = 5.0
    reply_quote_fallback_to_text: bool = True
    
    # Voice
    voice_to_text: bool = True
    voice_to_text_fail_reply: str = ""
    
    # Memory
    memory_db_path: str = "data/chat_memory.db"
    memory_context_limit: int = 12
    memory_ttl_sec: Optional[float] = None
    memory_cleanup_interval_sec: float = 0.0
    memory_seed_on_first_reply: bool = True
    memory_seed_limit: int = 30
    memory_seed_load_more: int = 0
    memory_seed_load_more_interval_sec: float = 0.3
    memory_seed_group: bool = False
    
    # Context
    context_rounds: int = 4
    context_max_tokens: int = 1200
    history_max_chats: int = 120
    history_ttl_sec: Optional[float] = None
    history_log_interval_sec: float = 300.0
    
    # Polling & Delay
    poll_interval_sec: float = 0.05
    poll_interval_min_sec: float = 0.05
    poll_interval_max_sec: float = 1.0
    poll_interval_backoff_factor: float = 1.2
    min_reply_interval_sec: float = 0.1
    random_delay_range_sec: List[float] = Field(default_factory=lambda: [0.1, 0.3])
    
    # Concurrency
    max_concurrency: int = 5
    keepalive_idle_sec: float = 0.0
    
    # Merging
    merge_user_messages_sec: float = 0.0
    
    # Filtering
    filter_mute: bool = False
    
    # Other
    reload_ai_client_on_change: bool = True
    config_reload_sec: float = 2.0

class LoggingConfig(BaseModel):
    level: str = "INFO"
    file: str = "wxauto_logs/bot.log"
    max_bytes: int = 10 * 1024 * 1024
    backup_count: int = 5
    format: Literal['text', 'json'] = 'text'

class AppConfig(BaseModel):
    api: ApiConfig
    bot: BotConfig
    logging: LoggingConfig
