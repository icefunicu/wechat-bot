# Windows 发布与更新说明

## 当前发布方式

项目已经配置为通过 GitHub Releases 发布，仓库固定为：

- `owner`: `byteD-x`
- `repo`: `wechat-bot`

Electron 打包配置位于 [electron-builder.yml](e:/Project/wechat-chat/electron-builder.yml)，更新检查使用 `electron-updater` 读取构建产物中的 `app-update.yml`。

## 构建产物

执行 `npm run build:release` 或 `.\build.bat` 后，会在 `release/` 目录生成：

- `微信AI助手-<version>-portable-x64.exe`
- `微信AI助手-<version>-setup-x64.exe`
- `微信AI助手-<version>-installer-x64.msi`
- `latest.yml`
- `*.blockmap`

实际发布时已统一为 ASCII 文件名，当前产物模式为：

- `wechat-ai-assistant-portable-<version>-x64.exe`
- `wechat-ai-assistant-setup-<version>.exe`
- `wechat-ai-assistant-installer-<version>-x64.msi`

说明：

- `portable-x64.exe` 用于免安装分发。
- `setup-x64.exe` 是 NSIS 安装包，也是 Windows 标准自动更新目标。
- `installer-x64.msi` 是 MSI 安装包，适合分发安装。
- `latest.yml` 和 `blockmap` 由 `electron-builder` 自动生成，GitHub 更新检查依赖它们。

## 应用内更新行为

桌面端现在会：

- 启动后自动检查更新
- 运行期间定时轮询更新
- 在发现新版本时显示系统通知
- 在“设置 -> 应用更新”中支持手动检查和跳转下载

注意：

- `NSIS` 是 Windows 官方支持的自动更新目标。
- `MSI` 安装用户也能收到“发现新版本”的提醒，但当前动作为打开 GitHub Releases 页面下载更新，不做应用内静默升级。

## 本地构建

只构建，不发布：

```powershell
npm run build:release
```

或：

```powershell
.\build.bat
```

## 发布到 GitHub Releases

先准备 GitHub Token：

```powershell
$env:GH_TOKEN="你的 GitHub Token"
```

然后执行：

```powershell
npm run publish:github
```

这会把以下文件上传到 GitHub Release：

- `微信AI助手-<version>-portable-x64.exe`
- `微信AI助手-<version>-setup-x64.exe`
- `微信AI助手-<version>-installer-x64.msi`
- `latest.yml`
- `*.blockmap`

对应当前配置，实际上传文件名为：

- `wechat-ai-assistant-portable-<version>-x64.exe`
- `wechat-ai-assistant-setup-<version>.exe`
- `wechat-ai-assistant-installer-<version>-x64.msi`

## 验证

1. 执行 `npm run build:release`，确认 `release/` 下已有 `setup-x64.exe`、`installer-x64.msi`、`latest.yml`。
2. 执行 `npm run publish:github`，确认对应 GitHub Release 附件上传完成。
3. 安装应用后启动，进入“设置 -> 应用更新”，点击“检查更新”。
4. 发布更高版本后，再次启动应用，确认能收到新版本提醒。

## 2026-03-15 优化计划落地

本轮根据 `OPTIMIZATION_SUGGESTIONS.md` 的短期计划补充了以下能力：

- 消息中心新增“消息详情”面板，可查看模型/预设、Token 估算、执行耗时、情绪识别和上下文召回摘要。
- 仪表盘新增机器人启动进度、运行诊断和“一键恢复”入口，用于处理微信掉线或运行异常。
- 启动画面从静态文案升级为带进度条的阶段提示，启动过程更可感知。
- 后端新增 `/api/recover`，并在 `/api/status` 中返回 `startup` 与 `diagnostics` 结构化状态。

建议验证：

1. 启动桌面端，确认 Splash 页面会显示阶段文本和进度条变化。
2. 在仪表盘启动机器人，确认状态卡片会展示启动阶段与进度。
3. 触发一条机器人回复后进入“消息中心”，点击消息项，确认可打开详情弹窗。
4. 断开微信或让机器人进入异常状态后，确认仪表盘出现诊断信息并可点击“一键恢复”。

## 2026-03-15 优化计划落地（第二批）

本轮继续完成中期计划中的运行可观测性和配置可验证能力：

- 仪表盘新增“健康监控”卡片，展示 CPU、内存、队列积压、AI 延迟，以及 AI 服务、微信连接、记忆库三项健康检查。
- 合并回复流程会实时回传状态，仪表盘可直接看到当前是否正在等待合并窗口结束。
- 设置页新增“提示词预览”，可以基于当前草稿配置和示例消息预览最终系统提示词，并标记是否命中会话覆盖、用户画像注入、情绪注入。
- 后端新增 `/api/preview_prompt`，用于在不保存配置的前提下验证提示词拼装结果。

建议验证：

1. 启动机器人并发送连续消息，确认仪表盘“健康监控”中的队列和“消息合并状态”会变化。
2. 切换到“设置 -> 提示词预览”，输入不同会话名与示例消息，确认能实时看到最终提示词内容。
3. 在系统提示中配置某个会话覆盖，再用同名会话预览，确认摘要显示“已命中会话覆盖”。
4. 调用 `POST /api/preview_prompt` 或通过前端按钮触发，确认不保存配置也能拿到预览结果。

## 2026-03-15 优化计划落地（第三批）

本轮继续补齐低侵入、可快速验证的性能与体验项：

- `AIClient` 新增 `tiktoken` 可选精算链路；环境中安装该依赖时会优先使用精确 token 估算，未安装时自动回退到原有启发式算法。
- 关键词情感识别增加 LRU 缓存，重复消息不会反复执行同一轮匹配计算。
- 桌面端补充快捷键支持：`Ctrl+1/2/3/4` 切页，`Ctrl+R` 重启机器人，`Ctrl+Q` 触发关闭流程，`F5` 刷新状态。
- Splash 阶段预加载主界面入口模块，降低主窗口首次显示前的资源等待。

建议验证：

1. 在已安装 `tiktoken` 的环境下启动机器人，观察长提示词场景下 Token 统计更稳定；未安装时功能应保持可用。
2. 重复发送相同情绪表达的消息，确认情感识别结果一致且不会引入额外异常。
3. 在桌面端分别按下 `Ctrl+1/2/3/4`、`Ctrl+R`、`Ctrl+Q`、`F5`，确认页面切换、机器人重启、关闭弹窗和状态刷新正常。
4. 启动应用，确认 Splash 后切换到主窗口的等待更平滑，没有引入新的白屏或报错。
