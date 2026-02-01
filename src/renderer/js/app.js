/**
 * 微信AI助手 - 主应用入口（重构版）
 * 
 * 采用 IIFE 模式兼容 Electron CSP 策略
 * 整合核心模块、服务层和页面控制器
 */

// ═══════════════════════════════════════════════════════════════════════════════
//                               核心模块 - StateManager
// ═══════════════════════════════════════════════════════════════════════════════

const StateManager = (function () {
    const _state = {
        bot: { running: false, paused: false, connected: false },
        currentPage: 'dashboard',
        logs: { autoScroll: true }
    };
    const _subscribers = new Map();

    return {
        get(path) {
            const keys = path.split('.');
            let value = _state;
            for (const key of keys) {
                if (value === undefined) return undefined;
                value = value[key];
            }
            return value;
        },

        set(path, value) {
            const keys = path.split('.');
            const lastKey = keys.pop();
            let target = _state;
            for (const key of keys) {
                if (target[key] === undefined) target[key] = {};
                target = target[key];
            }
            const oldValue = target[lastKey];
            target[lastKey] = value;
            this._notify(path, value, oldValue);
        },

        batchUpdate(updates) {
            for (const [path, value] of Object.entries(updates)) {
                this.set(path, value);
            }
        },

        subscribe(path, callback) {
            if (!_subscribers.has(path)) _subscribers.set(path, new Set());
            _subscribers.get(path).add(callback);
            return () => _subscribers.get(path)?.delete(callback);
        },

        _notify(path, newValue, oldValue) {
            if (_subscribers.has(path)) {
                for (const cb of _subscribers.get(path)) {
                    try { cb(newValue, oldValue, path); } catch (e) { console.error(e); }
                }
            }
            // 通配符支持
            const parts = path.split('.');
            for (let i = 1; i < parts.length; i++) {
                const wildcardPath = parts.slice(0, i).join('.') + '.*';
                if (_subscribers.has(wildcardPath)) {
                    for (const cb of _subscribers.get(wildcardPath)) {
                        try { cb(newValue, oldValue, path); } catch (e) { console.error(e); }
                    }
                }
            }
        }
    };
})();

// ═══════════════════════════════════════════════════════════════════════════════
//                               核心模块 - EventBus
// ═══════════════════════════════════════════════════════════════════════════════

const EventBus = (function () {
    const _handlers = new Map();

    return {
        on(event, handler) {
            if (!_handlers.has(event)) _handlers.set(event, new Set());
            _handlers.get(event).add(handler);
            return () => this.off(event, handler);
        },

        off(event, handler) {
            if (handler) _handlers.get(event)?.delete(handler);
            else _handlers.delete(event);
        },

        emit(event, data) {
            if (_handlers.has(event)) {
                for (const handler of _handlers.get(event)) {
                    try { handler(data); } catch (e) { console.error(`[EventBus] 错误:`, e); }
                }
            }
        }
    };
})();

// 事件常量
const Events = {
    PAGE_CHANGE: 'page:change',
    BOT_STATUS_CHANGE: 'bot:status-change',
    BOT_START: 'bot:start',
    BOT_STOP: 'bot:stop'
};

// ═══════════════════════════════════════════════════════════════════════════════
//                               服务层 - ApiService
// ═══════════════════════════════════════════════════════════════════════════════

const ApiService = (function () {
    let baseUrl = 'http://localhost:5000';
    let initialized = false;

    async function init() {
        if (window.electronAPI) {
            baseUrl = await window.electronAPI.getFlaskUrl();
        }
        initialized = true;
    }

    async function request(endpoint, options = {}) {
        if (!initialized) await init();
        const url = `${baseUrl}${endpoint}`;
        const config = { headers: { 'Content-Type': 'application/json' }, ...options };
        if (config.body && typeof config.body === 'object') {
            config.body = JSON.stringify(config.body);
        }
        const response = await fetch(url, config);
        return response.json();
    }

    return {
        init,
        getStatus: () => request('/api/status'),
        startBot: () => request('/api/start', { method: 'POST' }),
        stopBot: () => request('/api/stop', { method: 'POST' }),
        restartBot: () => request('/api/restart', { method: 'POST' }),
        pauseBot: (reason = '用户暂停') => request('/api/pause', { method: 'POST', body: { reason } }),
        resumeBot: () => request('/api/resume', { method: 'POST' }),
        getMessages: () => request('/api/messages'),
        sendMessage: (target, content) => request('/api/send', { method: 'POST', body: { target, content } }),
        getConfig: () => request('/api/config'),
        saveConfig: (config) => request('/api/config', { method: 'POST', body: config }),
        getLogs: (lines = 200) => request(`/api/logs?lines=${lines}`),
        clearLogs: () => request('/api/logs', { method: 'DELETE' }),
        getUsage: () => request('/api/usage')
    };
})();

// ═══════════════════════════════════════════════════════════════════════════════
//                               服务层 - Toast
// ═══════════════════════════════════════════════════════════════════════════════

const Toast = (function () {
    let container = null;

    function getIconSvg(name) {
        return `<svg class="icon"><use href="#icon-${name}"/></svg>`;
    }

    return {
        init() {
            container = document.getElementById('toast-container');
        },

        show(message, type = 'info', duration = 3000) {
            if (!container) this.init();
            const icons = {
                success: getIconSvg('check'),
                error: getIconSvg('x'),
                warning: getIconSvg('alert-circle'),
                info: getIconSvg('info')
            };
            const toast = document.createElement('div');
            toast.className = `toast ${type}`;
            toast.innerHTML = `<span class="toast-icon">${icons[type]}</span><span class="toast-message">${message}</span>`;
            container.appendChild(toast);
            setTimeout(() => {
                toast.style.animation = 'toastEnter 0.25s ease reverse';
                setTimeout(() => toast.remove(), 250);
            }, duration);
        },

        success(message) { this.show(message, 'success'); },
        error(message) { this.show(message, 'error'); },
        warning(message) { this.show(message, 'warning'); },
        info(message) { this.show(message, 'info'); }
    };
})();

// ═══════════════════════════════════════════════════════════════════════════════
//                               页面控制器基类
// ═══════════════════════════════════════════════════════════════════════════════

class PageController {
    constructor(name, containerId) {
        this.name = name;
        this.containerId = containerId;
        this.container = null;
        this._cleanups = [];
        this._isActive = false;
    }

    getContainer() {
        if (!this.container) this.container = document.getElementById(this.containerId);
        return this.container;
    }

    $(selector) { return this.getContainer()?.querySelector(selector); }
    $$(selector) { return this.getContainer()?.querySelectorAll(selector) || []; }

    async onInit() { console.log(`[${this.name}] 初始化`); }
    async onEnter() { this._isActive = true; console.log(`[${this.name}] 进入`); }
    async onLeave() { this._isActive = false; console.log(`[${this.name}] 离开`); }

    bindEvent(target, event, handler) {
        let element = typeof target === 'string' ? this.$(target) : target;
        if (!element) return;
        element.addEventListener(event, handler);
        this._cleanups.push(() => element.removeEventListener(event, handler));
    }

    watchState(path, handler) {
        const cleanup = StateManager.subscribe(path, handler);
        this._cleanups.push(cleanup);
    }

    getState(path) { return StateManager.get(path); }
    setState(path, value) { StateManager.set(path, value); }
    emit(event, data) { EventBus.emit(event, data); }

    cleanup() {
        for (const fn of this._cleanups) fn();
        this._cleanups = [];
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
//                               DashboardPage
// ═══════════════════════════════════════════════════════════════════════════════

class DashboardPage extends PageController {
    constructor() { super('DashboardPage', 'page-dashboard'); }

    async onInit() {
        await super.onInit();
        this._bindEvents();
    }

    async onEnter() {
        await super.onEnter();
        await this._loadRecentMessages();
    }

    _bindEvents() {
        this.bindEvent('#btn-toggle-bot', 'click', () => this._toggleBot());
        this.bindEvent('#btn-pause', 'click', () => this._togglePause());
        this.bindEvent('#btn-restart', 'click', () => this._restartBot());
        this.bindEvent('#btn-open-wechat', 'click', () => Toast.info('请手动打开微信客户端'));
        this.bindEvent('#btn-view-logs', 'click', () => this.emit(Events.PAGE_CHANGE, 'logs'));
        this.bindEvent('#btn-refresh-status', 'click', async () => {
            this.emit(Events.BOT_STATUS_CHANGE, {});
            Toast.success('状态已刷新');
        });
        this.bindEvent('#btn-minimize-tray', 'click', () => window.electronAPI?.minimizeToTray());
        this.bindEvent('#btn-view-all-messages', 'click', () => this.emit(Events.PAGE_CHANGE, 'messages'));
        this.watchState('bot.*', () => this._updateBotUI());
    }

    async _toggleBot() {
        const btn = this.$('#btn-toggle-bot');
        const btnText = btn?.querySelector('span');
        if (!btn) return;
        btn.disabled = true;
        try {
            const isRunning = this.getState('bot.running');
            if (isRunning) {
                btnText.textContent = '停止中...';
                const result = await ApiService.stopBot();
                Toast.show(result.message, result.success ? 'success' : 'error');
            } else {
                btnText.textContent = '启动中...';
                const result = await ApiService.startBot();
                Toast.show(result.message, result.success ? 'success' : 'error');
            }
            setTimeout(() => this.emit(Events.BOT_STATUS_CHANGE, {}), 1000);
        } catch (error) {
            Toast.error('操作失败: ' + error.message);
        } finally {
            btn.disabled = false;
        }
    }

    async _togglePause() {
        try {
            const isPaused = this.getState('bot.paused');
            const result = isPaused ? await ApiService.resumeBot() : await ApiService.pauseBot();
            Toast.show(result.message, result.success ? 'success' : 'error');
            this.emit(Events.BOT_STATUS_CHANGE, {});
        } catch (error) {
            Toast.error('操作失败: ' + error.message);
        }
    }

    async _restartBot() {
        try {
            Toast.info('正在重启机器人...');
            const result = await ApiService.restartBot();
            Toast.show(result.message, result.success ? 'success' : 'error');
            setTimeout(() => this.emit(Events.BOT_STATUS_CHANGE, {}), 2000);
        } catch (error) {
            Toast.error('重启失败: ' + error.message);
        }
    }

    _updateBotUI() {
        const isRunning = this.getState('bot.running');
        const isPaused = this.getState('bot.paused');

        const stateElem = this.$('#bot-state');
        if (stateElem) {
            const dot = stateElem.querySelector('.bot-state-dot');
            const text = stateElem.querySelector('.bot-state-text');
            if (isRunning) {
                dot.className = isPaused ? 'bot-state-dot paused' : 'bot-state-dot online';
                text.textContent = isPaused ? '已暂停' : '运行中';
            } else {
                dot.className = 'bot-state-dot offline';
                text.textContent = '离线';
            }
        }

        const pauseBtn = this.$('#btn-pause');
        const pauseText = pauseBtn?.querySelector('span');
        if (pauseText) pauseText.textContent = isPaused ? '恢复' : '暂停';

        const toggleBtn = this.$('#btn-toggle-bot');
        if (toggleBtn) {
            const icon = toggleBtn.querySelector('svg use');
            const text = toggleBtn.querySelector('span');
            if (isRunning) {
                text.textContent = '停止机器人';
                icon?.setAttribute('href', '#icon-square');
                toggleBtn.classList.remove('btn-primary');
                toggleBtn.classList.add('btn-secondary');
            } else {
                text.textContent = '启动机器人';
                icon?.setAttribute('href', '#icon-play');
                toggleBtn.classList.remove('btn-secondary');
                toggleBtn.classList.add('btn-primary');
            }
        }
    }

    async _loadRecentMessages() {
        try {
            const result = await ApiService.getMessages();
            const container = this.$('#recent-messages');
            if (result.success && result.messages && container) {
                this._renderMessages(container, result.messages.slice(-5));
            }
        } catch (error) {
            console.error('[DashboardPage] 加载消息失败:', error);
        }
    }

    _renderMessages(container, messages) {
        if (!messages || messages.length === 0) {
            container.innerHTML = `<div class="empty-state"><svg class="icon"><use href="#icon-inbox"/></svg><span class="empty-state-text">暂无消息记录</span></div>`;
            return;
        }
        container.innerHTML = messages.map(msg => {
            const icon = msg.is_self ? '<svg class="icon"><use href="#icon-bot"/></svg>' : '<svg class="icon"><use href="#icon-user"/></svg>';
            const sender = msg.sender || (msg.is_self ? 'AI助手' : '用户');
            const time = this._formatTime(msg.timestamp);
            const text = this._escapeHtml(msg.content || msg.text || '');
            return `<div class="message-item"><div class="message-avatar">${icon}</div><div class="message-body"><div class="message-meta"><span class="message-sender">${sender}</span><span class="message-time">${time}</span></div><div class="message-text">${text}</div></div></div>`;
        }).join('');
    }

    _formatTime(timestamp) {
        if (!timestamp) return '';
        const date = new Date(timestamp * 1000);
        const now = new Date();
        if (date.toDateString() === now.toDateString()) {
            return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
        }
        return date.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
    }

    _escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    updateStats(stats) {
        const fmt = (v) => v === undefined || v === null ? '0' : v.toLocaleString('zh-CN');
        const fmtToken = (v) => !v || v < 1000 ? (v || '0') : v < 1000000 ? (v / 1000).toFixed(1) + 'K' : (v / 1000000).toFixed(1) + 'M';

        const uptimeElem = this.$('#stat-uptime');
        const todayRepliesElem = this.$('#stat-today-replies');
        const todayTokensElem = this.$('#stat-today-tokens');
        const totalRepliesElem = this.$('#stat-total-replies');

        if (uptimeElem) uptimeElem.textContent = stats.uptime || '--';
        if (todayRepliesElem) todayRepliesElem.textContent = fmt(stats.today_replies);
        if (todayTokensElem) todayTokensElem.textContent = fmtToken(stats.today_tokens);
        if (totalRepliesElem) totalRepliesElem.textContent = fmt(stats.total_replies);
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
//                               MessagesPage
// ═══════════════════════════════════════════════════════════════════════════════

class MessagesPage extends PageController {
    constructor() { super('MessagesPage', 'page-messages'); }

    async onInit() {
        await super.onInit();
        this.bindEvent('#btn-refresh-messages', 'click', () => this._loadMessages());
        this.bindEvent('#message-search', 'input', (e) => this._filterMessages(e.target.value));
    }

    async onEnter() {
        await super.onEnter();
        await this._loadMessages();
    }

    async _loadMessages() {
        const container = this.$('#all-messages');
        if (!container) return;
        container.innerHTML = `<div class="loading-state"><div class="spinner"></div><span>加载中...</span></div>`;
        try {
            const result = await ApiService.getMessages();
            if (result.success && result.messages) {
                this._renderMessages(container, result.messages);
            } else {
                container.innerHTML = `<div class="empty-state"><svg class="icon"><use href="#icon-inbox"/></svg><span class="empty-state-text">暂无消息记录</span></div>`;
            }
        } catch (error) {
            container.innerHTML = `<div class="empty-state"><svg class="icon"><use href="#icon-alert-circle"/></svg><span class="empty-state-text">加载失败</span></div>`;
        }
    }

    _filterMessages(keyword) {
        const items = this.$$('#all-messages .message-item');
        const lowerKeyword = keyword.toLowerCase();
        items.forEach(item => {
            item.style.display = item.textContent.toLowerCase().includes(lowerKeyword) ? '' : 'none';
        });
    }

    _renderMessages(container, messages) {
        if (!messages || messages.length === 0) {
            container.innerHTML = `<div class="empty-state"><svg class="icon"><use href="#icon-inbox"/></svg><span class="empty-state-text">暂无消息记录</span></div>`;
            return;
        }
        container.innerHTML = messages.map(msg => {
            const icon = msg.is_self ? '<svg class="icon"><use href="#icon-bot"/></svg>' : '<svg class="icon"><use href="#icon-user"/></svg>';
            const sender = msg.sender || (msg.is_self ? 'AI助手' : '用户');
            const time = this._formatTime(msg.timestamp);
            const text = this._escapeHtml(msg.content || msg.text || '');
            return `<div class="message-item"><div class="message-avatar">${icon}</div><div class="message-body"><div class="message-meta"><span class="message-sender">${sender}</span><span class="message-time">${time}</span></div><div class="message-text">${text}</div></div></div>`;
        }).join('');
    }

    _formatTime(timestamp) {
        if (!timestamp) return '';
        const date = new Date(timestamp * 1000);
        const now = new Date();
        if (date.toDateString() === now.toDateString()) {
            return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
        }
        return date.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
    }

    _escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
//                               SettingsPage
// ═══════════════════════════════════════════════════════════════════════════════

class SettingsPage extends PageController {
    constructor() { super('SettingsPage', 'page-settings'); }

    async onInit() {
        await super.onInit();
        this._bindEvents();
        this._bindModalEvents();
    }

    async onEnter() {
        await super.onEnter();
        await this._loadSettings();
    }

    // ═══════════════════════════════════════════════════════════════════════
    //                           事件绑定
    // ═══════════════════════════════════════════════════════════════════════

    _bindEvents() {
        this.bindEvent('#btn-save-settings', 'click', () => this._saveGeneralSettings());

        this.bindEvent('#btn-refresh-config', 'click', async () => {
            await this._loadSettings();
            Toast.success('配置已刷新');
        });

        // 新增预设 - 委托到 document 以确保事件捕获
        this.bindEvent(document, 'click', (e) => {
            if (e.target.closest('#btn-add-preset')) {
                this._openAddModal();
            }
        });

        // 绑定预设卡片相关事件（使用委托）
        const container = this.getContainer();
        if (container) {
            container.addEventListener('click', (e) => {
                // 处理编辑按钮
                const editBtn = e.target.closest('.btn-edit-preset');
                if (editBtn) {
                    this._handleEditClick(e, editBtn);
                    return;
                }

                // 处理删除按钮
                const deleteBtn = e.target.closest('.btn-delete-preset');
                if (deleteBtn) {
                    this._handleDeleteClick(e, deleteBtn);
                    return;
                }

                // 处理卡片点击
                const card = e.target.closest('.preset-card');
                if (card) {
                    this._handleCardClick(e, card);
                }
            });
        }
    }

    _bindModalEvents() {
        // Modal Bindings (Use document.querySelector since modal is outside page container)
        const bindGlobal = (sel, event, handler) => {
            const el = document.querySelector(sel);
            if (el) {
                // Remove old listener to avoid duplicates if re-inited
                // (Note: PageController cleanup handles removing listeners added via this.bindEvent/addEventListener if tracked, 
                // but here we are adding to global elements manually. Simplified for now.)
                el.removeEventListener(event, handler);
                el.addEventListener(event, handler);
            }
        };

        const modal = document.querySelector('#preset-modal');
        if (modal) {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) this._closeModal();
            });
        }

        bindGlobal('#btn-close-modal', 'click', () => this._closeModal());
        bindGlobal('#btn-cancel-modal', 'click', () => this._closeModal());
        bindGlobal('#btn-save-modal', 'click', () => this._savePresetFromModal());

        bindGlobal('#btn-toggle-key', 'click', () => {
            const input = document.getElementById('edit-preset-key');
            if (input) input.type = input.type === 'password' ? 'text' : 'password';
        });
    }

    // ═══════════════════════════════════════════════════════════════════════
    //                           配置加载与保存
    // ═══════════════════════════════════════════════════════════════════════

    async _loadSettings() {
        try {
            const result = await ApiService.getConfig(); // Use Global ApiService

            if (!result || !result.success) {
                Toast.error('加载配置失败');
                return;
            }

            const { api: apiConfig, bot: botConfig } = result;
            this.currentApiConfig = apiConfig; // Cache for modal
            this.botConfig = botConfig;

            // 更新当前配置概览
            const activePreset = apiConfig.active_preset_info || {};
            this._setText('#info-active-preset', apiConfig.active_preset || '--');
            this._setText('#info-model', activePreset.model || apiConfig.model || '--');
            this._setText('#info-alias', activePreset.alias || apiConfig.alias || '--');

            // 显示 API Key 状态
            const apiKeyElem = this.$('#info-api-key');
            if (apiKeyElem) {
                if (activePreset.api_key_configured) {
                    apiKeyElem.textContent = activePreset.api_key_masked || '已配置';
                    apiKeyElem.className = 'config-info-value success';
                } else {
                    apiKeyElem.textContent = '未配置';
                    apiKeyElem.className = 'config-info-value warning';
                }
            }

            // 渲染预设列表
            this._renderPresetList(apiConfig);

            // 填充机器人设置
            this._setVal('#setting-self-name', botConfig.self_name || '');
            this._setVal('#setting-reply-suffix', botConfig.reply_suffix || '');
            this._setChecked('#setting-stream-reply', botConfig.stream_reply !== false);
            this._setChecked('#setting-group-at-only', botConfig.group_reply_only_when_at === true);

            // 填充白名单设置
            this._setChecked('#setting-whitelist-enabled', botConfig.whitelist_enabled === true);
            this._setVal('#setting-whitelist', (botConfig.whitelist || []).join('\n'));

        } catch (error) {
            console.error('[SettingsPage] 加载配置失败:', error);
            Toast.error('加载配置失败');
        }
    }

    _renderPresetList(apiConfig) {
        const presetListElem = this.$('#preset-list');
        if (!presetListElem) return;

        if (apiConfig.presets && apiConfig.presets.length > 0) {
            presetListElem.innerHTML = ''; // Clear

            apiConfig.presets.forEach(p => {
                // Create card element
                const card = document.createElement('div');
                card.className = `preset-card ${p.name === apiConfig.active_preset ? 'active' : ''}`;
                card.dataset.preset = p.name;

                card.innerHTML = `
                    <div class="preset-card-header">
                        <span class="preset-name">${p.name}</span>
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <span class="preset-status ${p.api_key_configured ? 'configured' : 'not-configured'}"></span>
                            <button class="btn btn-secondary btn-icon btn-sm btn-edit-preset" type="button" title="编辑" style="z-index: 2;">
                                <svg class="icon icon-sm" style="pointer-events: none;"><use href="#icon-settings"/></svg>
                            </button>
                            <button class="btn btn-secondary btn-icon btn-sm btn-delete-preset" type="button" title="删除" style="z-index: 2;">
                                <svg class="icon icon-sm" style="pointer-events: none;"><use href="#icon-trash"/></svg>
                            </button>
                        </div>
                    </div>
                    <div class="preset-model">${p.model}</div>
                    <div class="preset-alias">别名: ${p.alias}</div>
                `;
                presetListElem.appendChild(card);
            });

        } else {
            presetListElem.innerHTML = `
                <div class="empty-state">
                    <svg class="icon"><use href="#icon-alert-circle"/></svg>
                    <span class="empty-state-text">暂无预设配置</span>
                </div>
            `;
        }
    }

    // 处理卡片点击（切换预设）
    async _handleCardClick(e, card) {
        // e.target check is handled by delegation caller mostly, but double check
        if (e.target.closest('.btn-edit-preset, .btn-delete-preset')) return;

        const presetName = card.dataset.preset;
        const preset = this.currentApiConfig.presets.find(p => p.name === presetName);

        if (!preset) return;

        // 立即切换逻辑
        const previousActive = this.$('.preset-card.active');
        if (previousActive) previousActive.classList.remove('active');
        card.classList.add('active');

        // 更新内存中的 active_preset
        this.currentApiConfig.active_preset = presetName;

        // 尝试自动保存激活状态
        try {
            await ApiService.saveConfig({
                api: { active_preset: presetName }
            });

            // 更新 UI 显示
            this._setText('#info-active-preset', preset.name);
            this._setText('#info-model', preset.model);
            this._setText('#info-alias', preset.alias);

            // 更新 Key 状态显示
            const apiKeyElem = this.$('#info-api-key');
            if (apiKeyElem) {
                if (preset.api_key_configured) {
                    apiKeyElem.textContent = preset.api_key_masked || '已配置';
                    apiKeyElem.className = 'config-info-value success';
                } else {
                    apiKeyElem.textContent = '未配置';
                    apiKeyElem.className = 'config-info-value warning';
                }
            }

            Toast.success(`已切换至 ${preset.name}`);
        } catch (err) {
            console.error('切换预设失败', err);
            Toast.error('切换失败');
        }
    }

    _handleEditClick(e, btn) {
        e.stopPropagation();
        const card = btn.closest('.preset-card');
        const presetName = card.dataset.preset;
        this._openEditModal(presetName);
    }

    async _handleDeleteClick(e, btn) {
        e.stopPropagation();
        if (!confirm('确定要删除这个预设吗？')) return;

        const card = btn.closest('.preset-card');
        const presetName = card.dataset.preset;

        // 删除逻辑
        const presets = this.currentApiConfig.presets.filter(p => p.name !== presetName);

        try {
            const config = {
                api: {
                    presets: presets
                }
            };

            // 如果删除的是当前激活的，切换到第一个
            if (this.currentApiConfig.active_preset === presetName) {
                if (presets.length > 0) {
                    config.api.active_preset = presets[0].name;
                } else {
                    config.api.active_preset = '';
                }
            }

            const result = await ApiService.saveConfig(config);

            if (result.success) {
                Toast.success('预设已删除');
                await this._loadSettings();
            } else {
                Toast.error(result.message);
            }
        } catch (error) {
            Toast.error('删除失败: ' + error.message);
        }
    }

    // ═══════════════════════════════════════════════════════════════════════
    //                           常规设置保存
    // ═══════════════════════════════════════════════════════════════════════

    async _saveGeneralSettings() {
        const activePresetCard = this.$('.preset-card.active');
        const activePreset = activePresetCard?.dataset.preset || '';

        const config = {
            api: {
                active_preset: activePreset,
            },
            bot: {
                self_name: this._getVal('#setting-self-name'),
                reply_suffix: this._getVal('#setting-reply-suffix'),
                stream_reply: this._getChecked('#setting-stream-reply'),
                group_reply_only_when_at: this._getChecked('#setting-group-at-only'),
                whitelist_enabled: this._getChecked('#setting-whitelist-enabled'),
                whitelist: this._getVal('#setting-whitelist').split('\n').filter(s => s.trim()),
            }
        };

        try {
            const result = await ApiService.saveConfig(config);
            Toast.show(result.message, result.success ? 'success' : 'error');

            if (result.success) {
                await this._loadSettings();
            }
        } catch (error) {
            Toast.error('保存失败: ' + error.message);
        }
    }

    // ═══════════════════════════════════════════════════════════════════════
    //                           模态框逻辑
    // ═══════════════════════════════════════════════════════════════════════

    _openAddModal() {
        this._openEditModal(null);
    }

    _openEditModal(presetName) {
        const isNew = !presetName;
        let preset = null;
        if (!isNew) {
            preset = this.currentApiConfig.presets.find(p => p.name === presetName);
            if (!preset) {
                Toast.error('未找到预设信息');
                return;
            }
        }

        const modalTitle = document.querySelector('.modal-title');
        if (modalTitle) modalTitle.textContent = isNew ? '新增预设' : '编辑预设';

        // Helper
        const setGlobal = (id, val) => { const e = document.getElementById(id); if (e) e.value = val; };

        // 填充数据
        setGlobal('edit-preset-original-name', isNew ? '' : preset.name);
        setGlobal('edit-preset-name', isNew ? '' : preset.name);
        setGlobal('edit-preset-model', isNew ? '' : (preset.model || ''));
        setGlobal('edit-preset-alias', isNew ? '' : (preset.alias || ''));
        setGlobal('edit-preset-key', ''); // Key 不回显

        // 显示 API Key 提示
        const keyInput = document.getElementById('edit-preset-key');
        if (keyInput) {
            if (isNew) {
                keyInput.placeholder = '输入 API Key';
            } else {
                keyInput.placeholder = preset.api_key_configured ? '已配置 (留空保持不变)' : '未配置';
            }
        }

        // 打开模态框
        const modal = document.getElementById('preset-modal');
        if (modal) modal.classList.add('active');
    }

    _closeModal() {
        const modal = document.getElementById('preset-modal');
        if (modal) modal.classList.remove('active');
    }

    async _savePresetFromModal() {
        const getGlobal = (id) => { const e = document.getElementById(id); return e ? e.value : ''; };

        const originalName = getGlobal('edit-preset-original-name');
        const newName = getGlobal('edit-preset-name');
        const model = getGlobal('edit-preset-model');
        const alias = getGlobal('edit-preset-alias');
        const key = getGlobal('edit-preset-key');

        if (!newName || !model) {
            Toast.warning('预设名称和模型不能为空');
            return;
        }

        // 更新本地配置
        const presets = [...(this.currentApiConfig.presets || [])];

        if (!originalName) {
            // ================= 新增模式 =================
            if (presets.some(p => p.name === newName)) {
                Toast.error('预设名称已存在');
                return;
            }

            const newPreset = {
                name: newName,
                model: model,
                alias: alias,
            };

            if (key) {
                newPreset.api_key = key;
            }
            presets.push(newPreset);

        } else {
            // ================= 编辑模式 =================
            const index = presets.findIndex(p => p.name === originalName);

            if (index === -1) {
                Toast.error('预设不存在');
                return;
            }

            // 构建新的预设对象
            const updatedPreset = { ...presets[index] };
            updatedPreset.name = newName;
            updatedPreset.model = model;
            updatedPreset.alias = alias;

            if (key) {
                updatedPreset.api_key = key;
            } else {
                // 如果没输 key，且是编辑模式，删除前端可能存在的 api_key 字段
                delete updatedPreset.api_key;
            }

            // 删除前端展示字段
            delete updatedPreset.api_key_configured;
            delete updatedPreset.api_key_masked;

            presets[index] = updatedPreset;
        }

        try {
            const config = {
                api: {
                    presets: presets
                }
            };

            // 如果改了名字，且当前选中的是这个，需要同时更新 active_preset
            if (originalName !== newName && this.currentApiConfig.active_preset === originalName) {
                config.api.active_preset = newName;
            }

            const result = await ApiService.saveConfig(config);

            if (result.success) {
                Toast.success('预设已更新');
                this._closeModal();
                await this._loadSettings(); // 重新加载
            } else {
                Toast.error(result.message);
            }
        } catch (error) {
            Toast.error('保存失败: ' + error.message);
        }
    }

    // Helpers from original App.js implementation
    _setText(sel, text) { const e = this.$(sel); if (e) e.textContent = text; }
    _setVal(sel, val) { const e = this.$(sel); if (e) e.value = val; }
    _getVal(sel) { const e = this.$(sel); return e ? e.value : ''; }
    _setChecked(sel, checked) { const e = this.$(sel); if (e) e.checked = checked; }
    _getChecked(sel) { const e = this.$(sel); return e ? e.checked : false; }
}

// ═══════════════════════════════════════════════════════════════════════════════
//                               LogsPage
// ═══════════════════════════════════════════════════════════════════════════════

class LogsPage extends PageController {
    constructor() {
        super('LogsPage', 'page-logs');
        this._refreshInterval = null;
    }

    async onInit() {
        await super.onInit();
        this.bindEvent('#btn-refresh-logs', 'click', () => this._loadLogs());
        this.bindEvent('#btn-clear-logs', 'click', async () => {
            try {
                const result = await ApiService.clearLogs();
                Toast.show(result.message, result.success ? 'success' : 'error');
                this._loadLogs();
            } catch (error) {
                Toast.error('清空日志失败');
            }
        });
        this.bindEvent('#setting-auto-scroll', 'change', (e) => {
            this.setState('logs.autoScroll', e.target.checked);
        });
    }

    async onEnter() {
        await super.onEnter();
        await this._loadLogs();
        this._startAutoRefresh();
    }

    async onLeave() {
        await super.onLeave();
        this._stopAutoRefresh();
    }

    async _loadLogs() {
        const container = this.$('#log-content');
        if (!container) return;
        try {
            const result = await ApiService.getLogs(500);
            if (result.success && result.logs) {
                this._renderLogs(container, result.logs);
            }
        } catch (error) {
            container.textContent = '加载日志失败: ' + error.message;
        }
    }

    _renderLogs(container, logs) {
        if (!logs || logs.length === 0) {
            container.textContent = '暂无日志...';
            return;
        }
        container.innerHTML = logs.map(line => this._colorize(line)).join('\n');
        if (this.getState('logs.autoScroll') !== false) {
            container.scrollTop = container.scrollHeight;
        }
    }

    _colorize(line) {
        const escaped = this._escapeHtml(line);
        if (line.includes('ERROR') || line.includes('错误')) return `<span class="log-error">${escaped}</span>`;
        if (line.includes('WARNING') || line.includes('警告')) return `<span class="log-warning">${escaped}</span>`;
        if (line.includes('成功') || line.includes('完成')) return `<span class="log-success">${escaped}</span>`;
        if (line.includes('INFO')) return `<span class="log-info">${escaped}</span>`;
        if (line.includes('发送') || line.includes('回复')) return `<span class="log-send">${escaped}</span>`;
        if (line.includes('收到') || line.includes('接收')) return `<span class="log-receive">${escaped}</span>`;
        return escaped;
    }

    _escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    _startAutoRefresh() {
        this._stopAutoRefresh();
        this._refreshInterval = setInterval(() => this._loadLogs(), 2000);
    }

    _stopAutoRefresh() {
        if (this._refreshInterval) {
            clearInterval(this._refreshInterval);
            this._refreshInterval = null;
        }
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
//                               应用主类
// ═══════════════════════════════════════════════════════════════════════════════

class App {
    constructor() {
        this.pages = {
            dashboard: new DashboardPage(),
            messages: new MessagesPage(),
            settings: new SettingsPage(),
            logs: new LogsPage()
        };
        this.currentPage = null;
        this._statusInterval = null;
    }

    async init() {
        console.log('[App] 正在初始化...');

        await ApiService.init();
        Toast.init();

        await this._setupVersion();
        this._bindGlobalEvents();

        for (const page of Object.values(this.pages)) {
            await page.onInit();
        }

        await this._checkBackendConnection();
        await this._refreshStatus();
        await this._switchPage('dashboard');
        this._startStatusRefresh();

        console.log('[App] 初始化完成');
    }

    async _setupVersion() {
        if (window.electronAPI) {
            const version = await window.electronAPI.getAppVersion();
            const elem = document.getElementById('version-text');
            if (elem) elem.textContent = `v${version}`;
        }
    }

    async _checkBackendConnection() {
        let connected = false;
        if (window.electronAPI) {
            connected = await window.electronAPI.checkBackend();
        } else {
            try { await ApiService.getStatus(); connected = true; } catch { connected = false; }
        }
        StateManager.set('bot.connected', connected);
        this._updateConnectionStatus();
    }

    _bindGlobalEvents() {
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                this._switchPage(item.dataset.page);
            });
        });

        document.getElementById('btn-minimize')?.addEventListener('click', () => window.electronAPI?.minimizeWindow());
        document.getElementById('btn-maximize')?.addEventListener('click', () => window.electronAPI?.maximizeWindow());
        document.getElementById('btn-close')?.addEventListener('click', () => window.electronAPI?.closeWindow());

        if (window.electronAPI) {
            window.electronAPI.onTrayAction?.((action) => {
                if (action === 'start-bot' && !StateManager.get('bot.running')) {
                    EventBus.emit(Events.BOT_START, {});
                } else if (action === 'stop-bot' && StateManager.get('bot.running')) {
                    EventBus.emit(Events.BOT_STOP, {});
                }
            });
        }

        EventBus.on(Events.PAGE_CHANGE, (pageName) => this._switchPage(pageName));
        EventBus.on(Events.BOT_STATUS_CHANGE, () => this._refreshStatus());
    }

    async _switchPage(pageName) {
        if (this.currentPage) await this.currentPage.onLeave();

        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.toggle('active', item.dataset.page === pageName);
        });
        document.querySelectorAll('.page').forEach(page => {
            page.classList.toggle('active', page.id === `page-${pageName}`);
        });

        StateManager.set('currentPage', pageName);
        this.currentPage = this.pages[pageName];

        if (this.currentPage) await this.currentPage.onEnter();
        console.log(`[App] 切换到页面: ${pageName}`);
    }

    async _refreshStatus() {
        try {
            const status = await ApiService.getStatus();
            StateManager.batchUpdate({
                'bot.running': status.running,
                'bot.paused': status.is_paused,
                'bot.connected': true
            });
            this.pages.dashboard?.updateStats(status);
            this._updateConnectionStatus();
        } catch (error) {
            console.error('[App] 刷新状态失败:', error);
            StateManager.set('bot.connected', false);
            this._updateConnectionStatus();
        }
    }

    _updateConnectionStatus() {
        const badge = document.getElementById('status-badge');
        if (!badge) return;
        const dot = badge.querySelector('.status-dot');
        const label = badge.querySelector('.status-label');

        const connected = StateManager.get('bot.connected');
        const running = StateManager.get('bot.running');
        const paused = StateManager.get('bot.paused');

        if (!connected) {
            dot.className = 'status-dot offline';
            label.textContent = '未连接';
        } else if (running) {
            dot.className = paused ? 'status-dot warning' : 'status-dot online';
            label.textContent = paused ? '已暂停' : '运行中';
        } else {
            dot.className = 'status-dot offline';
            label.textContent = '已停止';
        }
    }

    _startStatusRefresh() {
        this._statusInterval = setInterval(() => this._refreshStatus(), 5000);
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
//                               应用启动
// ═══════════════════════════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', async () => {
    const app = new App();
    await app.init();

    // 暴露到全局（调试用）
    window.__app = app;
    window.__state = StateManager;
    window.__events = EventBus;
});
