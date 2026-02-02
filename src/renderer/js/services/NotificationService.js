/**
 * 通知服务
 * 
 * 提供 Toast 通知功能
 */

import { eventBus, Events } from '../core/EventBus.js';

class NotificationService {
    constructor() {
        this.container = null;
        this.defaultDuration = 3000;
    }

    /**
     * 初始化通知容器
     */
    init() {
        this.container = document.getElementById('toast-container');
        if (!this.container) {
            console.warn('[NotificationService] Toast 容器未找到');
        }
    }

    /**
     * 显示通知
     * @param {string} message - 消息内容
     * @param {string} type - 类型 (success/error/warning/info)
     * @param {number} duration - 显示时长 (ms)
     */
    show(message, type = 'info', duration = this.defaultDuration) {
        if (!this.container) {
            this.init();
        }

        const icons = {
            success: this._getIconSvg('check'),
            error: this._getIconSvg('x'),
            warning: this._getIconSvg('alert-circle'),
            info: this._getIconSvg('info')
        };

        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.innerHTML = `
            <span class="toast-icon">${icons[type]}</span>
            <span class="toast-message">${message}</span>
        `;

        this.container.appendChild(toast);

        // 触发事件
        eventBus.emit(Events.TOAST_SHOW, { message, type });

        // 自动移除
        setTimeout(() => {
            toast.style.animation = 'toastEnter 0.25s ease reverse';
            setTimeout(() => toast.remove(), 250);
        }, duration);
    }

    /**
     * 成功通知
     */
    success(message, duration) {
        this.show(message, 'success', duration);
    }

    /**
     * 错误通知
     */
    error(message, duration) {
        this.show(message, 'error', duration);
    }

    /**
     * 警告通知
     */
    warning(message, duration) {
        this.show(message, 'warning', duration);
    }

    /**
     * 信息通知
     */
    info(message, duration) {
        this.show(message, 'info', duration);
    }

    getErrorMessage(error, fallback = '操作失败') {
        if (!error) return fallback;
        if (typeof error === 'string') return error;
        if (error.message) return error.message;
        return fallback;
    }

    /**
     * 获取 SVG 图标
     */
    _getIconSvg(name) {
        return `<svg class="icon"><use href="#icon-${name}"/></svg>`;
    }
}

// 导出单例
export const notificationService = new NotificationService();
export default notificationService;

// 同时提供 toast 别名以保持向后兼容
export const toast = notificationService;
