/**
 * 消息页面控制器
 */

import { PageController } from '../core/PageController.js';
import { Events } from '../core/EventBus.js';
import { apiService } from '../services/ApiService.js';

export class MessagesPage extends PageController {
    constructor() {
        super('MessagesPage', 'page-messages');
        this._allMessages = [];
        this._pageSize = 100;
        this._offset = 0;
        this._total = 0;
        this._activeChatId = '';
        this._keyword = '';
        this._chats = [];
        this._searchTimer = null;
        this._messageMap = new Map();
    }

    async onInit() {
        await super.onInit();
        this._bindEvents();
    }

    async onEnter() {
        await super.onEnter();
        await this._reloadMessages();
    }

    // ═══════════════════════════════════════════════════════════════════════
    //                           事件绑定
    // ═══════════════════════════════════════════════════════════════════════

    _bindEvents() {
        this.bindEvent('#btn-refresh-messages', 'click', () => this._reloadMessages());

        this.bindEvent('#message-search', 'input', (e) => {
            this._keyword = e.target.value.trim();
            if (this._searchTimer) {
                clearTimeout(this._searchTimer);
            }
            this._searchTimer = setTimeout(() => this._reloadMessages(), 250);
        });

        this.bindEvent('#message-chat-filter', 'change', (e) => {
            this._activeChatId = e.target.value || '';
            this._reloadMessages();
        });

        this.bindEvent('#btn-load-more-messages', 'click', () => {
            this._loadMessages({ append: true });
        });

        this.bindEvent('#all-messages', 'click', (event) => {
            const target = event.target.closest('.message-item');
            if (!target) {
                return;
            }
            const messageId = target.dataset.messageId;
            if (messageId) {
                this._openMessageDetails(messageId);
            }
        });

        this.bindEvent('#btn-close-message-detail', 'click', () => this._closeMessageDetails());
        this.bindEvent('#message-detail-modal', 'click', (event) => {
            if (event.target?.id === 'message-detail-modal') {
                this._closeMessageDetails();
            }
        });

        this.listenEvent(Events.MESSAGE_RECEIVED, (message) => this._handleIncomingEvent(message));
    }

    // ═══════════════════════════════════════════════════════════════════════
    //                           消息加载
    // ═══════════════════════════════════════════════════════════════════════

    async _reloadMessages() {
        this._offset = 0;
        await this._loadMessages({ append: false, forceLoading: true });
    }

    async _loadMessages(options = {}) {
        const { append = false, forceLoading = false } = options;
        const container = this.$('#all-messages');
        if (!container) return;

        if (!append || forceLoading) {
            container.innerHTML = `
                <div class="loading-state">
                    <div class="spinner"></div>
                    <span>加载中...</span>
                </div>
            `;
        }

        try {
            const result = await apiService.getMessages({
                limit: this._pageSize,
                offset: append ? this._offset : 0,
                chatId: this._activeChatId,
                keyword: this._keyword
            });

            if (result.success && result.messages) {
                this._chats = Array.isArray(result.chats) ? result.chats : this._chats;
                this._renderChatOptions();

                this._allMessages = append
                    ? [...this._allMessages, ...result.messages]
                    : [...result.messages];
                this._offset = (append ? this._offset : 0) + result.messages.length;
                this._total = result.total ?? this._allMessages.length;
                this._renderMessages(container, this._allMessages);
                this._updateMeta();
                this._updateLoadMore(result.has_more);
            } else {
                this._allMessages = [];
                this._total = 0;
                container.innerHTML = `
                    <div class="empty-state">
                        <svg class="icon"><use href="#icon-inbox"/></svg>
                        <span class="empty-state-text">暂无消息记录</span>
                    </div>
                `;
                this._updateMeta();
                this._updateLoadMore(false);
            }
        } catch (error) {
            this._allMessages = [];
            this._total = 0;
            container.innerHTML = `
                <div class="empty-state">
                    <svg class="icon"><use href="#icon-alert-circle"/></svg>
                    <span class="empty-state-text">加载失败</span>
                </div>
            `;
            this._updateMeta();
            this._updateLoadMore(false);
        }
    }

    _renderChatOptions() {
        const select = this.$('#message-chat-filter');
        if (!select) {
            return;
        }
        const options = ['<option value="">全部会话</option>'];
        for (const chat of this._chats) {
            const chatId = this._escapeHtml(chat.chat_id || '');
            const displayName = this._escapeHtml(chat.display_name || chat.chat_id || '未命名会话');
            const count = Number(chat.message_count || 0).toLocaleString('zh-CN');
            options.push(`<option value="${chatId}">${displayName} (${count})</option>`);
        }
        select.innerHTML = options.join('');
        select.value = this._activeChatId;
    }

    _updateMeta() {
        const totalElem = this.$('#message-total-count');
        const filterElem = this.$('#message-filter-summary');
        if (totalElem) {
            totalElem.textContent = `${this._allMessages.length}/${this._total || 0} 条`;
        }
        if (filterElem) {
            const parts = [];
            if (this._activeChatId) {
                const currentChat = this._chats.find(chat => chat.chat_id === this._activeChatId);
                parts.push(currentChat?.display_name || this._activeChatId);
            }
            if (this._keyword) {
                parts.push(`关键词: ${this._keyword}`);
            }
            filterElem.textContent = parts.length ? parts.join(' · ') : '全部消息';
        }
    }

    _updateLoadMore(hasMore) {
        const button = this.$('#btn-load-more-messages');
        if (!button) {
            return;
        }
        button.hidden = !hasMore;
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

        this._messageMap = new Map(
            messages.map((msg, index) => [String(msg.id ?? `msg-${index}`), msg])
        );

        container.innerHTML = messages.map((msg, index) => {
            const icon = msg.is_self
                ? '<svg class="icon"><use href="#icon-bot"/></svg>'
                : '<svg class="icon"><use href="#icon-user"/></svg>';
            const sender = msg.sender || (msg.is_self ? 'AI助手' : '用户');
            const time = this._formatTime(msg.timestamp);
            const text = this._escapeHtml(msg.content || msg.text || '');
            const roleClass = msg.is_self ? 'is-self' : 'is-user';
            const messageId = this._escapeHtml(String(msg.id ?? `msg-${index}`));
            const detailBadge = this._hasMetadataDetails(msg.metadata)
                ? '<span class="message-detail-badge">详情</span>'
                : '';

            return `
                <div class="message-item ${roleClass}" data-chat-id="${this._escapeHtml(msg.wx_id || '')}" data-message-id="${messageId}" style="animation-delay: ${index * 0.03}s">
                    <div class="message-avatar">${icon}</div>
                    <div class="message-body">
                        <div class="message-meta">
                            <span class="message-sender">${sender}</span>
                            <span class="message-time">${time}</span>
                            ${detailBadge}
                        </div>
                        <div class="message-text">${text}</div>
                    </div>
                </div>
            `;
        }).join('');
    }

    _handleIncomingEvent(message) {
        if (!message) {
            return;
        }
        const chatId = message.chat_id || '';
        if (this._activeChatId && chatId !== this._activeChatId) {
            return;
        }
        if (this._keyword) {
            const haystack = `${message.sender || ''} ${message.content || ''}`.toLowerCase();
            if (!haystack.includes(this._keyword.toLowerCase())) {
                return;
            }
        }

        const normalized = {
            id: message.id || `live-${Date.now()}`,
            wx_id: chatId || message.chat_name || '',
            sender: message.direction === 'outgoing' ? (message.sender || 'AI助手') : (message.sender || message.chat_name || '用户'),
            content: message.content || '',
            timestamp: message.timestamp,
            is_self: message.direction === 'outgoing',
            metadata: message.metadata || {}
        };
        const existingChat = this._chats.find(chat => chat.chat_id === normalized.wx_id);
        if (existingChat) {
            existingChat.message_count = Number(existingChat.message_count || 0) + 1;
            existingChat.last_timestamp = normalized.timestamp;
        } else if (normalized.wx_id) {
            this._chats = [{
                chat_id: normalized.wx_id,
                display_name: message.chat_name || normalized.sender || normalized.wx_id,
                message_count: 1,
                last_timestamp: normalized.timestamp
            }, ...this._chats];
        }
        this._chats.sort((left, right) => Number(right.last_timestamp || 0) - Number(left.last_timestamp || 0));
        this._renderChatOptions();
        this._allMessages = [normalized, ...this._allMessages].slice(0, Math.max(this._offset, this._pageSize));
        this._total += 1;
        const container = this.$('#all-messages');
        if (container && this.isActive()) {
            this._renderMessages(container, this._allMessages);
            this._updateMeta();
        }
    }

    _openMessageDetails(messageId) {
        const modal = this.$('#message-detail-modal');
        const body = this.$('#message-detail-body');
        const message = this._messageMap.get(String(messageId));
        if (!modal || !body || !message) {
            return;
        }
        body.innerHTML = this._renderMessageDetailContent(message);
        modal.classList.add('active');
    }

    _closeMessageDetails() {
        this.$('#message-detail-modal')?.classList.remove('active');
    }

    _renderMessageDetailContent(message) {
        const metadata = message.metadata || {};
        const blocks = [];

        blocks.push(`
            <div class="detail-group">
                <div class="detail-group-title">消息概览</div>
                <div class="detail-grid">
                    <div><span>发送者</span><strong>${this._escapeHtml(message.sender || '--')}</strong></div>
                    <div><span>时间</span><strong>${this._escapeHtml(this._formatTime(message.timestamp) || '--')}</strong></div>
                    <div><span>角色</span><strong>${message.is_self ? 'AI 回复' : '用户消息'}</strong></div>
                    <div><span>会话</span><strong>${this._escapeHtml(message.wx_id || '--')}</strong></div>
                </div>
            </div>
        `);

        if (metadata.model || metadata.preset || metadata.engine) {
            blocks.push(`
                <div class="detail-group">
                    <div class="detail-group-title">模型信息</div>
                    <div class="detail-grid">
                        <div><span>预设</span><strong>${this._escapeHtml(metadata.preset || '--')}</strong></div>
                        <div><span>模型</span><strong>${this._escapeHtml(metadata.model || '--')}</strong></div>
                        <div><span>别名</span><strong>${this._escapeHtml(metadata.model_alias || '--')}</strong></div>
                        <div><span>引擎</span><strong>${this._escapeHtml(metadata.engine || '--')}</strong></div>
                    </div>
                </div>
            `);
        }

        if (metadata.tokens) {
            blocks.push(`
                <div class="detail-group">
                    <div class="detail-group-title">Token 估算</div>
                    <div class="detail-grid">
                        <div><span>用户输入</span><strong>${this._escapeHtml(String(metadata.tokens.user ?? 0))}</strong></div>
                        <div><span>模型回复</span><strong>${this._escapeHtml(String(metadata.tokens.reply ?? 0))}</strong></div>
                        <div><span>总计</span><strong>${this._escapeHtml(String(metadata.tokens.total ?? 0))}</strong></div>
                        <div><span>回复模式</span><strong>${metadata.streamed ? '流式' : '单次'}</strong></div>
                    </div>
                </div>
            `);
        }

        if (metadata.timings && Object.keys(metadata.timings).length > 0) {
            const timingRows = Object.entries(metadata.timings).map(([key, value]) => `
                <div><span>${this._escapeHtml(key)}</span><strong>${this._escapeHtml(String(value))}s</strong></div>
            `).join('');
            blocks.push(`
                <div class="detail-group">
                    <div class="detail-group-title">执行耗时</div>
                    <div class="detail-grid">${timingRows}</div>
                </div>
            `);
        }

        if (metadata.emotion) {
            const emotion = metadata.emotion;
            const keywords = Array.isArray(emotion.keywords_matched) ? emotion.keywords_matched.join('、') : '';
            blocks.push(`
                <div class="detail-group">
                    <div class="detail-group-title">情绪识别</div>
                    <div class="detail-grid">
                        <div><span>情绪</span><strong>${this._escapeHtml(emotion.emotion || '--')}</strong></div>
                        <div><span>置信度</span><strong>${this._escapeHtml(String(emotion.confidence ?? '--'))}</strong></div>
                        <div><span>强度</span><strong>${this._escapeHtml(String(emotion.intensity ?? '--'))}</strong></div>
                        <div><span>关键词</span><strong>${this._escapeHtml(keywords || '--')}</strong></div>
                    </div>
                </div>
            `);
        }

        if (metadata.context_summary) {
            blocks.push(this._renderContextSummary(metadata.context_summary));
        }

        if (!this._hasMetadataDetails(metadata)) {
            blocks.push(`
                <div class="detail-empty">
                    当前消息暂无可展示的详细元数据。
                </div>
            `);
        }

        return blocks.join('');
    }

    _renderContextSummary(summary) {
        const renderList = (title, items) => {
            if (!Array.isArray(items) || items.length === 0) {
                return '';
            }
            return `
                <div class="detail-subsection">
                    <div class="detail-subtitle">${this._escapeHtml(title)}</div>
                    <ul class="detail-list">
                        ${items.map(item => `<li>${this._escapeHtml(item)}</li>`).join('')}
                    </ul>
                </div>
            `;
        };

        return `
            <div class="detail-group">
                <div class="detail-group-title">思考上下文</div>
                <div class="detail-grid">
                    <div><span>短期上下文</span><strong>${this._escapeHtml(String(summary.short_term_messages ?? 0))}</strong></div>
                    <div><span>导出语料命中</span><strong>${this._escapeHtml(String(summary.export_rag_hits ?? 0))}</strong></div>
                    <div><span>运行记忆命中</span><strong>${this._escapeHtml(String(summary.runtime_memory_hits ?? 0))}</strong></div>
                </div>
                ${renderList('短期上下文预览', summary.short_term_preview)}
                ${renderList('导出语料召回', summary.export_rag_snippets)}
                ${renderList('运行记忆召回', summary.runtime_memory_snippets)}
            </div>
        `;
    }

    _hasMetadataDetails(metadata) {
        return !!metadata && Object.keys(metadata).length > 0;
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
