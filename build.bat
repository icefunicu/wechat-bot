@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

echo.
echo ==============================================================
echo            WeChat AI Assistant - Build Script
echo ==============================================================
echo.

set "PROJECT_ROOT=%~dp0"
cd /d "%PROJECT_ROOT%"
if errorlevel 1 (
    echo Failed to enter project root: %PROJECT_ROOT%
    exit /b 1
)

echo [1/5] Checking Node.js...
where node >nul 2>&1
if errorlevel 1 (
    echo Node.js was not found. Install Node.js first.
    echo https://nodejs.org/
    exit /b 1
)
for /f "tokens=*" %%i in ('node -v') do set "NODE_VERSION=%%i"
echo     Node.js !NODE_VERSION!

echo [2/5] Checking Python...
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
    where python >nul 2>&1
    if errorlevel 1 (
        echo Python was not found. Install Python 3.8+ first.
        exit /b 1
    )
    set "PYTHON_EXE=python"
)
for /f "tokens=*" %%i in ('"!PYTHON_EXE!" --version') do set "PY_VERSION=%%i"
echo     !PY_VERSION!

echo [3/5] Checking Node dependencies...
if not exist "node_modules" (
    call npm install
    if errorlevel 1 (
        echo npm install failed.
        exit /b 1
    )
)
echo     Node dependencies are ready.

echo [4/5] Building Python backend...
if not exist "backend-dist" mkdir backend-dist

"!PYTHON_EXE!" -m PyInstaller --name wechat-bot-backend --distpath "%PROJECT_ROOT%backend-dist" --workpath "%PROJECT_ROOT%build" --specpath "%PROJECT_ROOT%build" --noconfirm --clean --console --add-data "%PROJECT_ROOT%data;data" --hidden-import wxauto --hidden-import quart --hidden-import hypercorn --hidden-import openai --hidden-import httpx --collect-all wxauto "%PROJECT_ROOT%run.py"
if errorlevel 1 (
    echo PyInstaller build failed.
    exit /b 1
)
echo     Python backend build complete.

echo [5/5] Building portable Electron EXE...
call npm run build:portable
if errorlevel 1 (
    echo Electron portable build failed.
    exit /b 1
)

echo.
echo ==============================================================
echo                    Build Complete
echo ==============================================================
echo.
echo Output: %PROJECT_ROOT%release\
echo.

if exist release explorer release
