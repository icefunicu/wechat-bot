/**
 * 仪表盘页面控制器
 */

import { PageController } from '../core/PageController.js';
import { Events } from '../core/EventBus.js';
import { apiService } from '../services/ApiService.js';
import { toast } from '../services/NotificationService.js';

export class DashboardPage extends PageController {
    constructor() {
        super('DashboardPage', 'page-dashboard');
        this._lastStats = null;
    }

    async onInit() {
        await super.onInit();
        this._bindEvents();
    }

    async onEnter() {
        await super.onEnter();
        await this._loadRecentMessages();
    }

    // ═══════════════════════════════════════════════════════════════════════
    //                           事件绑定
    // ═══════════════════════════════════════════════════════════════════════

    _bindEvents() {
        // 启动/停止按钮
        this.bindEvent('#btn-toggle-bot', 'click', () => this._toggleBot());

        // 暂停按钮
        this.bindEvent('#btn-pause', 'click', () => this._togglePause());

        // 重启按钮
        this.bindEvent('#btn-restart', 'click', () => this._restartBot());

        // 快捷操作
        this.bindEvent('#btn-open-wechat', 'click', async () => {
            try {
                if (window.electronAPI && window.electronAPI.openWeChat) {
                    await window.electronAPI.openWeChat();
                    toast.success('正在打开微信...');
                } else {
                    toast.info('请手动打开微信客户端');
                }
            } catch (e) {
                console.error('打开微信失败:', e);
                if (e.message && e.message.includes('No handler registered')) {
                    toast.error('请重启应用以应用最新更改');
                } else {
                    toast.error('打开微信失败，请手动打开');
                }
            }
        });

        this.bindEvent('#btn-view-logs', 'click', () => {
            this.emit(Events.PAGE_CHANGE, 'logs');
        });

        this.bindEvent('#btn-refresh-status', 'click', async () => {
            this.emit(Events.BOT_STATUS_CHANGE, {});
            toast.success('状态已刷新');
        });

        this.bindEvent('#btn-minimize-tray', 'click', () => {
            window.electronAPI?.minimizeToTray();
        });

        this.bindEvent('#btn-view-all-messages', 'click', () => {
            this.emit(Events.PAGE_CHANGE, 'messages');
        });

        // 监听状态变化
        this.watchState('bot.*', () => this._updateBotUI());
    }

    // ═══════════════════════════════════════════════════════════════════════
    //                           机器人控制
    // ═══════════════════════════════════════════════════════════════════════

    async _toggleBot() {
        const btn = this.$('#btn-toggle-bot');
        const btnText = btn?.querySelector('span');
        if (!btn) return;

        btn.disabled = true;

        try {
            const isRunning = this.getState('bot.running');
            if (isRunning) {
                btnText.textContent = '停止中...';
                const result = await apiService.stopBot();
                toast.show(result.message, result.success ? 'success' : 'error');
            } else {
                btnText.textContent = '启动中...';
                const result = await apiService.startBot();
                toast.show(result.message, result.success ? 'success' : 'error');
            }

            // 延迟触发状态刷新
            setTimeout(() => this.emit(Events.BOT_STATUS_CHANGE, {}), 1000);
        } catch (error) {
            toast.error(toast.getErrorMessage(error, '操作失败'));
        } finally {
            btn.disabled = false;
        }
    }

    async _togglePause() {
        try {
            const isPaused = this.getState('bot.paused');
            if (isPaused) {
                const result = await apiService.resumeBot();
                toast.show(result.message, result.success ? 'success' : 'error');
            } else {
                const result = await apiService.pauseBot();
                toast.show(result.message, result.success ? 'success' : 'error');
            }

            this.emit(Events.BOT_STATUS_CHANGE, {});
        } catch (error) {
            toast.error(toast.getErrorMessage(error, '操作失败'));
        }
    }

    async _restartBot() {
        try {
            toast.info('正在重启机器人...');
            const result = await apiService.restartBot();
            toast.show(result.message, result.success ? 'success' : 'error');

            setTimeout(() => this.emit(Events.BOT_STATUS_CHANGE, {}), 2000);
        } catch (error) {
            toast.error(toast.getErrorMessage(error, '重启失败'));
        }
    }

    // ═══════════════════════════════════════════════════════════════════════
    //                           UI 更新
    // ═══════════════════════════════════════════════════════════════════════

    _updateBotUI() {
        const isRunning = this.getState('bot.running');
        const isPaused = this.getState('bot.paused');

        // 更新机器人状态显示
        const stateElem = this.$('#bot-state');
        if (stateElem) {
            const dot = stateElem.querySelector('.bot-state-dot');
            const text = stateElem.querySelector('.bot-state-text');

            if (isRunning) {
                if (isPaused) {
                    dot.className = 'bot-state-dot paused';
                    text.textContent = '已暂停';
                } else {
                    dot.className = 'bot-state-dot online';
                    text.textContent = '运行中';
                }
            } else {
                dot.className = 'bot-state-dot offline';
                text.textContent = '离线';
            }
        }

        // 更新暂停按钮文本
        const pauseBtn = this.$('#btn-pause');
        const pauseText = pauseBtn?.querySelector('span');
        if (pauseText) {
            pauseText.textContent = isPaused ? '恢复' : '暂停';
        }

        // 更新切换按钮
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

    // ═══════════════════════════════════════════════════════════════════════
    //                           消息加载
    // ═══════════════════════════════════════════════════════════════════════

    async _loadRecentMessages() {
        try {
            const result = await apiService.getMessages();
            const container = this.$('#recent-messages');

            if (result.success && result.messages && container) {
                const messages = result.messages.slice(-5);
                this._renderMessages(container, messages);
            }
        } catch (error) {
            console.error('[DashboardPage] 加载最近消息失败:', error);
        }
    }

    _renderMessages(container, messages) {
        if (!messages || messages.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <svg class="icon"><use href="#icon-inbox"/></svg>
                    <span class="empty-state-text">暂无消息记录</span>
                </div>
            `;
            return;
        }

        container.innerHTML = messages.map((msg, index) => {
            const icon = msg.is_self
                ? '<svg class="icon"><use href="#icon-bot"/></svg>'
                : '<svg class="icon"><use href="#icon-user"/></svg>';
            const sender = msg.sender || (msg.is_self ? 'AI助手' : '用户');
            const time = this._formatTime(msg.timestamp);
            const text = this._escapeHtml(msg.content || msg.text || '');
            const roleClass = msg.is_self ? 'is-self' : 'is-user';

            return `
                <div class="message-item ${roleClass}" style="animation-delay: ${index * 0.05}s">
                    <div class="message-avatar">${icon}</div>
                    <div class="message-body">
                        <div class="message-meta">
                            <span class="message-sender">${sender}</span>
                            <span class="message-time">${time}</span>
                        </div>
                        <div class="message-text">${text}</div>
                    </div>
                </div>
            `;
        }).join('');
    }

    _formatTime(timestamp) {
        if (!timestamp) return '';
        const date = new Date(timestamp * 1000);
        const now = new Date();

        if (date.toDateString() === now.toDateString()) {
            return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
        }

        return date.toLocaleString('zh-CN', {
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
    }

    _escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * 更新统计数据
     */
    updateStats(stats) {
        const nextStats = {
            uptime: stats.uptime || '--',
            today_replies: stats.today_replies ?? 0,
            today_tokens: stats.today_tokens ?? 0,
            total_replies: stats.total_replies ?? 0
        };
        const uptimeElem = this.$('#stat-uptime');
        const todayRepliesElem = this.$('#stat-today-replies');
        const todayTokensElem = this.$('#stat-today-tokens');
        const totalRepliesElem = this.$('#stat-total-replies');

        if (!this._lastStats || this._lastStats.uptime !== nextStats.uptime) {
            if (uptimeElem) uptimeElem.textContent = nextStats.uptime;
        }
        if (!this._lastStats || this._lastStats.today_replies !== nextStats.today_replies) {
            if (todayRepliesElem) todayRepliesElem.textContent = this._formatNumber(nextStats.today_replies);
        }
        if (!this._lastStats || this._lastStats.today_tokens !== nextStats.today_tokens) {
            if (todayTokensElem) todayTokensElem.textContent = this._formatTokens(nextStats.today_tokens);
        }
        if (!this._lastStats || this._lastStats.total_replies !== nextStats.total_replies) {
            if (totalRepliesElem) totalRepliesElem.textContent = this._formatNumber(nextStats.total_replies);
        }

        this._lastStats = nextStats;
    }

    _formatNumber(value) {
        if (value === undefined || value === null) return '0';
        return value.toLocaleString('zh-CN');
    }

    _formatTokens(value) {
        if (!value || value < 1000) return value || '0';
        if (value < 1000000) return (value / 1000).toFixed(1) + 'K';
        return (value / 1000000).toFixed(1) + 'M';
    }
}

export default DashboardPage;
