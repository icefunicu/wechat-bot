# 微信 AI 自动回复机器人（wxauto）

基于 `wxauto` 驱动已登录的微信 PC 客户端，自动轮询消息并调用 OpenAI 兼容 `/chat/completions` 接口生成回复。仅支持 Windows，推荐配合微信 PC 3.9.x 使用。

## 功能特性

- 多预设 API 探测与自动选择：支持 OpenAI 兼容多家服务，按优先级探测可用模型
- 文本消息自动回复：消息规范化、群聊 @ 识别、可选发送者前缀
- 语音转文字：调用微信内置“语音转文字”（可开关，失败可回退回复）
- 回复策略丰富：流式输出、分段发送、随机延迟、最小回复间隔
- 消息合并：短时间内连发消息自动合并，避免多次触发模型
- 记忆与上下文：AI 内存（按轮数/估算 token 裁剪）+ SQLite 记忆库注入（支持 TTL 自动清理）
- 过滤与白名单：忽略公众号/服务号/关键词/会话名，群聊白名单与 @ 控制
- 热更新与重连：`config.py` 定时热重载，可重载 AI 客户端模块，掉线自动重连
- 日志记录：可选记录消息/回复内容，日志文件自动轮转

## 运行环境

- Windows 10/11
- 微信 PC 版 3.9.x（不支持 4.x）
- Python 3.8+
- 已登录并保持运行的微信 PC 客户端
- 能访问配置的 OpenAI 兼容 API

## 安装与运行

1) 安装依赖
```bash
pip install -r requirements.txt
```

2) 配置 `config.py` 与 `api_keys.py`（见下文）

3) 运行
```bash
python main.py
```

## 项目结构

- `main.py`：入口与主循环，连接微信、轮询消息、过滤与归一化、发送回复、热重载与重连
- `ai_client.py`：OpenAI 兼容 `/chat/completions` 客户端（httpx 异步 + 流式）
- `memory.py`：SQLite 记忆库（按会话存储用户/助手消息）
- `config.py`：运行时配置（API 预设、机器人行为、日志）
- `api_keys.py`：可选密钥文件（已在 `.gitignore` 中）
- `requirements.txt`：依赖清单
- `wxauto_logs/`：运行日志目录（自动创建）

## 配置详解

### API 配置（`CONFIG["api"]`）

- `base_url`：OpenAI 兼容接口地址
- `api_key`：API 密钥（占位符会被视为未配置）
- `model`：模型名称
- `alias`：模型别名（日志与 `{alias}` 占位符）
- `timeout_sec` / `max_retries`：超时与重试（上限分别为 10s / 2 次）
- `temperature` / `max_tokens` / `max_completion_tokens`：生成参数
- `reasoning_effort`：模型推理强度（如支持）
- `allow_empty_key`：允许空 key（仅在本地网关或无需鉴权时使用）
- `active_preset` / `presets`：多预设配置与优先级

预设探测逻辑：
1. 将 `active_preset` 排在首位进行探测
2. 过滤掉缺少 `base_url` / `model` 或密钥为占位符的预设
3. 通过 `/chat/completions` 发送 `ping` 探测，选首个可用的预设

### 密钥文件（`api_keys.py`）

`config.py` 会尝试加载 `api_keys.py`，并覆盖默认 key 或指定预设的 key。建议把真实密钥放这里，避免提交到仓库。

示例：
```python
API_KEYS = {
    "default": "YOUR_DEFAULT_KEY",
    "presets": {
        "OpenAI": "YOUR_OPENAI_KEY",
        "Doubao": "YOUR_DOUBAO_KEY",
    },
}
```

### 机器人配置（`CONFIG["bot"]`）

基础与人设：
- `self_name`：微信昵称，用于群聊 @ 检测
- `system_prompt`：系统提示词，可包含 `{history_context}`
- `system_prompt_overrides`：按会话名覆盖系统提示词
- `reply_suffix`：回复后缀，支持 `{alias}` / `{model}`

记忆与上下文：
- `context_rounds`：对话轮数上限
- `context_max_tokens`：估算 token 上限（优先于轮数裁剪）
- `history_max_chats`：内存中最多保留的会话数
- `history_ttl_sec`：内存历史过期时间
- `memory_db_path`：SQLite 记忆库路径
- `memory_ttl_sec`：SQLite 记忆库保留时间
- `memory_cleanup_interval_sec`：SQLite 记忆库清理间隔
- `memory_context_limit`：每次注入的历史条数（0 表示禁用）
- `memory_seed_on_first_reply`：首次回复时自动抓取最近聊天记录
- `memory_seed_limit`：首次抓取的历史条数上限（0 表示禁用）
- `memory_seed_load_more`：额外向上加载历史的次数
- `memory_seed_load_more_interval_sec`：加载历史的滚动间隔（秒）
- `memory_seed_group`：是否对群聊也执行首次历史抓取
- `history_log_interval_sec`：周期性输出历史统计日志

回复与发送：
- `stream_reply`：启用流式回复（SSE）
- `stream_buffer_chars` / `stream_chunk_max_chars`：流式缓冲阈值与最大分段长度
- `reply_chunk_size` / `reply_chunk_delay_sec`：非流式分段发送与间隔
- `min_reply_interval_sec`：最小回复间隔
- `random_delay_range_sec`：随机延迟区间（模拟人工）
- `merge_user_messages_sec` / `merge_user_messages_max_wait_sec`：合并连发消息窗口
- `send_exact_match`：发送到精确匹配会话名
- `send_fallback_current_chat`：发送失败时回退到当前聊天
- `max_concurrency`：并发处理上限

群聊与过滤：
- `group_reply_only_when_at`：群聊仅在被 @ 时回复
- `group_include_sender`：群聊消息加入发送者前缀
- `whitelist_enabled` / `whitelist`：仅对白名单群聊回复
- `ignore_official` / `ignore_service`：忽略公众号/服务号
- `ignore_names` / `ignore_keywords`：按会话名/关键词过滤
- `filter_mute`：过滤免打扰会话

语音与表情：
- `voice_to_text`：语音转文字开关
- `voice_to_text_fail_reply`：转写失败时的回复
- `emoji_policy`：`wechat` / `strip` / `keep` / `mixed`
- `emoji_replacements`：自定义 emoji 替换表

热更新与重连：
- `config_reload_sec`：`config.py` 热重载间隔
- `keepalive_idle_sec`：空闲超时触发重连
- `reconnect_max_retries` / `reconnect_backoff_sec` / `reconnect_max_delay_sec`
- `reload_ai_client_on_change`：配置变更后重新探测预设
- `reload_ai_client_module`：检测到 `ai_client.py` 变化时热重载

### 日志配置（`CONFIG["logging"]`）

- `level`：日志等级
- `file`：日志文件路径（留空仅控制台）
- `max_bytes` / `backup_count`：文件轮转设置
- `log_message_content` / `log_reply_content`：是否记录消息/回复内容

## 工作流程概览

1) 启动后加载配置与日志 → 探测可用 API 预设  
2) 轮询微信消息 → 归一化消息结构 → 过滤与合并  
3) 语音转文字（可选）→ 组装系统提示词与记忆上下文  
4) 调用模型（流式或非流式）→ emoji 策略处理 → 分段发送  
5) 写入记忆库 → 记录日志 → 空闲/异常触发重连  
6) 定时热重载配置，必要时重新选择模型预设

## 运行产物与注意事项

- 运行后会生成 `wxauto_logs/` 日志目录与 `chat_history.db` 记忆库
- 建议将 `chat_history.db` 加入 `.gitignore`，避免提交敏感对话内容；可通过 `memory_ttl_sec` 控制保留时长
- 自动化存在风险，建议使用小号测试并合理设置回复频率

## 常见问题

1) **无法连接微信或导入 wxauto 失败**  
请确认微信 PC 版为 3.9.x 且已登录运行；4.x 不支持。

2) **群聊不回复**  
检查 `whitelist_enabled` / `whitelist`、`group_reply_only_when_at`、`self_name`、`filter_mute`。

3) **预设探测失败**  
确认 `base_url` / `model` / `api_key` 配置正确，或设置 `allow_empty_key=True` 仅在无需鉴权时使用。

4) **语音转文字不可用**  
需要微信客户端支持语音转文字；可关闭 `voice_to_text` 或设置失败回退回复。

## 测试

当前仓库未提供测试用例。如你新增 `tests/`，可使用：
```bash
python -m unittest discover -s tests
```

## 免责声明

自动化控制微信存在账号风险，请自行评估并合理使用。
