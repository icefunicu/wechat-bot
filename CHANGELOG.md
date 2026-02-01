# Changelog

All notable changes to this project will be documented in this file.

## [1.0.0] - 2025-02-01

### 🎉 Initial Release

这是微信 AI 自动回复机器人的第一个正式版本。

#### ✨ 主要功能
- **微信集成**：基于 `wxauto` 深度集成微信 PC 版 (3.9.x)，支持消息实时监听与自动回复。
- **多模型支持**：内置 OpenAI、DeepSeek、Doubao (豆包)、Moonshot (Kimi) 等多家大模型预设，支持自动轮询切换。
- **智能对话**：
  - 支持上下文记忆 (SQLite 持久化)。
  - 支持用户画像与个性化记忆。
  - 支持情感识别与动态语气调整。
- **桌面客户端**：基于 Electron 的可视化控制台，支持配置管理、状态监控和日志查看。
- **安全机制**：
  - 支持黑白名单过滤。
  - 内置防封号策略 (随机延迟、回复间隔限制)。
  - 敏感信息 (API Key) 分离存储。

#### 🛠️ 工具链
- `chat_exporter`: 支持直接解密导出微信聊天记录为 CSV。
- `prompt_gen`: 基于历史聊天记录生成个性化 System Prompt。
- `web_api`: 提供 HTTP 接口供二次开发。

#### 📦 部署
- 支持 Windows 10/11。
- 提供源码运行 (`python run.py`) 和 Electron 客户端两种启动方式。
