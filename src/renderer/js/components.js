/**
 * 微信AI助手 - UI 组件
 * 
 * 提供可复用的 UI 组件（使用 SVG 图标）
 */

// ═══════════════════════════════════════════════════════════════════════════════
//                               SVG 图标工具
// ═══════════════════════════════════════════════════════════════════════════════

const Icons = {
    /**
     * 获取 SVG 图标 HTML
     * @param {string} name - 图标名称
     * @param {string} className - 额外的 CSS 类
     */
    get(name, className = '') {
        return `<svg class="icon ${className}"><use href="#icon-${name}"/></svg>`;
    },

    // 常用图标快捷方法
    bot: (cls) => Icons.get('bot', cls),
    user: (cls) => Icons.get('user', cls),
    check: (cls) => Icons.get('check', cls),
    x: (cls) => Icons.get('x', cls),
    alertCircle: (cls) => Icons.get('alert-circle', cls),
    info: (cls) => Icons.get('info', cls),
    inbox: (cls) => Icons.get('inbox', cls),
};

// ═══════════════════════════════════════════════════════════════════════════════
//                               Toast 通知
// ═══════════════════════════════════════════════════════════════════════════════

class Toast {
    constructor() {
        this.container = document.getElementById('toast-container');
    }

    /**
     * 显示通知
     * @param {string} message - 消息内容
     * @param {string} type - 类型 (success/error/warning/info)
     * @param {number} duration - 显示时长 (ms)
     */
    show(message, type = 'info', duration = 3000) {
        const icons = {
            success: Icons.check(),
            error: Icons.x(),
            warning: Icons.alertCircle(),
            info: Icons.info()
        };

        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.innerHTML = `
            <span class="toast-icon">${icons[type]}</span>
            <span class="toast-message">${message}</span>
        `;

        this.container.appendChild(toast);

        // 自动移除
        setTimeout(() => {
            toast.style.animation = 'toastEnter 0.25s ease reverse';
            setTimeout(() => toast.remove(), 250);
        }, duration);
    }

    success(message) { this.show(message, 'success'); }
    error(message) { this.show(message, 'error'); }
    warning(message) { this.show(message, 'warning'); }
    info(message) { this.show(message, 'info'); }
}

// ═══════════════════════════════════════════════════════════════════════════════
//                               消息列表渲染
// ═══════════════════════════════════════════════════════════════════════════════

class MessageRenderer {
    /**
     * 渲染消息列表
     * @param {HTMLElement} container - 容器元素
     * @param {Array} messages - 消息数组
     */
    static render(container, messages) {
        if (!messages || messages.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    ${Icons.get('inbox')}
                    <span class="empty-state-text">暂无消息记录</span>
                </div>
            `;
            return;
        }

        container.innerHTML = messages.map(msg => this.renderItem(msg)).join('');
    }

    /**
     * 渲染单条消息
     */
    static renderItem(msg) {
        const icon = msg.is_self ? Icons.bot() : Icons.user();
        const sender = msg.sender || (msg.is_self ? 'AI助手' : '用户');
        const time = this.formatTime(msg.timestamp);
        const text = this.escapeHtml(msg.content || msg.text || '');

        return `
            <div class="message-item">
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
    }

    /**
     * 格式化时间
     */
    static formatTime(timestamp) {
        if (!timestamp) return '';
        const date = new Date(timestamp * 1000);
        const now = new Date();

        // 同一天只显示时间
        if (date.toDateString() === now.toDateString()) {
            return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
        }

        // 不同天显示日期和时间
        return date.toLocaleString('zh-CN', {
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
    }

    /**
     * HTML 转义
     */
    static escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
//                               日志渲染
// ═══════════════════════════════════════════════════════════════════════════════

class LogRenderer {
    /**
     * 渲染日志
     * @param {HTMLElement} container - 容器元素
     * @param {Array} logs - 日志行数组
     * @param {boolean} autoScroll - 是否自动滚动到底部
     */
    static render(container, logs, autoScroll = true) {
        if (!logs || logs.length === 0) {
            container.textContent = '暂无日志...';
            return;
        }

        // 添加颜色高亮
        const coloredLogs = logs.map(line => this.colorize(line)).join('\n');
        container.innerHTML = coloredLogs;

        // 自动滚动
        if (autoScroll) {
            container.scrollTop = container.scrollHeight;
        }
    }

    /**
     * 日志行着色
     */
    static colorize(line) {
        const escaped = this.escapeHtml(line);

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

    static escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
//                               数字格式化
// ═══════════════════════════════════════════════════════════════════════════════

class Formatter {
    /**
     * 格式化数字（添加千分位）
     */
    static number(value) {
        if (value === undefined || value === null) return '0';
        return value.toLocaleString('zh-CN');
    }

    /**
     * 格式化 token 数量
     */
    static tokens(value) {
        if (!value || value < 1000) return value || '0';
        if (value < 1000000) return (value / 1000).toFixed(1) + 'K';
        return (value / 1000000).toFixed(1) + 'M';
    }

    /**
     * 格式化运行时长
     */
    static uptime(seconds) {
        if (!seconds || seconds <= 0) return '--';

        const h = Math.floor(seconds / 3600);
        const m = Math.floor((seconds % 3600) / 60);

        if (h > 0) {
            return `${h}小时${m}分`;
        }
        return `${m}分钟`;
    }
}

// 创建全局实例
window.Icons = Icons;
window.toast = new Toast();
window.MessageRenderer = MessageRenderer;
window.LogRenderer = LogRenderer;
window.Formatter = Formatter;
