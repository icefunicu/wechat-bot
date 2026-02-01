/**
 * 日志页面控制器
 */

import { PageController } from '../core/PageController.js';
import { apiService } from '../services/ApiService.js';
import { toast } from '../services/NotificationService.js';

export class LogsPage extends PageController {
    constructor() {
        super('LogsPage', 'page-logs');
        this._refreshInterval = null;
    }

    async onInit() {
        await super.onInit();
        this._bindEvents();
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

    // ═══════════════════════════════════════════════════════════════════════
    //                           事件绑定
    // ═══════════════════════════════════════════════════════════════════════

    _bindEvents() {
        this.bindEvent('#btn-refresh-logs', 'click', () => this._loadLogs());

        this.bindEvent('#btn-clear-logs', 'click', async () => {
            try {
                const result = await apiService.clearLogs();
                toast.show(result.message, result.success ? 'success' : 'error');
                this._loadLogs();
            } catch (error) {
                toast.error('清空日志失败');
            }
        });

        this.bindEvent('#setting-auto-scroll', 'change', (e) => {
            this.setState('logs.autoScroll', e.target.checked);
        });
    }

    // ═══════════════════════════════════════════════════════════════════════
    //                           日志加载
    // ═══════════════════════════════════════════════════════════════════════

    async _loadLogs() {
        const container = this.$('#log-content');
        if (!container) return;

        try {
            const result = await apiService.getLogs(500);

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

        const coloredLogs = logs.map(line => this._colorizeLine(line)).join('\n');
        container.innerHTML = coloredLogs;

        // 自动滚动
        const autoScroll = this.getState('logs.autoScroll');
        if (autoScroll !== false) {
            container.scrollTop = container.scrollHeight;
        }
    }

    _colorizeLine(line) {
        const escaped = this._escapeHtml(line);

        // 错误 - 红色
        if (line.includes('ERROR') || line.includes('错误')) {
            return `<span class="log-error">${escaped}</span>`;
        }
        // 警告 - 黄色
        if (line.includes('WARNING') || line.includes('警告')) {
            return `<span class="log-warning">${escaped}</span>`;
        }
        // 成功 - 绿色
        if (line.includes('成功') || line.includes('完成')) {
            return `<span class="log-success">${escaped}</span>`;
        }
        // 信息 - 蓝色
        if (line.includes('INFO')) {
            return `<span class="log-info">${escaped}</span>`;
        }
        // 发送消息
        if (line.includes('发送') || line.includes('回复')) {
            return `<span class="log-send">${escaped}</span>`;
        }
        // 接收消息
        if (line.includes('收到') || line.includes('接收')) {
            return `<span class="log-receive">${escaped}</span>`;
        }

        return escaped;
    }

    _escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // ═══════════════════════════════════════════════════════════════════════
    //                           自动刷新
    // ═══════════════════════════════════════════════════════════════════════

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

export default LogsPage;
