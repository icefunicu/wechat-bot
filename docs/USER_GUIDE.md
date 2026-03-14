# 使用手册

本手册负责承载详细的使用、配置、运行与排障说明。  
README 只保留仓库首页所需的高层信息，这份文档负责逐步操作。

## 目录

- [1. 环境要求](#1-环境要求)
- [2. 安装依赖](#2-安装依赖)
- [3. 首次配置](#3-首次配置)
- [4. 启动前检查](#4-启动前检查)
- [5. 启动方式](#5-启动方式)
- [6. 验证是否正常工作](#6-验证是否正常工作)
- [7. LangChain / RAG 配置](#7-langchain--rag-配置)
- [8. 配置说明](#8-配置说明)
- [9. 常见问题](#9-常见问题)
- [10. 开发与测试](#10-开发与测试)

## 1. 环境要求

运行前请确认：

- Windows 10 或 Windows 11
- 微信 PC `3.9.x`
- Python `3.9+`
- Node.js `16+`
- 微信客户端已登录

限制：

- 当前项目不支持微信 `4.x`
- 不支持 Linux / macOS 直接运行微信自动化
- 运行时应保持微信客户端处于可访问状态

## 2. 安装依赖

### 2.1 克隆仓库

```bash
git clone https://github.com/byteD-x/wechat-bot.git
cd wechat-bot
```

### 2.2 安装 Python 依赖

```bash
pip install -r requirements.txt
```

这一步会安装：

- Quart / Hypercorn
- wxauto 相关后端依赖
- ChromaDB
- LangChain / LangGraph / LangSmith
- 测试依赖

### 2.3 安装桌面端依赖

```bash
npm install
```

这一步会安装 Electron 桌面端依赖。

## 3. 首次配置

推荐优先使用桌面界面配置。

### 3.1 打开桌面设置页

```bash
npm run dev
```

### 3.2 配置模型

在设置页里完成：

1. 选择一个模型预设
2. 填写 API Key
3. 选择模型名称
4. 点击测试连接
5. 保存配置

### 3.3 配置文件优先级

运行时主要会读取以下配置来源：

1. `data/config_override.json`
2. `data/api_keys.py`
3. `prompt_overrides.py`
4. `backend/config.py`

建议：

- 默认配置放在 `backend/config.py`
- 真实密钥放在 `data/api_keys.py`
- 界面保存产生的覆写会进入 `data/config_override.json`

## 4. 启动前检查

运行环境自检：

```bash
python run.py check
```

建议至少确认：

- Python 依赖安装完成
- Node.js / Electron 依赖安装完成
- 微信版本满足要求
- 配置文件可读

## 5. 启动方式

### 5.1 桌面模式

```bash
npm run dev
```

适合：

- 在 GUI 中配置参数
- 查看状态与日志
- 通过设置页切换模型预设

### 5.2 无头机器人模式

```bash
python run.py start
```

适合：

- 已完成配置
- 只需要机器人主循环
- 不需要桌面控制台

### 5.3 Web API 模式

```bash
python run.py web
```

适合：

- 单独运行后端 API
- 调试接口
- 与 Electron 或外部控制端联动

## 6. 验证是否正常工作

建议按以下顺序验证：

1. 打开设置页，确认当前预设和 Key 已配置
2. 访问状态页，确认运行状态正常
3. 给允许回复的联系人发送一条简单文本
4. 查看 `data/logs/bot.log`
5. 检查 API `/api/status` 与 `/api/config`

如果没有回复，优先检查：

- 微信是否仍是 `3.9.x`
- 当前会话是否被白名单或过滤规则限制
- API Key 是否有效
- 激活预设是否可连接

## 7. LangChain / RAG 配置

### 7.1 LangChain Runtime

`agent` 分区用于控制当前主运行时。

常用字段：

```python
"agent": {
    "enabled": True,
    "streaming_enabled": True,
    "graph_mode": "state_graph",
    "retriever_top_k": 3,
    "retriever_score_threshold": 1.0,
    "embedding_cache_ttl_sec": 300.0,
    "background_fact_extraction_enabled": True,
    "emotion_fast_path_enabled": True,
    "langsmith_enabled": False,
    "langsmith_project": "wechat-chat",
}
```

建议：

- 初次使用保持默认
- 性能调优时重点调整 `retriever_top_k`、阈值和缓存 TTL
- 开启 LangSmith 前先确认你接受外部 tracing

### 7.2 运行期向量记忆

相关开关位于 `bot`：

```python
"rag_enabled": True
```

作用：

- 对当前聊天中的历史消息做向量召回
- 适合补充近期语义上下文

### 7.3 导出语料 RAG

相关字段：

```python
"export_rag_enabled": True,
"export_rag_dir": "data/chat_exports/聊天记录",
"export_rag_top_k": 3,
"export_rag_max_chunks_per_chat": 500,
```

作用：

- 从导出的真实聊天中召回你过去的表达风格
- 更偏“风格模仿”，不是事实数据库

使用方式：

1. 导出聊天记录
2. 放到 `data/chat_exports/聊天记录/...`
3. 启动机器人或等待自动增量导入

相关命令：

```bash
python -m tools.chat_exporter.cli
python -m tools.prompt_gen.generator
```

## 8. 配置说明

### 8.1 `api`

负责模型与提供方：

- `base_url`
- `api_key`
- `model`
- `embedding_model`
- `active_preset`
- `presets`
- `timeout_sec`
- `max_retries`

### 8.2 `bot`

负责机器人行为：

- 回复格式与引用
- 轮询与并发
- 记忆与上下文
- 群聊规则
- 控制命令
- 情绪识别
- RAG 开关

### 8.3 `agent`

负责 LangChain/LangGraph 运行时：

- 主链路开关
- 流式输出
- Retriever 参数
- Embedding 缓存
- 后台事实提取
- LangSmith tracing

### 8.4 `logging`

负责日志：

- 日志级别
- 日志文件
- 轮转大小与数量
- 是否记录消息正文

## 9. 常见问题

### 9.1 `pip` 或 `python` 不存在

处理：

1. 重新安装 Python
2. 勾选 `Add Python to PATH`
3. 重开终端

### 9.2 `npm install` 失败

处理：

1. 检查 Node.js 版本
2. 清理 `node_modules`
3. 重新执行 `npm install`

### 9.3 机器人不回复

优先排查：

- 微信是否为 `3.9.x`
- 微信是否保持登录
- 当前会话是否被过滤
- 是否开启白名单并漏配会话
- 模型连接是否成功
- 日志中是否有请求错误

### 9.4 模型能连通但 RAG 没效果

优先排查：

- `rag_enabled` 或 `export_rag_enabled` 是否开启
- embedding 模型是否可用
- 导出目录是否存在有效语料
- `retriever_top_k` 是否过低

### 9.5 LangSmith 不生效

优先排查：

- `agent.langsmith_enabled` 是否开启
- LangSmith API Key 是否已配置
- 网络是否允许访问 LangSmith 服务

## 10. 开发与测试

### 10.1 常用命令

```bash
# 安装依赖
pip install -r requirements.txt
npm install

# 桌面开发模式
npm run dev

# 启动机器人
python run.py start

# 启动 Web API
python run.py web

# 环境检查
python run.py check
```

### 10.2 测试

```bash
python -m unittest discover -s tests
```

当前测试覆盖重点包括：

- API 路由
- Bot 生命周期
- Export RAG
- Agent Runtime

### 10.3 敏感数据注意事项

不要提交以下内容：

- 真实 API Key
- `data/chat_exports/`
- `data/`
- `data/logs/`
- 解密后的微信数据库
