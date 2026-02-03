/**
 * 消息页面控制器
 */

import { PageController } from '../core/PageController.js';
import { apiService } from '../services/ApiService.js';
import { toast } from '../services/NotificationService.js';

export class MessagesPage extends PageController {
    constructor() {
        super('MessagesPage', 'page-messages');
        this._allMessages = [];
    }

    async onInit() {
        await super.onInit();
        this._bindEvents();
    }

    async onEnter() {
        await super.onEnter();
        await this._loadMessages();
    }

    // ═══════════════════════════════════════════════════════════════════════
    //                           事件绑定
    // ═══════════════════════════════════════════════════════════════════════

    _bindEvents() {
        this.bindEvent('#btn-refresh-messages', 'click', () => this._loadMessages());

        this.bindEvent('#message-search', 'input', (e) => {
            this._filterMessages(e.target.value);
        });
    }

    // ═══════════════════════════════════════════════════════════════════════
    //                           消息加载
    // ═══════════════════════════════════════════════════════════════════════

    async _loadMessages() {
        const container = this.$('#all-messages');
        if (!container) return;

        container.innerHTML = `
            <div class="loading-state">
                <div class="spinner"></div>
                <span>加载中...</span>
            </div>
        `;

        try {
            const result = await apiService.getMessages();

            if (result.success && result.messages) {
                this._allMessages = result.messages;
                this._renderMessages(container, result.messages);
            } else {
                container.innerHTML = `
                    <div class="empty-state">
                        <svg class="icon"><use href="#icon-inbox"/></svg>
                        <span class="empty-state-text">暂无消息记录</span>
                    </div>
                `;
            }
        } catch (error) {
            container.innerHTML = `
                <div class="empty-state">
                    <svg class="icon"><use href="#icon-alert-circle"/></svg>
                    <span class="empty-state-text">加载失败</span>
                </div>
            `;
        }
    }

    _filterMessages(keyword) {
        const items = this.$$('#all-messages .message-item');
        const lowerKeyword = keyword.toLowerCase();

        items.forEach(item => {
            const text = item.textContent.toLowerCase();
            item.style.display = text.includes(lowerKeyword) ? '' : 'none';
        });
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
                <div class="message-item ${roleClass}" style="animation-delay: ${index * 0.03}s">
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
}

export default MessagesPage;
