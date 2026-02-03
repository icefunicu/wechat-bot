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
        this._logLines = [];
        this._maxLines = 500;
        this._refreshIntervalMs = 2000;
        this._isLoading = false;
        this._searchKeyword = '';
        this._levelFilter = '';
        this._wrapEnabled = false;
        this._lastUpdatedAt = null;
    }

    async onInit() {
        await super.onInit();
        this._bindEvents();
    }

    async onEnter() {
        await super.onEnter();
        const linesSelect = this.$('#log-lines');
        if (linesSelect) {
            const value = parseInt(linesSelect.value, 10);
            if (!Number.isNaN(value)) {
                this._maxLines = value;
            }
        }
        const wrapToggle = this.$('#setting-wrap');
        if (wrapToggle) {
            this._wrapEnabled = wrapToggle.checked;
            this._updateWrap();
        }
        await this._loadLogs(true);
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
        this.bindEvent('#btn-refresh-logs', 'click', () => this._loadLogs(true));

        this.bindEvent('#btn-clear-logs', 'click', async () => {
            try {
                const result = await apiService.clearLogs();
                toast.show(result.message, result.success ? 'success' : 'error');
                this._logLines = [];
                this._loadLogs(true);
            } catch (error) {
                toast.error('清空日志失败');
            }
        });

        this.bindEvent('#setting-auto-scroll', 'change', (e) => {
            this.setState('logs.autoScroll', e.target.checked);
        });

        this.bindEvent('#setting-auto-refresh', 'change', (e) => {
            this.setState('logs.autoRefresh', e.target.checked);
            if (e.target.checked) {
                this._startAutoRefresh();
            } else {
                this._stopAutoRefresh();
            }
        });

        this.bindEvent('#setting-wrap', 'change', (e) => {
            this._wrapEnabled = e.target.checked;
            this._updateWrap();
        });

        this.bindEvent('#log-search', 'input', (e) => {
            this._searchKeyword = e.target.value.trim();
            this._refreshFilteredView();
        });

        this.bindEvent('#log-level', 'change', (e) => {
            this._levelFilter = e.target.value;
            this._refreshFilteredView();
        });

        this.bindEvent('#log-lines', 'change', (e) => {
            const value = parseInt(e.target.value, 10);
            if (!Number.isNaN(value)) {
                this._maxLines = value;
                this._loadLogs(true);
            }
        });

        this.bindEvent('#btn-copy-logs', 'click', () => this._copyLogs());
        this.bindEvent('#btn-export-logs', 'click', () => this._exportLogs());
    }

    // ═══════════════════════════════════════════════════════════════════════
    //                           日志加载
    // ═══════════════════════════════════════════════════════════════════════

    async _loadLogs(force = false) {
        const container = this.$('#log-content');
        if (!container) return;
        if (this._isLoading) return;
        this._isLoading = true;

        try {
            const result = await apiService.getLogs(this._maxLines);

            if (result.success && result.logs) {
                const mergeResult = this._mergeLogs(this._logLines, result.logs, force);
                this._logLines = mergeResult.merged;
                if (this._hasFilters()) {
                    this._refreshFilteredView();
                } else if (mergeResult.mode === 'append') {
                    this._appendLogs(container, mergeResult.appendLines);
                    this._updateMeta(this._logLines.length, this._logLines.length);
                } else {
                    this._renderLogs(container, this._logLines);
                    this._updateMeta(this._logLines.length, this._logLines.length);
                }
                this._lastUpdatedAt = Date.now();
                this._updateLastUpdated();
            }
        } catch (error) {
            container.textContent = toast.getErrorMessage(error, '加载日志失败');
        } finally {
            this._isLoading = false;
        }
    }

    _renderLogs(container, logs, emptyText = '暂无日志...') {
        if (!logs || logs.length === 0) {
            container.textContent = emptyText;
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

    _appendLogs(container, logs) {
        if (!logs || logs.length === 0) return;
        if (container.textContent === '暂无日志...' || container.textContent === '等待日志加载...') {
            this._renderLogs(container, logs);
            return;
        }
        const coloredLogs = logs.map(line => this._colorizeLine(line)).join('\n');
        container.insertAdjacentHTML('beforeend', '\n' + coloredLogs);
        const autoScroll = this.getState('logs.autoScroll');
        if (autoScroll !== false) {
            container.scrollTop = container.scrollHeight;
        }
    }

    _mergeLogs(existing, incoming, force = false) {
        if (force || existing.length === 0) {
            return { mode: 'replace', merged: incoming, appendLines: [] };
        }
        if (!incoming || incoming.length === 0) {
            return { mode: 'append', merged: existing, appendLines: [] };
        }
        const maxOverlap = Math.min(existing.length, incoming.length);
        let overlap = 0;
        for (let i = maxOverlap; i > 0; i--) {
            const tail = existing.slice(-i);
            const head = incoming.slice(0, i);
            let matched = true;
            for (let j = 0; j < i; j++) {
                if (tail[j] !== head[j]) {
                    matched = false;
                    break;
                }
            }
            if (matched) {
                overlap = i;
                break;
            }
        }
        if (overlap === 0) {
            return { mode: 'replace', merged: incoming, appendLines: [] };
        }
        const appendLines = incoming.slice(overlap);
        let merged = existing.concat(appendLines);
        if (merged.length > this._maxLines) {
            merged = merged.slice(-this._maxLines);
            return { mode: 'replace', merged, appendLines: [] };
        }
        return { mode: 'append', merged, appendLines };
    }

    _colorizeLine(line) {
        const escaped = this._escapeHtml(line);
        const level = this._getLineLevel(line);
        if (!level) {
            return escaped;
        }
        return `<span class="log-${level}">${escaped}</span>`;
    }

    _getLineLevel(line) {
        if (line.includes('ERROR') || line.includes('错误')) {
            return 'error';
        }
        if (line.includes('WARNING') || line.includes('警告')) {
            return 'warning';
        }
        if (line.includes('成功') || line.includes('完成')) {
            return 'success';
        }
        if (line.includes('INFO') || line.includes('信息')) {
            return 'info';
        }
        if (line.includes('发送') || line.includes('回复')) {
            return 'send';
        }
        if (line.includes('收到') || line.includes('接收')) {
            return 'receive';
        }
        return '';
    }

    _hasFilters() {
        return Boolean(this._searchKeyword || this._levelFilter);
    }

    _getFilteredLogs() {
        if (!this._logLines || this._logLines.length === 0) return [];
        const keyword = this._searchKeyword.toLowerCase();
        const level = this._levelFilter;
        return this._logLines.filter((line) => {
            if (keyword && !line.toLowerCase().includes(keyword)) {
                return false;
            }
            if (level) {
                return this._getLineLevel(line) === level;
            }
            return true;
        });
    }

    _refreshFilteredView() {
        const container = this.$('#log-content');
        if (!container) return;
        const filtered = this._getFilteredLogs();
        const emptyText = this._logLines.length ? '没有匹配的日志...' : '暂无日志...';
        this._renderLogs(container, filtered, emptyText);
        this._updateMeta(this._logLines.length, filtered.length);
    }

    _updateWrap() {
        const wrapper = this.$('.log-container');
        if (!wrapper) return;
        wrapper.classList.toggle('wrap', this._wrapEnabled);
    }

    _updateMeta(totalCount, visibleCount) {
        const countElem = this.$('#log-count');
        const visibleElem = this.$('#log-visible-count');
        if (countElem) countElem.textContent = `${totalCount} 行`;
        if (visibleElem) visibleElem.textContent = `${visibleCount} 匹配`;
    }

    _updateLastUpdated() {
        const updatedElem = this.$('#log-updated');
        if (!updatedElem) return;
        if (!this._lastUpdatedAt) {
            updatedElem.textContent = '--';
            return;
        }
        const date = new Date(this._lastUpdatedAt);
        updatedElem.textContent = date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    }

    async _copyLogs() {
        const logs = this._hasFilters() ? this._getFilteredLogs() : this._logLines;
        if (!logs || logs.length === 0) {
            toast.info('暂无可复制日志');
            return;
        }
        const text = logs.join('\n');
        try {
            if (navigator.clipboard?.writeText) {
                await navigator.clipboard.writeText(text);
            } else {
                const textarea = document.createElement('textarea');
                textarea.value = text;
                textarea.style.position = 'fixed';
                textarea.style.opacity = '0';
                document.body.appendChild(textarea);
                textarea.select();
                document.execCommand('copy');
                document.body.removeChild(textarea);
            }
            toast.success('日志已复制');
        } catch (error) {
            toast.error('复制失败');
        }
    }

    _exportLogs() {
        const logs = this._hasFilters() ? this._getFilteredLogs() : this._logLines;
        if (!logs || logs.length === 0) {
            toast.info('暂无可导出日志');
            return;
        }
        const text = logs.join('\n');
        const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
        a.href = url;
        a.download = `logs-${timestamp}.txt`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        toast.success('日志已导出');
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
        if (this.getState('logs.autoRefresh') === false) return;
        this._refreshInterval = setInterval(() => {
            // 页面不可见时不刷新，节省资源
            if (!document.hidden) {
                this._loadLogs();
            }
        }, this._refreshIntervalMs);
    }

    _stopAutoRefresh() {
        if (this._refreshInterval) {
            clearInterval(this._refreshInterval);
            this._refreshInterval = null;
        }
    }
}

export default LogsPage;
