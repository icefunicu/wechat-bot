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
