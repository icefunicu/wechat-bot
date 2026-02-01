/**
 * 微信AI助手 - API 封装
 * 
 * 封装所有与 Flask 后端的通信
 */

class API {
    constructor() {
        this.baseUrl = 'http://localhost:5000';
        this.initialized = false;
    }

    /**
     * 初始化 API（从 Electron 获取实际的 Flask URL）
     */
    async init() {
        if (window.electronAPI) {
            this.baseUrl = await window.electronAPI.getFlaskUrl();
        }
        this.initialized = true;
    }

    /**
     * 发起 HTTP 请求
     */
    async request(endpoint, options = {}) {
        if (!this.initialized) {
            await this.init();
        }

        const url = `${this.baseUrl}${endpoint}`;
        const config = {
            headers: {
                'Content-Type': 'application/json',
            },
            ...options,
        };

        if (config.body && typeof config.body === 'object') {
            config.body = JSON.stringify(config.body);
        }

        try {
            const response = await fetch(url, config);
            const data = await response.json();
            return data;
        } catch (error) {
            console.error(`[API] 请求失败: ${endpoint}`, error);
            throw error;
        }
    }

    // ═══════════════════════════════════════════════════════════════════════
    //                           状态 API
    // ═══════════════════════════════════════════════════════════════════════

    /**
     * 获取机器人状态
     */
    async getStatus() {
        return this.request('/api/status');
    }

    /**
     * 启动机器人
     */
    async startBot() {
        return this.request('/api/start', { method: 'POST' });
    }

    /**
     * 停止机器人
     */
    async stopBot() {
        return this.request('/api/stop', { method: 'POST' });
    }

    /**
     * 重启机器人
     */
    async restartBot() {
        return this.request('/api/restart', { method: 'POST' });
    }

    /**
     * 暂停机器人
     */
    async pauseBot(reason = '用户暂停') {
        return this.request('/api/pause', {
            method: 'POST',
            body: { reason }
        });
    }

    /**
     * 恢复机器人
     */
    async resumeBot() {
        return this.request('/api/resume', { method: 'POST' });
    }

    // ═══════════════════════════════════════════════════════════════════════
    //                           消息 API
    // ═══════════════════════════════════════════════════════════════════════

    /**
     * 获取消息列表
     */
    async getMessages() {
        return this.request('/api/messages');
    }

    /**
     * 发送消息
     */
    async sendMessage(target, content) {
        return this.request('/api/send', {
            method: 'POST',
            body: { target, content }
        });
    }

    // ═══════════════════════════════════════════════════════════════════════
    //                           配置 API
    // ═══════════════════════════════════════════════════════════════════════

    /**
     * 获取配置
     */
    async getConfig() {
        return this.request('/api/config');
    }

    /**
     * 保存配置
     */
    async saveConfig(config) {
        return this.request('/api/config', {
            method: 'POST',
            body: config
        });
    }

    // ═══════════════════════════════════════════════════════════════════════
    //                           日志 API
    // ═══════════════════════════════════════════════════════════════════════

    /**
     * 获取日志
     */
    async getLogs(lines = 200) {
        return this.request(`/api/logs?lines=${lines}`);
    }

    /**
     * 清空日志
     */
    async clearLogs() {
        return this.request('/api/logs', { method: 'DELETE' });
    }

    // ═══════════════════════════════════════════════════════════════════════
    //                           使用统计 API
    // ═══════════════════════════════════════════════════════════════════════

    /**
     * 获取使用统计
     */
    async getUsage() {
        return this.request('/api/usage');
    }
}

// 创建全局 API 实例
window.api = new API();
