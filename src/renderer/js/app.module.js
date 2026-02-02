/**
 * 微信AI助手 - 主应用入口
 * 
 * 精简后的入口文件，只负责：
 * - 初始化核心模块
 * - 加载页面控制器
 * - 全局事件协调
 */

// 修复 ReferenceError: dragEvent is not defined
// 某些环境下可能存在对 dragEvent 的错误引用（可能是 DragEvent 的拼写错误或遗留代码）
if (typeof window.dragEvent === 'undefined') {
    window.dragEvent = window.DragEvent;
}

import { stateManager, eventBus, Events } from './core/index.js';
import { apiService, notificationService } from './services/index.js';
import { DashboardPage, MessagesPage, SettingsPage, LogsPage } from './pages/index.js';

// ═══════════════════════════════════════════════════════════════════════════════
//                               应用类
// ═══════════════════════════════════════════════════════════════════════════════

class App {
    constructor() {
        // 页面控制器映射
        this.pages = {
            dashboard: new DashboardPage(),
            messages: new MessagesPage(),
            settings: new SettingsPage(),
            logs: new LogsPage()
        };

        // 当前活动页面
        this.currentPage = null;

        // 状态刷新定时器
        this._statusInterval = null;
    }

    /**
     * 初始化应用
     */
    async init() {
        console.log('[App] 正在初始化...');

        // 初始化服务
        await apiService.init();
        notificationService.init();

        // 设置版本号
        await this._setupVersion();

        // 绑定全局事件
        this._bindGlobalEvents();
        this._setupCloseChoiceModal();

        // 初始化所有页面
        for (const page of Object.values(this.pages)) {
            await page.onInit();
        }

        // 检查后端连接并刷新状态
        await this._checkBackendConnection();
        await this._refreshStatus();

        // 切换到默认页面
        await this._switchPage('dashboard');

        // 启动状态定时刷新
        this._startStatusRefresh();

        console.log('[App] 初始化完成');
    }

    // ═══════════════════════════════════════════════════════════════════════
    //                           版本和连接
    // ═══════════════════════════════════════════════════════════════════════

    async _setupVersion() {
        if (window.electronAPI) {
            const version = await window.electronAPI.getAppVersion();
            const versionElem = document.getElementById('version-text');
            if (versionElem) {
                versionElem.textContent = `v${version}`;
            }
        }
    }

    async _checkBackendConnection() {
        let connected = false;
        if (window.electronAPI) {
            connected = await window.electronAPI.checkBackend();
        } else {
            try {
                await apiService.getStatus();
                connected = true;
            } catch {
                connected = false;
            }
        }
        stateManager.set('bot.connected', connected);
        this._updateConnectionStatus();
    }

    // ═══════════════════════════════════════════════════════════════════════
    //                           全局事件绑定
    // ═══════════════════════════════════════════════════════════════════════

    _bindGlobalEvents() {
        // 导航事件
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                const page = item.dataset.page;
                this._switchPage(page);
            });
        });

        // 标题栏按钮
        document.getElementById('btn-minimize')?.addEventListener('click', () => {
            window.electronAPI?.minimizeWindow();
        });

        document.getElementById('btn-maximize')?.addEventListener('click', () => {
            window.electronAPI?.maximizeWindow();
        });

        document.getElementById('btn-close')?.addEventListener('click', () => {
            window.electronAPI?.closeWindow();
        });

        // 托盘事件
        if (window.electronAPI) {
            window.electronAPI.onTrayAction?.((action) => {
                if (action === 'start-bot' && !stateManager.get('bot.running')) {
                    eventBus.emit(Events.BOT_START, {});
                } else if (action === 'stop-bot' && stateManager.get('bot.running')) {
                    eventBus.emit(Events.BOT_STOP, {});
                }
            });
        }

        // 监听页面切换事件
        eventBus.on(Events.PAGE_CHANGE, (pageName) => {
            this._switchPage(pageName);
        });

        // 监听状态刷新事件
        eventBus.on(Events.BOT_STATUS_CHANGE, () => {
            this._refreshStatus();
        });
    }

    _setupCloseChoiceModal() {
        const modal = document.getElementById('close-choice-modal');
        const remember = document.getElementById('close-choice-remember');
        const btnMinimize = document.getElementById('btn-close-choice-minimize');
        const btnQuit = document.getElementById('btn-close-choice-quit');
        const statusText = document.getElementById('close-choice-status');

        if (!modal || !window.electronAPI?.onAppCloseDialog) return;

        const openModal = () => {
            if (remember) remember.checked = false;
            const running = stateManager.get('bot.running');
            const paused = stateManager.get('bot.paused');
            if (statusText) {
                if (!running) {
                    statusText.textContent = '机器人已停止';
                } else if (paused) {
                    statusText.textContent = '机器人已暂停';
                } else {
                    statusText.textContent = '机器人运行中';
                }
            }
            modal.classList.add('active');
        };

        const closeModal = () => {
            modal.classList.remove('active');
        };

        window.electronAPI.onAppCloseDialog(() => {
            openModal();
        });

        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                closeModal();
            }
        });

        window.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && modal.classList.contains('active')) {
                closeModal();
            }
        });

        btnMinimize?.addEventListener('click', async () => {
            const keep = !!remember?.checked;
            closeModal();
            await window.electronAPI.confirmCloseAction('minimize', keep);
        });

        btnQuit?.addEventListener('click', async () => {
            const keep = !!remember?.checked;
            closeModal();
            await window.electronAPI.confirmCloseAction('quit', keep);
        });
    }

    // ═══════════════════════════════════════════════════════════════════════
    //                           页面切换
    // ═══════════════════════════════════════════════════════════════════════

    async _switchPage(pageName) {
        // 通知当前页面离开
        if (this.currentPage) {
            await this.currentPage.onLeave();
        }

        // 更新导航状态
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.toggle('active', item.dataset.page === pageName);
        });

        // 切换页面可见性
        document.querySelectorAll('.page').forEach(page => {
            page.classList.toggle('active', page.id === `page-${pageName}`);
        });

        // 更新状态
        stateManager.set('currentPage', pageName);
        this.currentPage = this.pages[pageName];

        // 通知新页面进入
        if (this.currentPage) {
            await this.currentPage.onEnter();
        }

        console.log(`[App] 切换到页面: ${pageName}`);
    }

    // ═══════════════════════════════════════════════════════════════════════
    //                           状态刷新
    // ═══════════════════════════════════════════════════════════════════════

    async _refreshStatus() {
        try {
            const status = await apiService.getStatus();

            // 更新状态管理器
            stateManager.batchUpdate({
                'bot.running': status.running,
                'bot.paused': status.is_paused,
                'bot.connected': true
            });

            // 更新仪表盘统计
            if (this.pages.dashboard) {
                this.pages.dashboard.updateStats(status);
            }

            // 更新连接状态
            this._updateConnectionStatus();

        } catch (error) {
            console.error('[App] 刷新状态失败:', error);
            stateManager.set('bot.connected', false);
            this._updateConnectionStatus();
        }
    }

    _updateConnectionStatus() {
        const badge = document.getElementById('status-badge');
        if (!badge) return;

        const dot = badge.querySelector('.status-dot');
        const label = badge.querySelector('.status-label');

        const connected = stateManager.get('bot.connected');
        const running = stateManager.get('bot.running');
        const paused = stateManager.get('bot.paused');

        if (!connected) {
            dot.className = 'status-dot offline';
            label.textContent = '未连接';
        } else if (running) {
            if (paused) {
                dot.className = 'status-dot warning';
                label.textContent = '已暂停';
            } else {
                dot.className = 'status-dot online';
                label.textContent = '运行中';
            }
        } else {
            dot.className = 'status-dot offline';
            label.textContent = '已停止';
        }
    }

    _startStatusRefresh() {
        // 每 5 秒刷新状态
        this._statusInterval = setInterval(() => this._refreshStatus(), 5000);
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
//                               应用启动
// ═══════════════════════════════════════════════════════════════════════════════

// 等待 DOM 加载完成后初始化
document.addEventListener('DOMContentLoaded', async () => {
    const app = new App();
    await app.init();

    // 暴露到全局（用于调试）
    window.__app = app;
    window.__state = stateManager;
    window.__events = eventBus;
});
