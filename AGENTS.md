# 仓库指南

## 项目结构与模块组织
- `run.py`: 统一入口点（启动/检查/设置/Web服务）。
- `requirements.txt`: Python 运行时依赖。
- `package.json`: Electron/Node.js 依赖。
- `backend/`: 主应用程序包 (Python)。
  - `bot.py`: 主 `WeChatBot` 类，控制生命周期。
  - `main.py`: 异步入口点，初始化机器人。
  - `config.py`: 运行时配置逻辑。
  - `api.py`: 基于 Quart 的 Web API 服务器。
  - `core/`: 核心业务逻辑（AI 客户端、记忆、工厂模式、情感分析）。
  - `handlers/`: 消息处理程序（过滤器、发送器、转换器）。
  - `utils/`: 通用工具（日志、配置加载器、常用工具）。
- `src/`: Electron 前端源码。
  - `main/`: Electron 主进程。
  - `renderer/`: Web 界面 (HTML/JS/CSS)。
- `tools/`: 独立工具。
  - `chat_exporter/`: CSV 导出逻辑（支持直接读取数据库）。
  - `prompt_gen/`: 个性化提示生成器。
  - `wx_db/`: 微信数据库接口（解密与解析）。
- `data/`: 数据目录（API 密钥、数据库 - gitignored）。
- `scripts/`: 维护脚本（安装向导、检查）。
- `wxauto_logs/`: 运行时日志。

## 构建、测试与开发命令
- `pip install -r requirements.txt`: 安装 Python 依赖。
- `npm install`: 安装 Electron 依赖。
- `npm run dev`: 在开发模式下启动桌面客户端（及后端）。
- `python run.py start`: 运行机器人（无头模式）。
- `python run.py web`: 运行 Web API 服务器。
- `python run.py check`: 检查环境和依赖。
- `python run.py setup`: 运行配置向导。
- `python -m unittest discover -s tests`: 运行单元测试。
- `.\build.bat`: 将项目构建为 Windows 可执行安装程序 (dist/)。
- 应用程序仅针对 Windows + WeChat PC 3.9.x (不支持 4.x)。请保持客户端登录并运行。
- `backend/config.py` 的更改会被轮询并热重载；逻辑更改需要重启。

## 配置说明
- `api`: 支持 `presets`（预设）+ `active_preset`（激活预设）；包含 `base_url`、`model`、`api_key`、超时、重试、`temperature`、`max_tokens`/`max_completion_tokens` 以及可选的 `reasoning_effort`。
- `bot`: 回复后缀、表情策略 (`wechat`/`strip`/`keep`/`mixed`)、上下文/历史限制、轮询/延迟设置、保活/重连、群回复规则（`self_name`、`group_reply_only_when_at`、白名单、忽略列表）以及发送回退。
- `bot` (个性化): `personalization_enabled`、`profile_update_frequency`、`remember_facts_enabled`、`max_context_facts`、`profile_inject_in_prompt`。
- `bot` (情感): `emotion_detection_enabled`、`emotion_detection_mode` (keywords/ai)、`emotion_inject_in_prompt`、`emotion_log_enabled`。
- `logging`: 级别/文件/轮换（默认 `wxauto_logs/bot.log`）。

## 已实现功能
- 通过 `wxauto` 集成 WeChat PC 3.9.x，具有轮询循环和重连退避机制。
- 私聊/群聊消息规范化，@-mention 检测，以及群上下文中可选的发送者前缀。
- 仅处理文本；非文本消息基于消息类型标记被忽略。
- 每个聊天的内存对话历史记录，具有最大轮数、TTL 和总聊天上限。
- 多预设 API 探测/选择，具有占位符密钥检测和可选的空密钥允许。
- `config.py`（以及可选的 `ai_client.py`）的热重载，支持运行时设置更新。
- 表情清理策略和可配置的回复后缀模板。
- 安全节流：随机拟人延迟和最小回复间隔。
- 过滤器：忽略官方/服务号、命名聊天、关键词、静音过滤的聊天，以及可选的白名单群组。
- **用户画像管理**：昵称、关系、性格和上下文事实存储。
- **情感检测**：基于关键词和基于 AI 的情感分析，具有可配置模式。
- **拟人化**：时间感知提示、对话风格适应、情感趋势分析和关系演进。
- **个性化提示生成**：分析导出的聊天记录，生成模仿用户对话风格的每位联系人系统提示。
- **Web API & 仪表板**：通过 HTTP/Electron 监控状态、发送消息和管理配置。前端采用 `StateManager` + `EventBus` 架构实现响应式 UI。

## 性能优化
- `EmotionResult` 使用 `@dataclass(slots=True)` 以减少内存占用。
- token 估算使用 `@lru_cache(maxsize=1024)` 避免冗余计算。
- 使用 `frozenset` 进行 O(1) 成员检查（情感关键词、消息类型标记、允许的角色）。
- `MemoryManager` 支持上下文管理器，用于自动资源清理。

## 数据工作流
1. **导出聊天记录**：使用内置 CLI (`python -m tools.chat_exporter.cli`) 将微信聊天导出为 CSV 格式（支持直接 DB 解密）。
2. **组织文件**：将导出文件放置在 `chat_exports/聊天记录/<ContactName(wxid)>/<ContactName>.csv`（导出器自动处理）。
3. **生成提示**：运行 `python -m tools.prompt_gen.generator` 分析聊天并生成个性化提示。
4. **审查输出**：检查 `chat_exports/top10_prompts_summary.json` 中的生成提示。
5. **集成**：将提示复制到 `config.py` 的 `system_prompt_overrides` 或使用 `prompt_overrides.py`。

## 代码风格与命名约定
- Python，4 空格缩进；保持类型提示和文档字符串与现有模块一致。
- 命名：函数/变量使用 `snake_case`，类使用 `CapWords`，常量使用 `UPPER_SNAKE_CASE`。
- 没有配置格式化程序或 linter；保持更改小且可读。

## 测试指南
- 单元测试位于 `tests/` 中，使用标准库 `unittest` 运行器。
- 运行测试：`python -m unittest discover -s tests`。

## 提交与 Pull Request 指南
- 此 checkout 没有 `.git` 历史记录，因此没有既定的提交消息约定。
- 使用简短的命令式主题（例如，“Add retry backoff”），并在正文中解释配置更改。
- PR 应包括：摘要、链接的问题（如果有）、如何验证更改以及任何配置或日志影响。

## 安全与配置提示
- `config.py` 包含 API 密钥；在版本控制中保留占位符，避免共享真实机密。
- `wxauto_logs/` 中的日志可能包含消息内容；将其视为敏感信息，不要提交。
- `chat_exports/` 包含敏感聊天记录；保持 gitignore 并不共享。
