# 微信 AI 自动回复机器人（wxauto）

仅支持 Windows。通过 wxauto 驱动已登录的微信 PC 客户端，实现自动回复。

## 环境要求

- Windows 已安装并登录微信 PC 版 3.9.x（不支持 4.x）
- Python 3.8+
- Git（用于从 GitHub 安装 wxauto）

## 快速开始
1) 安装依赖：
```
pip install -r requirements.txt
```
2) 修改 `config.py`（API、白名单等）。
3) 运行程序：
```
python main.py
```

## 配置说明（config.py）

- `api.base_url`：OpenAI 兼容 API 的接口地址
- `api.api_key`：API 密钥
- `api.model`：模型名称
- `api.alias`：模型别名（用于日志与 `{alias}`）
- `api.active_preset`：优先尝试的预设名称
- `api.presets`：预设列表（按顺序探测并使用可用的）
- `api.timeout_sec`/`api.max_retries`: timeout and retry settings.
- `api.temperature`/`api.max_tokens`/`api.max_completion_tokens`: generation controls.
- `api.reasoning_effort`: optional reasoning level (model-dependent).

- `bot.self_name`：你的微信昵称（用于 @ 检测）
- `bot.system_prompt`：系统提示词
- `bot.reply_suffix`：每条回复末尾追加内容，支持 `{alias}` / `{model}`
- `bot.context_rounds`：对话记忆轮数
- `bot.merge_user_messages_sec`：合并连续消息的等待窗口（秒），0 表示不合并
- `bot.merge_user_messages_max_wait_sec`：合并连续消息的最长等待（秒），0 表示不限制
- `bot.group_reply_only_when_at`：群聊仅在被 @ 时回复
- `bot.whitelist_enabled`：开启后仅对白名单群聊自动回复（私聊不受影响）
- `bot.whitelist`：允许自动回复的群聊名称列表
- `bot.emoji_policy`: emoji handling (wechat/strip/keep/mixed).
- `bot.context_max_tokens`: cap the context by estimated tokens.
- `bot.stream_reply`: enable streaming replies.
- `bot.reply_chunk_size`/`bot.reply_chunk_delay_sec`: chunked sending controls.

## 热加载

- `config.py` 会按间隔自动重新加载（`bot.config_reload_sec`）。
- 开启 `bot.reload_ai_client_module` 可热加载 `ai_client.py`。
- `bot.reload_ai_client_on_change` can re-probe presets after config updates.
- `main.py` 的改动仍需重启程序。

## 行为与限制

- 仅处理文本消息，图片/语音/文件会被忽略。
- 对话上下文只保存在内存中，重启后不保留。
- 群聊 @ 检测依赖 `bot.self_name` 的准确性。

## 风险提示

自动化有风险，建议用小号测试并控制回复频率，避免账号限制。

## Testing

Run unit tests (no WeChat client or network calls required):
```
python -m unittest discover -s tests
```
