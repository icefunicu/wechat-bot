@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║           🤖 微信AI助手 - 构建脚本                          ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

:: 获取项目根目录
set "PROJECT_ROOT=%~dp0"
cd /d "%PROJECT_ROOT%"

:: 检查 Node.js
echo [1/5] 检查 Node.js 环境...
where node >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo ❌ 未找到 Node.js，请先安装 Node.js
    echo    下载地址: https://nodejs.org/
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('node -v') do set NODE_VERSION=%%i
echo     ✓ Node.js %NODE_VERSION%

:: 检查 Python
echo [2/5] 检查 Python 环境...
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
    where python >nul 2>&1
    if %ERRORLEVEL% neq 0 (
        echo ❌ 未找到 Python，请先安装 Python 3.8+
        pause
        exit /b 1
    )
    set "PYTHON_EXE=python"
)
for /f "tokens=*" %%i in ('!PYTHON_EXE! --version') do set PY_VERSION=%%i
echo     ✓ !PY_VERSION!

:: 安装 Node 依赖
echo [3/5] 安装 Electron 依赖...
if not exist "node_modules" (
    call npm install
    if %ERRORLEVEL% neq 0 (
        echo ❌ npm install 失败
        pause
        exit /b 1
    )
)
echo     ✓ 依赖已安装

:: 打包 Python 后端
echo [4/5] 打包 Python 后端...
if not exist "backend-dist" (
    mkdir backend-dist
)

:: 检查是否已打包
if not exist "backend-dist\wechat-bot-backend\wechat-bot-backend.exe" (
    echo     正在使用 PyInstaller 打包后端...
    !PYTHON_EXE! -m PyInstaller ^
        --name wechat-bot-backend ^
        --distpath backend-dist ^
        --workpath build ^
        --specpath build ^
        --noconfirm ^
        --console ^
        --add-data "web\templates;web\templates" ^
        --add-data "data;data" ^
        --hidden-import wxauto ^
        --hidden-import flask ^
        --hidden-import flask_socketio ^
        --hidden-import openai ^
        --hidden-import httpx ^
        --collect-all wxauto ^
        run.py
    
    if %ERRORLEVEL% neq 0 (
        echo ❌ PyInstaller 打包失败
        echo    请确保已安装 PyInstaller: pip install pyinstaller
        pause
        exit /b 1
    )
)
echo     ✓ 后端已打包

:: 构建 Electron 应用
echo [5/5] 构建 Electron 应用...
call npm run build

if %ERRORLEVEL% neq 0 (
    echo ❌ Electron 构建失败
    pause
    exit /b 1
)

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║                    ✅ 构建完成！                             ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.
echo 输出目录: %PROJECT_ROOT%dist\
echo.

:: 打开输出目录
explorer dist

pause
