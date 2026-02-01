@echo off
chcp 65001 >nul

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║           🤖 微信AI助手 - 开发模式                          ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

cd /d "%~dp0"

:: 检查 node_modules
if not exist "node_modules" (
    echo 正在安装依赖...
    call npm install
)

:: 启动 Flask 后端（后台）
echo 正在启动 Flask 后端...
start /b "" .venv\Scripts\python.exe run.py web

:: 等待后端启动
timeout /t 3 /nobreak >nul

:: 启动 Electron
echo 正在启动 Electron...
call npm start -- --dev
