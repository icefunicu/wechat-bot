/**
 * 状态管理器
 * 
 * 提供统一的状态管理，支持订阅式更新
 */

class StateManager {
    constructor() {
        // 应用状态
        this._state = {
            // 机器人状态
            bot: {
                running: false,
                paused: false,
                connected: false
            },
            // 当前页面
            currentPage: 'dashboard',
            // 日志设置
            logs: {
                autoScroll: true
            },
            // 刷新定时器
            intervals: {
                status: null,
                logs: null
            }
        };

        // 订阅者映射
        this._subscribers = new Map();

        // 状态变更历史（调试用）
        this._history = [];
    }

    /**
     * 获取完整状态
     */
    getState() {
        return { ...this._state };
    }

    /**
     * 获取状态切片
     * @param {string} path - 状态路径，如 'bot.running'
     */
    get(path) {
        const keys = path.split('.');
        let value = this._state;
        for (const key of keys) {
            if (value === undefined) return undefined;
            value = value[key];
        }
        return value;
    }

    /**
     * 设置状态
     * @param {string} path - 状态路径
     * @param {*} value - 新值
     */
    set(path, value) {
        const keys = path.split('.');
        const lastKey = keys.pop();
        let target = this._state;

        for (const key of keys) {
            if (target[key] === undefined) {
                target[key] = {};
            }
            target = target[key];
        }

        const oldValue = target[lastKey];
        target[lastKey] = value;

        // 记录历史
        this._history.push({
            path,
            oldValue,
            newValue: value,
            timestamp: Date.now()
        });

        // 保持历史记录在合理范围
        if (this._history.length > 100) {
            this._history.shift();
        }

        // 通知订阅者
        this._notifySubscribers(path, value, oldValue);

        console.log(`[StateManager] 状态更新: ${path}`, { oldValue, newValue: value });
    }

    /**
     * 批量更新状态
     * @param {Object} updates - 更新对象，如 { 'bot.running': true, 'bot.paused': false }
     */
    batchUpdate(updates) {
        for (const [path, value] of Object.entries(updates)) {
            this.set(path, value);
        }
    }

    /**
     * 订阅状态变更
     * @param {string} path - 状态路径，支持通配符 '*'
     * @param {Function} callback - 回调函数 (newValue, oldValue, path) => void
     * @returns {Function} 取消订阅函数
     */
    subscribe(path, callback) {
        if (!this._subscribers.has(path)) {
            this._subscribers.set(path, new Set());
        }
        this._subscribers.get(path).add(callback);

        // 返回取消订阅函数
        return () => {
            this._subscribers.get(path)?.delete(callback);
        };
    }

    /**
     * 通知订阅者
     */
    _notifySubscribers(path, newValue, oldValue) {
        // 精确匹配
        if (this._subscribers.has(path)) {
            for (const callback of this._subscribers.get(path)) {
                try {
                    callback(newValue, oldValue, path);
                } catch (error) {
                    console.error('[StateManager] 订阅者回调错误:', error);
                }
            }
        }

        // 通配符匹配
        if (this._subscribers.has('*')) {
            for (const callback of this._subscribers.get('*')) {
                try {
                    callback(newValue, oldValue, path);
                } catch (error) {
                    console.error('[StateManager] 订阅者回调错误:', error);
                }
            }
        }

        // 父路径通配符匹配（如 'bot.*' 匹配 'bot.running'）
        const parts = path.split('.');
        for (let i = 1; i < parts.length; i++) {
            const wildcardPath = parts.slice(0, i).join('.') + '.*';
            if (this._subscribers.has(wildcardPath)) {
                for (const callback of this._subscribers.get(wildcardPath)) {
                    try {
                        callback(newValue, oldValue, path);
                    } catch (error) {
                        console.error('[StateManager] 订阅者回调错误:', error);
                    }
                }
            }
        }
    }

    /**
     * 获取状态变更历史
     */
    getHistory() {
        return [...this._history];
    }

    /**
     * 清空历史
     */
    clearHistory() {
        this._history = [];
    }
}

// 导出单例
export const stateManager = new StateManager();
export default stateManager;
