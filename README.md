# 微信 AI 自动回复机器人

基于 `wxauto` 驱动已登录的微信 PC 客户端，自动轮询消息并调用 OpenAI 兼容 `/chat/completions` 接口生成回复。

> 📋 **支持环境**：Windows 10/11 + 微信 PC 3.9.x（不支持 4.x）

---

## 📑 目录

- [功能特性](#功能特性)
- [快速开始](#快速开始)
- [项目结构](#项目结构)
- [配置说明](#配置说明)
- [工作流程](#工作流程)
- [聊天记录导出](#聊天记录导出)
- [个性化 Prompt 生成](#个性化-prompt-生成)
- [常见问题](#常见问题)

---

## 功能特性

### 🤖 核心功能
| 功能 | 说明 |
|------|------|
| **多预设 API** | 支持 OpenAI 兼容多家服务，按优先级自动探测可用模型 |
| **文本自动回复** | 消息规范化、群聊 @ 识别、可选发送者前缀 |
| **语音转文字** | 调用微信内置转写（可开关，失败可回退回复） |
| **回复策略** | 流式输出、分段发送、随机延迟、最小回复间隔 |
| **消息合并** | 短时间内连发消息自动合并，避免多次触发模型 |

### 🧠 记忆与上下文
- AI 内存（按轮数/估算 token 裁剪）
- SQLite 记忆库注入（支持 TTL 自动清理）
- **个性化记忆**：用户画像管理（昵称、关系、性格特征）
- **事实记忆**：AI 自动提取重要信息（生日、偏好、计划等）

### 💝 情感识别与人性化
- **情感检测**：支持关键词模式（快速）和 AI 模式（精准）
- **时间感知**：根据时间段调整回复语气
- **对话风格适应**：学习并适应用户的沟通风格
- **关系演进**：基于互动次数自动调整关系亲密度

### ⚙️ 管理与过滤
- 白名单 / 黑名单过滤（公众号/服务号/关键词/会话名）
- `config.py` 热更新，掉线自动重连
- 日志文件自动轮转

---

## 快速开始

### 1️⃣ 环境准备

```
✅ Windows 10/11
✅ 微信 PC 版 3.9.x（已登录并保持运行）
✅ Python 3.8+
✅ 可访问 OpenAI 兼容 API
```

### 2️⃣ 安装依赖

```bash
pip install -r requirements.txt
```

### 3️⃣ 配置密钥

创建 `api_keys.py`（已在 `.gitignore` 中）：

```python
API_KEYS = {
    "default": "YOUR_DEFAULT_KEY",
    "presets": {
        "OpenAI": "YOUR_OPENAI_KEY",
        "Doubao": "YOUR_DOUBAO_KEY",
    },
}
```

### 4️⃣ 运行机器人

```bash
python run.py start
```

---

## 项目结构

```
wechat-chat/
├── run.py               # 项目启动入口 (start/check/setup)
├── requirements.txt     # 依赖清单
├── app/                 # 核心应用代码
│   ├── bot.py           # 机器人主类
│   ├── config.py        # 运行时配置
│   ├── main.py          # 启动逻辑
│   ├── core/            # 核心业务 (AI/Memory/Factory)
│   ├── handlers/        # 消息处理 (Filter/Sender/Convert)
│   └── utils/           # 通用工具
│
├── tools/               # 工具箱
│   ├── chat_exporter/   # 聊天记录导出
│   ├── prompt_gen/      # Prompt 生成器
│   └── wx_db/           # 微信数据库接口
│
├── data/                # 数据目录 (gitignored)
│   ├── api_keys.py      # API 密钥
│   └── chat.db          # 记忆数据库
│
├── scripts/             # 维护脚本
│   ├── check.py         # 环境检测
│   └── setup_wizard.py  # 设置向导
│
└── wxauto_logs/         # 运行日志目录
```

---

## 配置说明

### API 配置（`CONFIG["api"]`）

| 参数 | 说明 |
|------|------|
| `base_url` | OpenAI 兼容接口地址 |
| `api_key` | API 密钥 |
| `model` | 模型名称 |
| `alias` | 模型别名（用于日志） |
| `timeout_sec` | 超时时间（上限 10s） |
| `max_retries` | 重试次数（上限 2 次） |
| `temperature` | 生成温度参数 |
| `max_tokens` | 最大 token 数 |
| `active_preset` | 当前使用的预设名 |
| `presets` | 多预设配置列表 |

**预设探测逻辑**：
1. 将 `active_preset` 排在首位探测
2. 过滤缺少必要配置或密钥为占位符的预设
3. 通过 `/chat/completions` 发送 `ping` 探测，选首个可用预设

### 机器人配置（`CONFIG["bot"]`）

<details>
<summary><b>基础与人设</b></summary>

| 参数 | 说明 |
|------|------|
| `self_name` | 微信昵称，用于群聊 @ 检测 |
| `system_prompt` | 系统提示词，可包含 `{history_context}` |
| `system_prompt_overrides` | 按会话名覆盖系统提示词 |
| `reply_suffix` | 回复后缀，支持 `{alias}` / `{model}` |

</details>

<details>
<summary><b>记忆与上下文</b></summary>

| 参数 | 说明 |
|------|------|
| `context_rounds` | 对话轮数上限 |
| `context_max_tokens` | 估算 token 上限 |
| `history_max_chats` | 内存中最多保留的会话数 |
| `history_ttl_sec` | 内存历史过期时间 |
| `memory_db_path` | SQLite 记忆库路径 |
| `memory_ttl_sec` | 记忆库保留时间 |
| `memory_context_limit` | 每次注入的历史条数 |

</details>

<details>
<summary><b>回复与发送</b></summary>

| 参数 | 说明 |
|------|------|
| `stream_reply` | 启用流式回复（SSE） |
| `reply_chunk_size` | 非流式分段长度 |
| `min_reply_interval_sec` | 最小回复间隔 |
| `random_delay_range_sec` | 随机延迟区间 |
| `merge_user_messages_sec` | 合并连发消息窗口 |

</details>

<details>
<summary><b>群聊与过滤</b></summary>

| 参数 | 说明 |
|------|------|
| `group_reply_only_when_at` | 群聊仅 @ 时回复 |
| `whitelist_enabled` | 启用白名单 |
| `whitelist` | 白名单群聊列表 |
| `ignore_official` | 忽略公众号 |
| `ignore_names` | 按会话名忽略 |

</details>

<details>
<summary><b>个性化与情感</b></summary>

| 参数 | 说明 |
|------|------|
| `personalization_enabled` | 启用个性化功能 |
| `profile_update_frequency` | 画像更新频率 |
| `emotion_detection_enabled` | 启用情感识别 |
| `emotion_detection_mode` | `keywords` 或 `ai` |

</details>

### 日志配置（`CONFIG["logging"]`）

| 参数 | 说明 |
|------|------|
| `level` | 日志等级 |
| `file` | 日志文件路径 |
| `max_bytes` | 单文件大小上限 |
| `backup_count` | 保留文件数量 |

---

## 工作流程

```
┌─────────────────────────────────────────────────────────────┐
│                      机器人工作流程                           │
└─────────────────────────────────────────────────────────────┘

  ┌──────────────┐    探测 API    ┌──────────────┐
  │   启动程序   │ ─────────────▶ │  选择模型预设 │
  └──────────────┘                └──────────────┘
                                        │
                                        ▼
                                ┌──────────────┐
                                │  轮询微信消息 │ ◀──────┐
                                └──────────────┘        │
                                        │               │
                                        ▼               │
                                ┌──────────────┐        │
                                │ 过滤 / 合并  │        │
                                └──────────────┘        │
                                        │               │
                                        ▼               │
                                ┌──────────────┐        │
                                │  调用 AI 模型 │        │
                                └──────────────┘        │
                                        │               │
                                        ▼               │
                                ┌──────────────┐        │
                                │  发送回复    │────────┘
                                └──────────────┘
```

**详细步骤**：
1. 启动后加载配置与日志 → 探测可用 API 预设
2. 轮询微信消息 → 归一化消息结构 → 过滤与合并
3. 语音转文字（可选）→ 组装系统提示词与记忆上下文
4. 调用模型（流式或非流式）→ emoji 策略处理 → 分段发送
5. 写入记忆库 → 记录日志 → 空闲/异常触发重连
6. 定时热重载配置，必要时重新选择模型预设

---

## 聊天记录导出

本项目支持分析微信聊天记录生成个性化 Prompt。需要先将聊天记录从微信导出为 CSV 格式。

### 方式一：内置导出脚本

> 💡 可直接从**已解密的** WeChatMsg 数据库导出，格式与原 WeChatMsg 保持一致。

```bash
python -m tools.chat_exporter.cli --db-dir "E:\wxid_xxx\Msg" --db-version 4 --output-dir chat_exports
```

**常用参数**：

| 参数 | 说明 |
|------|------|
| `--db-dir` | 解密后的微信数据库目录 |
| `--db-version` | 数据库版本（3 或 4） |
| `--output-dir` | 输出目录（默认 `chat_exports`） |
| `--contact` | 按备注/昵称/wxid 精确匹配导出（可重复） |
| `--include-chatrooms` | 包含群聊导出 |
| `--start` / `--end` | 导出时间范围（需成对提供） |

**示例**：
```bash
# 导出所有联系人
python -m tools.chat_exporter.cli --db-dir "E:\wxid_xxx\Msg" --output-dir chat_exports

# 导出指定联系人
python -m tools.chat_exporter.cli --db-dir "E:\wxid_xxx\Msg" --contact "张三" --contact "李四"

# 导出指定时间范围
python -m tools.chat_exporter.cli --db-dir "E:\wxid_xxx\Msg" --start "2024-01-01 00:00:00" --end "2024-12-31 23:59:59"
```

### 方式二：使用 WeChatMsg 工具

[WeChatMsg](https://github.com/LC044/WeChatMsg) 是一个开源的微信聊天记录导出工具：

- ✅ 导出为 CSV / JSON / HTML 格式
- ✅ 支持微信 PC 3.9.x 版本
- ✅ 支持导出图片、语音、视频等附件
- ✅ 数据分析与可视化

**导出步骤**：
1. 下载 [WeChatMsg](https://github.com/LC044/WeChatMsg/releases)
2. 运行 `WeChatMsg.exe`
3. 确保微信 PC 3.9.x 已登录
4. 选择要导出的联系人
5. 选择「导出为 CSV」，保存到 `chat_exports/聊天记录/` 目录

### 目录结构要求

```
chat_exports/
├── 聊天记录/
│   ├── 联系人A(wxid_xxx)/
│   │   └── 联系人A.csv
│   ├── 联系人B(wxid_yyy)/
│   │   └── 联系人B.csv
│   └── ...
└── top10_prompts_summary.json  # 生成的个性化 Prompt 汇总
```

> ⚠️ **注意**：`chat_exports/` 目录包含敏感的聊天记录，已加入 `.gitignore`，请勿提交到版本库。

---

## 个性化 Prompt 生成

使用 Prompt 生成器分析聊天记录，为每个联系人生成独特的系统提示词，让 AI 回复更贴近你的真实聊天风格。

### 功能

- 📊 自动统计每个联系人的消息数量
- 🔝 找出聊天最多的 Top N 联系人（默认 10）
- 🤖 调用 AI 分析聊天风格并生成个性化 Prompt
- 💾 输出结果保存为 JSON 和 Python 格式

### 使用方法

```bash
# 完整执行（需要 AI API）
python -m tools.prompt_gen.generator

# 仅统计，不调用 AI
python -m tools.prompt_gen.generator --dry-run

# 只处理 Top 5 联系人
python -m tools.prompt_gen.generator --top 5

# 限制每个联系人分析的消息数量
python -m tools.prompt_gen.generator --limit 100
```

### 工作原理

```
                    ┌──────────────────────────────────────┐
                    │          Prompt 生成流程              │
                    └──────────────────────────────────────┘

  ┌──────────────┐                        ┌──────────────┐
  │  CSV 聊天记录 │ ──────扫描统计───────▶ │  Top N 排序  │
  └──────────────┘                        └──────────────┘
                                                 │
                                                 ▼
                                         ┌──────────────┐
                                         │  AI 风格分析 │
                                         └──────────────┘
                                                 │
                              ┌──────────────────┼──────────────────┐
                              ▼                  ▼                  ▼
                    ┌──────────────┐   ┌──────────────────┐  ┌────────────┐
                    │ summary.json │   │ prompt_overrides │  │  prompt.txt │
                    │   (汇总)     │   │     .py (集成)   │  │  (单个)    │
                    └──────────────┘   └──────────────────┘  └────────────┘
```

1. 扫描 `chat_exports/聊天记录/` 下的所有联系人目录
2. 解析 CSV 文件，统计文本消息数量
3. 筛选出 Top N 联系人（排除系统账号）
4. 对每个联系人，取最近的聊天记录发送给 AI 分析
5. AI 生成个性化的 `system_prompt`，包含：
   - 称呼方式、用词偏好、句子风格
   - 表情习惯、关系亲疏
   - 场景化回复建议
6. 结果保存到多个位置：
   - `chat_exports/top10_prompts_summary.json`
   - `prompt_overrides.py`
   - 各联系人目录下的 `system_prompt.txt`

### 集成到机器人

**方式一**：直接在 `config.py` 中配置

```python
"system_prompt_overrides": {
    "联系人A": "生成的 Prompt 内容...",
    "联系人B": "生成的 Prompt 内容...",
},
```

**方式二**：导入生成的覆盖文件

```python
from prompt_overrides import PROMPT_OVERRIDES
# 然后在 config.py 中使用 PROMPT_OVERRIDES
```

---

## 性能优化

本项目采用了多项性能优化措施：

| 类型 | 优化措施 |
|------|---------|
| **内存** | `@dataclass(slots=True)` 减少内存占用 |
| **计算** | `@lru_cache(maxsize=1024)` 缓存 Token 估算 |
| **查找** | `frozenset` 实现 O(1) 成员检查 |
| **数据库** | WAL 模式 + 256MB mmap + 多索引加速 |
| **连接** | HTTP 连接池复用（最大连接数 20） |

---

## 常见问题

<details>
<summary><b>❓ 无法连接微信或导入 wxauto 失败</b></summary>

确认微信 PC 版为 3.9.x 且已登录运行；4.x 不支持。

</details>

<details>
<summary><b>❓ 群聊不回复</b></summary>

检查以下配置：
- `whitelist_enabled` / `whitelist`
- `group_reply_only_when_at`
- `self_name`
- `filter_mute`

</details>

<details>
<summary><b>❓ 预设探测失败</b></summary>

确认 `base_url` / `model` / `api_key` 配置正确，或设置 `allow_empty_key=True`（仅在无需鉴权时使用）。

</details>

<details>
<summary><b>❓ 语音转文字不可用</b></summary>

需要微信客户端支持语音转文字；可关闭 `voice_to_text` 或设置失败回退回复。

</details>

<details>
<summary><b>❓ Prompt 生成失败</b></summary>

确认：
- `chat_exports/聊天记录/` 目录结构正确
- CSV 文件编码为 UTF-8
- API 配置正确且可用

</details>

---

## 运行产物与注意事项

- 运行后会生成 `wxauto_logs/` 日志目录与 `chat_history.db` 记忆库
- 建议将 `chat_history.db` 加入 `.gitignore`，避免提交敏感对话内容
- 可通过 `memory_ttl_sec` 控制保留时长
- 自动化存在风险，建议使用小号测试并合理设置回复频率

---

## 测试

当前仓库未提供测试用例。如需添加：

```bash
# 在 tests/ 目录创建测试
python -m unittest discover -s tests
```

---

## 免责声明

> ⚠️ 自动化控制微信存在账号风险，请自行评估并合理使用。

---

<div align="center">

**Made with ❤️ for WeChat Automation**

</div>
</CodeContent>
<parameter name="EmptyFile">false
