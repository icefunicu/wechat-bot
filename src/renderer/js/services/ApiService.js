/**
 * API 服务
 * 
 * 封装所有与 Flask 后端的通信
 */

class ApiService {
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
        console.log('[ApiService] 初始化完成，baseUrl:', this.baseUrl);
    }

    /**
     * 发起 HTTP 请求
     * @param {string} endpoint - API 端点
     * @param {Object} options - 请求选项
     * @param {number} retries - 重试次数
     */
    async request(endpoint, options = {}, retries = 1) {
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

        let lastError = null;
        for (let attempt = 0; attempt <= retries; attempt++) {
            try {
                const response = await fetch(url, config);
                const data = await response.json();
                return data;
            } catch (error) {
                console.error(`[ApiService] 请求失败 (尝试 ${attempt + 1}/${retries + 1}): ${endpoint}`, error);
                lastError = error;
                if (attempt < retries) {
                    // 等待一段时间后重试
                    await new Promise(resolve => setTimeout(resolve, 1000));
                }
            }
        }

        throw lastError;
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
     * @param {string} reason - 暂停原因
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
     * @param {string} target - 目标
     * @param {string} content - 内容
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
     * @param {Object} config - 配置对象
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
     * @param {number} lines - 行数
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

// 导出单例
export const apiService = new ApiService();
export default apiService;
