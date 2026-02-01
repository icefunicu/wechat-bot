/**
 * 微信AI助手 - Electron 主进程
 * 
 * 负责：
 * - 创建和管理应用窗口
 * - 启动和管理 Python 后端进程
 * - 系统托盘功能
 * - IPC 通信
 */

const { app, BrowserWindow, Tray, Menu, ipcMain, shell, nativeImage } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const http = require('http');
const Store = require('electron-store');
const iconv = require('iconv-lite');

// 配置存储
const store = new Store({
    defaults: {
        windowBounds: { width: 1200, height: 800 },
        startMinimized: false,
        autoStartBot: false,
        flaskPort: 5000,
        isFirstRun: true
    }
});

// 全局变量
let mainWindow = null;
let splashWindow = null;
let tray = null;
let pythonProcess = null;
let isQuitting = false;

// 开发模式检测
const isDev = process.argv.includes('--dev');
const FLASK_PORT = store.get('flaskPort');
const FLASK_URL = `http://localhost:${FLASK_PORT}`;

// ═══════════════════════════════════════════════════════════════════════════════
//                               应用路径工具
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * 获取资源路径（开发模式 vs 打包模式）
 */
function getResourcePath(relativePath) {
    if (isDev) {
        // 开发模式：项目根目录
        return path.join(__dirname, '..', '..', relativePath);
    } else {
        // 打包模式：extraResources 目录
        return path.join(process.resourcesPath, relativePath);
    }
}

/**
 * 获取 Python 后端可执行文件路径
 */
function getBackendPath() {
    if (isDev) {
        return null;
    } else {
        return path.join(process.resourcesPath, 'backend', 'wechat-bot-backend.exe');
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
//                               Python 后端管理
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * 检查 Flask 服务是否在运行
 */
function checkFlaskServer() {
    return new Promise((resolve) => {
        const req = http.get(`${FLASK_URL}/api/status`, (res) => {
            resolve(res.statusCode === 200);
        });
        req.on('error', () => resolve(false));
        req.setTimeout(2000, () => {
            req.destroy();
            resolve(false);
        });
    });
}

/**
 * 启动 Python 后端
 */
async function startPythonBackend() {
    const isRunning = await checkFlaskServer();
    if (isRunning) {
        console.log('[Backend] Flask 服务已在运行');
        return true;
    }

    return new Promise((resolve, reject) => {
        let cmd, args, options;

        if (isDev) {
            // 开发模式：使用虚拟环境的 Python
            const projectRoot = path.join(__dirname, '..', '..');
            const venvPython = path.join(projectRoot, '.venv', 'Scripts', 'python.exe');

            cmd = venvPython;
            args = ['run.py', 'web'];
            options = {
                cwd: projectRoot,
                env: {
                    ...process.env,
                    PYTHONUNBUFFERED: '1',
                    PYTHONIOENCODING: 'utf-8',
                    PYTHONLEGACYWINDOWSSTDIO: '1' // 修复 Windows 下控制台乱码
                }
            };
        } else {
            const backendPath = getBackendPath();
            cmd = backendPath;
            args = ['web'];
            options = {
                cwd: path.dirname(backendPath),
                env: {
                    ...process.env,
                    PYTHONLEGACYWINDOWSSTDIO: '1'
                }
            };
        }

        console.log(`[Backend] 启动命令: ${cmd} ${args.join(' ')}`);
        // 不设置 encoding: 'utf-8'，保持 buffer 格式以便手动解码
        pythonProcess = spawn(cmd, args, options);

        // 处理输出流
        pythonProcess.stdout.on('data', (data) => {
            // 尝试使用 iconv-lite 解码，Windows 通常是 gbk，但也可能是 utf-8
            // 这里我们先尝试 utf-8 (因为设置了 PYTHONIOENCODING=utf-8)
            // 如果乱码持续，可能需要根据系统 locale 动态调整，或者后端强制输出 gbk
            const str = iconv.decode(data, 'utf-8');
            console.log(`[Backend] ${str.trim()}`);
        });

        pythonProcess.stderr.on('data', (data) => {
            const str = iconv.decode(data, 'utf-8');
            console.error(`[Backend Error] ${str.trim()}`);
        });

        pythonProcess.on('error', (err) => {
            console.error('[Backend] 启动失败:', err);
            reject(err);
        });

        pythonProcess.on('exit', (code) => {
            console.log(`[Backend] 进程退出，代码: ${code}`);
            pythonProcess = null;
        });

        // 等待服务启动
        let attempts = 0;
        const maxAttempts = 60; // 增加超时时间到 60 秒

        const checkInterval = setInterval(async () => {
            attempts++;
            const isUp = await checkFlaskServer();

            if (isUp) {
                clearInterval(checkInterval);
                console.log('[Backend] Flask 服务已就绪');
                resolve(true);
            } else if (attempts >= maxAttempts) {
                clearInterval(checkInterval);
                console.error('[Backend] 服务启动超时');
                reject(new Error('Flask 服务启动超时'));
            }
        }, 1000);
    });
}

/**
 * 停止 Python 后端
 */
function stopPythonBackend() {
    if (pythonProcess) {
        console.log('[Backend] 正在停止...');
        pythonProcess.kill('SIGTERM');
        setTimeout(() => {
            if (pythonProcess) {
                pythonProcess.kill('SIGKILL');
            }
        }, 5000);
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
//                               启动画面
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * 创建启动画面
 */
function createSplashWindow() {
    splashWindow = new BrowserWindow({
        width: 400,
        height: 300,
        frame: false,
        transparent: true,
        resizable: false,
        center: true,
        skipTaskbar: true,
        alwaysOnTop: true,
        webPreferences: {
            contextIsolation: true,
            nodeIntegration: false
        }
    });

    splashWindow.loadFile(path.join(__dirname, '..', 'renderer', 'splash.html'));
}

/**
 * 关闭启动画面并显示主窗口
 */
function closeSplashAndShowMain() {
    if (splashWindow) {
        splashWindow.close();
        splashWindow = null;
    }

    if (mainWindow) {
        mainWindow.show();
        mainWindow.focus();
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
//                               窗口管理
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * 创建主窗口
 */
function createMainWindow() {
    const { width, height } = store.get('windowBounds');

    mainWindow = new BrowserWindow({
        width: width,
        height: height,
        minWidth: 900,
        minHeight: 600,
        title: '微信AI助手',
        icon: path.join(__dirname, '..', 'assets', 'icon.png'),
        backgroundColor: '#0A0A0F',
        frame: false,
        show: false,
        webPreferences: {
            preload: path.join(__dirname, '..', 'preload', 'index.js'),
            contextIsolation: true,
            nodeIntegration: false,
            devTools: isDev
        }
    });

    // 加载页面
    mainWindow.loadFile(path.join(__dirname, '..', 'renderer', 'index.html'));

    // 保存窗口大小
    mainWindow.on('resize', () => {
        const bounds = mainWindow.getBounds();
        store.set('windowBounds', { width: bounds.width, height: bounds.height });
    });

    // 关闭时最小化到托盘
    mainWindow.on('close', (event) => {
        if (!isQuitting) {
            event.preventDefault();
            mainWindow.hide();
        }
    });

    // 开发模式打开 DevTools
    if (isDev) {
        mainWindow.webContents.openDevTools();
    }
}

/**
 * 创建系统托盘
 */
function createTray() {
    const iconPath = path.join(__dirname, '..', 'assets', 'icon.png');
    const icon = nativeImage.createFromPath(iconPath);

    tray = new Tray(icon.resize({ width: 16, height: 16 }));

    const contextMenu = Menu.buildFromTemplate([
        {
            label: '显示主窗口',
            click: () => {
                mainWindow.show();
                mainWindow.focus();
            }
        },
        { type: 'separator' },
        {
            label: '启动机器人',
            click: () => {
                mainWindow.webContents.send('tray-action', 'start-bot');
            }
        },
        {
            label: '停止机器人',
            click: () => {
                mainWindow.webContents.send('tray-action', 'stop-bot');
            }
        },
        { type: 'separator' },
        {
            label: '退出',
            click: () => {
                isQuitting = true;
                app.quit();
            }
        }
    ]);

    tray.setToolTip('微信AI助手');
    tray.setContextMenu(contextMenu);

    tray.on('double-click', () => {
        mainWindow.show();
        mainWindow.focus();
    });
}

// ═══════════════════════════════════════════════════════════════════════════════
//                               IPC 通信处理
// ═══════════════════════════════════════════════════════════════════════════════

function setupIPC() {
    ipcMain.handle('get-flask-url', () => FLASK_URL);
    ipcMain.handle('check-backend', async () => await checkFlaskServer());

    ipcMain.handle('start-backend', async () => {
        try {
            await startPythonBackend();
            return { success: true };
        } catch (err) {
            return { success: false, error: err.message };
        }
    });

    ipcMain.handle('open-external', (event, url) => shell.openExternal(url));
    ipcMain.handle('get-app-version', () => app.getVersion());
    ipcMain.handle('minimize-to-tray', () => mainWindow.hide());

    // 窗口控制
    ipcMain.handle('window-minimize', () => mainWindow.minimize());
    ipcMain.handle('window-maximize', () => {
        if (mainWindow.isMaximized()) {
            mainWindow.unmaximize();
        } else {
            mainWindow.maximize();
        }
    });
    ipcMain.handle('window-close', () => mainWindow.hide());

    // 首次运行检测
    ipcMain.handle('is-first-run', () => store.get('isFirstRun'));
    ipcMain.handle('set-first-run-complete', () => {
        store.set('isFirstRun', false);
        return true;
    });
}

// ═══════════════════════════════════════════════════════════════════════════════
//                               应用生命周期
// ═══════════════════════════════════════════════════════════════════════════════

// 单实例锁
const gotTheLock = app.requestSingleInstanceLock();

if (!gotTheLock) {
    app.quit();
} else {
    app.on('second-instance', () => {
        if (mainWindow) {
            if (mainWindow.isMinimized()) mainWindow.restore();
            mainWindow.show();
            mainWindow.focus();
        }
    });
}

// 应用就绪
app.whenReady().then(async () => {
    // 创建启动画面
    createSplashWindow();

    // 设置 IPC
    setupIPC();

    // 创建主窗口（但不显示）
    createMainWindow();
    createTray();

    // 启动 Python 后端 (带超时机制)
    try {
        console.log('[Main] 开始启动后端...');

        // 创建一个承诺，在1秒后解决，不仅仅是拒绝，这样我们可以继续流程
        const timeoutPromise = new Promise(resolve => {
            setTimeout(() => {
                resolve('TIMEOUT');
            }, 1000);
        });

        // 使用 Promise.race 等待后端启动或超时
        const result = await Promise.race([
            startPythonBackend(),
            timeoutPromise
        ]);

        if (result === 'TIMEOUT') {
            console.log('[Main] 后端启动仍在后台进行，先行显示主窗口');
        } else {
            console.log('[Main] 后端启动完成');
        }
    } catch (err) {
        console.error('[Main] 后端启动过程中出错 (非致命):', err);
    } finally {
        // 无论后端状态如何，都关闭闪屏并显示主窗口
        // 稍微延时一点点以平滑过渡
        setTimeout(() => {
            closeSplashAndShowMain();
        }, 500);
    }
});

// 所有窗口关闭时
app.on('window-all-closed', () => {
    // Windows 上不退出，保持托盘运行
});

// 应用退出前
app.on('before-quit', () => {
    isQuitting = true;
    stopPythonBackend();
});

// 激活时（macOS）
app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
        createMainWindow();
    } else {
        mainWindow.show();
    }
});
