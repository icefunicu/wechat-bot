/**
 * 设置页面控制器
 */

import { PageController } from '../core/PageController.js';
import { apiService } from '../services/ApiService.js';
import { toast } from '../services/NotificationService.js';

export class SettingsPage extends PageController {
    constructor() {
        super('SettingsPage', 'page-settings');
        this.currentConfig = null;
    }

    async onInit() {
        await super.onInit();
        this._bindEvents();
    }

    async onEnter() {
        await super.onEnter();
        await this._loadConfig();
    }

    // ═══════════════════════════════════════════════════════════════════════
    //                           事件绑定
    // ═══════════════════════════════════════════════════════════════════════

    _bindEvents() {
        // 刷新配置
        this.bindEvent('#btn-refresh-config', 'click', () => this._loadConfig());

        // 保存配置
        this.bindEvent('#btn-save-settings', 'click', () => this._saveConfig());

        // 新增预设
        this.bindEvent('#btn-add-preset', 'click', () => this._openPresetModal());

        // 模态框事件
        this.bindEvent('#btn-close-modal', 'click', () => this._closePresetModal());
        this.bindEvent('#btn-cancel-modal', 'click', () => this._closePresetModal());
        this.bindEvent('#btn-save-modal', 'click', () => this._savePreset());

        this.bindEvent('#btn-reset-close-behavior', 'click', async () => {
            if (!window.electronAPI?.resetCloseBehavior) {
                toast.error('当前环境不支持重置');
                return;
            }
            const result = await window.electronAPI.resetCloseBehavior();
            if (result?.success) {
                toast.success('已重置关闭选择');
            } else {
                toast.error('重置失败');
            }
        });
        
        // 模态框内模型选择变化
        this.bindEvent('#edit-preset-model-select', 'change', (e) => {
            const customInput = this.$('#edit-preset-model-custom');
            if (e.target.value === 'custom') {
                customInput.style.display = 'block';
            } else {
                customInput.style.display = 'none';
            }
            this._updateApiKeyHelp(this._getProviderNameForHelp());
        });

        // 防止标题栏拖拽事件冒泡导致错误
        this.bindEvent('.modal-header', 'mousedown', (e) => {
            e.stopPropagation();
        });

        // 切换 Key 显示
        this.bindEvent('#btn-toggle-key', 'click', () => {
            const input = this.$('#edit-preset-key');
            if (input.type === 'password') {
                input.type = 'text';
            } else {
                input.type = 'password';
            }
        });

        this.bindEvent('#edit-preset-name', 'input', () => {
            this._updateApiKeyHelp(this._getProviderNameForHelp());
        });
    }

    // ═══════════════════════════════════════════════════════════════════════
    //                           辅助数据
    // ═══════════════════════════════════════════════════════════════════════

    _getProviderModels() {
        return {
            'OpenAI': ['gpt-3.5-turbo', 'gpt-4', 'gpt-4-turbo', 'gpt-4o', 'gpt-4o-mini'],
            'Doubao (豆包)': ['doubao-seed-1-8-251228', 'doubao-pro-4k', 'doubao-pro-32k', 'doubao-lite-4k', 'doubao-lite-32k'],
            'DeepSeek': ['deepseek-chat', 'deepseek-coder'],
            'SiliconFlow': ['deepseek-ai/DeepSeek-V3', 'deepseek-ai/DeepSeek-R1', 'deepseek-ai/DeepSeek-V2.5'],
            'Moonshot (Kimi)': ['moonshot-v1-8k', 'moonshot-v1-32k', 'moonshot-v1-128k'],
            'Zhipu (智谱)': ['glm-4', 'glm-4-air', 'glm-4-flash', 'glm-3-turbo'],
            'Qwen (通义千问)': ['qwen-turbo', 'qwen-plus', 'qwen-max'],
            'Groq': ['llama3-70b-8192', 'mixtral-8x7b-32768'],
            'Ollama': ['llama3', 'mistral', 'qwen'],
            'Other': []
        };
    }

    _getProviderIcon(name) {
        const lower = name.toLowerCase();
        if (lower.includes('openai') || lower.includes('gpt')) return '🟢';
        if (lower.includes('doubao') || lower.includes('豆包')) return '📦';
        if (lower.includes('deepseek')) return '🦈';
        if (lower.includes('moonshot') || lower.includes('kimi')) return '🌙';
        if (lower.includes('zhipu') || lower.includes('glm')) return '🧠';
        if (lower.includes('qwen') || lower.includes('通义')) return '😺';
        if (lower.includes('silicon')) return '🌊';
        if (lower.includes('groq')) return '⚡';
        return '🤖';
    }

    _getProviderNameForHelp() {
        const select = this.$('#edit-preset-model-select');
        const nameInput = this.$('#edit-preset-name');
        const option = select?.options?.[select.selectedIndex];
        const optgroup = option?.closest('optgroup');
        if (optgroup?.label) return optgroup.label;
        if (nameInput?.value) return nameInput.value;
        if (option?.value) return option.value;
        return 'Other';
    }

    _getProviderKeyInfo(name) {
        const lower = (name || '').toLowerCase();
        if (lower.includes('openai') || lower.includes('gpt')) {
            return { text: '获取 OpenAI API Key →', url: 'https://platform.openai.com/api-keys' };
        }
        if (lower.includes('doubao') || lower.includes('豆包') || lower.includes('volc') || lower.includes('ark')) {
            return { text: '获取 豆包 API Key →', url: 'https://console.volcengine.com/ark' };
        }
        if (lower.includes('deepseek')) {
            return { text: '获取 DeepSeek API Key →', url: 'https://platform.deepseek.com/api_keys' };
        }
        if (lower.includes('silicon')) {
            return { text: '获取 SiliconFlow API Key →', url: 'https://cloud.siliconflow.cn/account/ak' };
        }
        if (lower.includes('moonshot') || lower.includes('kimi')) {
            return { text: '获取 Moonshot API Key →', url: 'https://platform.moonshot.cn/console/api-keys' };
        }
        if (lower.includes('zhipu') || lower.includes('glm') || lower.includes('智谱')) {
            return { text: '获取 智谱 API Key →', url: 'https://open.bigmodel.cn/usercenter/apikeys' };
        }
        if (lower.includes('qwen') || lower.includes('通义')) {
            return { text: '获取 通义千问 API Key →', url: 'https://dashscope.console.aliyun.com/apiKey' };
        }
        if (lower.includes('groq')) {
            return { text: '获取 Groq API Key →', url: 'https://console.groq.com/keys' };
        }
        if (lower.includes('ollama')) {
            return { text: 'Ollama 无需 API Key，查看文档 →', url: 'https://ollama.com/' };
        }
        return { text: '获取 API Key →', url: 'https://www.google.com/search?q=API+Key+%E8%8E%B7%E5%8F%96' };
    }

    _updateApiKeyHelp(name) {
        const help = this.$('#api-key-help');
        const link = this.$('#api-key-help-link');
        if (!help || !link) return;
        const info = this._getProviderKeyInfo(name);
        link.textContent = info.text;
        link.href = info.url;
        help.style.display = 'block';
    }

    // ═══════════════════════════════════════════════════════════════════════
    //                           配置加载与保存
    // ═══════════════════════════════════════════════════════════════════════

    async _loadConfig() {
        try {
            const result = await apiService.getConfig();
            if (result.success) {
                // 后端返回的是扁平结构，剔除 success 字段后即为配置
                const { success, ...config } = result;
                this.currentConfig = config;
                this._renderConfig(this.currentConfig);
                toast.success('配置已加载');
            } else {
                this.$('#preset-list').innerHTML = `<div class="empty-state error">加载失败: ${result.message}</div>`;
                toast.error('加载配置失败: ' + result.message);
            }
        } catch (error) {
            console.error('加载配置异常:', error);
            this.$('#preset-list').innerHTML = '<div class="empty-state error">加载异常，请检查服务</div>';
            toast.error('加载配置异常');
        }
    }

    _renderConfig(config) {
        if (!config) return;

        // 渲染概览信息 - 优化版
        const api = config.api || {};
        const activePresetName = api.active_preset || '未设置';
        
        // 查找当前预设的完整信息以获取更多详情
        const presets = api.presets || [];
        const currentPreset = presets.find(p => p.name === activePresetName) || {};
        
        // 优先使用预设中的信息，回退到全局
        const activeModel = currentPreset.model || api.model || '--';
        const activeAlias = currentPreset.alias || api.alias || '--';
        const hasKey = currentPreset.api_key_configured;

        const icon = this._getProviderIcon(activePresetName);

        // 更新顶部英雄卡片
        const heroContainer = this.$('#current-config-hero');
        if (heroContainer) {
             heroContainer.innerHTML = `
                <div class="config-hero-card">
                    <div class="hero-icon">${icon}</div>
                    <div class="hero-content">
                        <div class="hero-title">
                            <span class="hero-name">${activePresetName}</span>
                            <span class="status-badge active">
                                <span class="status-dot"></span>已激活
                            </span>
                        </div>
                        <div class="hero-details">
                            <div class="detail-item">
                                <span class="detail-label">模型</span>
                                <span class="detail-value">${activeModel}</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label">别名</span>
                                <span class="detail-value">${activeAlias}</span>
                            </div>
                             <div class="detail-item">
                                <span class="detail-label">API Key</span>
                                <span class="detail-value mono">${hasKey ? '已配置' : '未配置'}</span>
                            </div>
                        </div>
                    </div>
                    <div class="hero-actions">
                        <button class="btn btn-sm btn-secondary" id="btn-ping-test">
                            <svg class="icon" viewBox="0 0 24 24"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>
                            测试连接
                        </button>
                        <div class="ping-result" id="ping-result">未测试</div>
                    </div>
                </div>
             `;
             
             // 绑定测试按钮
             const btnPing = heroContainer.querySelector('#btn-ping-test');
             const pingResult = heroContainer.querySelector('#ping-result');
             if (pingResult) {
                 pingResult.textContent = '未测试';
                 pingResult.className = 'ping-result';
             }
             if(btnPing) {
                 btnPing.onclick = async () => {
                     const btn = btnPing;
                     const originalText = btn.innerHTML;
                     btn.disabled = true;
                     btn.innerHTML = '<span class="spinner-sm"></span> 测试中...'; // 假设有 spinner 样式，或者用文字
                     if (pingResult) {
                         pingResult.textContent = '测试中...';
                         pingResult.className = 'ping-result pending';
                     }
                     
                     try {
                         const res = await apiService.testConnection(activePresetName);
                         if (res.success) {
                             toast.success('连接成功！API 配置有效。');
                             if (pingResult) {
                                 pingResult.textContent = '连接成功';
                                 pingResult.className = 'ping-result success';
                             }
                         } else {
                             toast.error(res.message || '连接测试失败');
                             if (pingResult) {
                                 pingResult.textContent = res.message || '连接失败';
                                 pingResult.className = 'ping-result error';
                             }
                         }
                     } catch (e) {
                         console.error(e);
                         toast.error('连接测试异常');
                         if (pingResult) {
                             pingResult.textContent = '连接异常';
                             pingResult.className = 'ping-result error';
                         }
                     } finally {
                         btn.disabled = false;
                         btn.innerHTML = originalText;
                     }
                 };
             }
        } else {
            // 回退到旧的 DOM 结构
            if(this.$('#info-active-preset')) this.$('#info-active-preset').textContent = activePresetName;
            if(this.$('#info-model')) this.$('#info-model').textContent = activeModel;
            if(this.$('#info-alias')) this.$('#info-alias').textContent = activeAlias;
            if(this.$('#info-api-key')) this.$('#info-api-key').textContent = hasKey ? '已配置' : '未配置';
        }

        // 渲染机器人设置
        const bot = config.bot || {};
        this.$('#setting-self-name').value = bot.self_name || '';
        this.$('#setting-reply-suffix').value = bot.reply_suffix || '';
        if(this.$('#setting-stream-reply')) this.$('#setting-stream-reply').checked = !!bot.stream_reply;
        this.$('#setting-group-at-only').checked = !!bot.group_reply_only_when_at;
        this.$('#setting-whitelist-enabled').checked = !!bot.whitelist_enabled;
        this.$('#setting-whitelist').value = (bot.whitelist || []).join('\n');

        // 渲染预设列表
        this._renderPresetList(api.presets || {});
    }

    async _saveConfig() {
        if (!this.currentConfig) return;

        try {
            // 收集表单数据
            const botSettings = {
                self_name: this.$('#setting-self-name').value,
                reply_suffix: this.$('#setting-reply-suffix').value,
                group_reply_only_when_at: this.$('#setting-group-at-only').checked,
                whitelist_enabled: this.$('#setting-whitelist-enabled').checked,
                whitelist: this.$('#setting-whitelist').value.split('\n').map(s => s.trim()).filter(s => s)
            };

            // 合并到当前配置
            const newConfig = {
                ...this.currentConfig,
                bot: {
                    ...this.currentConfig.bot,
                    ...botSettings
                }
            };

            const result = await apiService.saveConfig(newConfig);
            if (result.success) {
                this.currentConfig = result.config; // 更新本地配置
                this._renderConfig(this.currentConfig);
                toast.success('配置已保存');
            } else {
                toast.error('保存失败: ' + result.message);
            }
        } catch (error) {
            console.error('保存配置异常:', error);
            toast.error('保存配置异常');
        }
    }

    // ═══════════════════════════════════════════════════════════════════════
    //                           预设管理
    // ═══════════════════════════════════════════════════════════════════════

    _renderPresetList(presets) {
        const list = this.$('#preset-list');
        list.innerHTML = '';

        // 确保 presets 是数组
        const presetList = Array.isArray(presets) ? presets : [];

        if (presetList.length === 0) {
            list.innerHTML = '<div class="empty-state">暂无预设</div>';
            return;
        }

        presetList.forEach(preset => {
            const name = preset.name;
            const isActive = name === this.currentConfig.api?.active_preset;
            const icon = this._getProviderIcon(name);

            const item = document.createElement('div');
            // 使用 CSS 类控制样式
            item.className = `preset-card ${isActive ? 'active' : ''}`;
            
            item.innerHTML = `
                <div class="preset-card-header">
                    <div class="preset-icon">${icon}</div>
                    <div class="preset-info">
                        <div class="preset-name">
                            ${name}
                            ${isActive ? '<span class="tag tag-active">当前使用</span>' : ''}
                            ${preset.api_key_configured ? 
                                '<span class="tag" style="background: rgba(16, 185, 129, 0.2); color: #10b981; margin-left: 6px; font-size: 0.75em; padding: 2px 6px;">已配 Key</span>' : 
                                '<span class="tag" style="background: rgba(245, 158, 11, 0.2); color: #f59e0b; margin-left: 6px; font-size: 0.75em; padding: 2px 6px;">无 Key</span>'}
                        </div>
                        <div class="preset-meta">
                            <span class="meta-item model-name" title="${preset.model}">${preset.model}</span>
                            ${preset.alias ? `<span class="meta-separator">·</span><span class="meta-item">${preset.alias}</span>` : ''}
                        </div>
                    </div>
                </div>
                <div class="preset-card-actions">
                    ${!isActive ? `<button class="btn-icon btn-ghost btn-activate" title="启用"><svg class="icon" viewBox="0 0 24 24"><path d="M5 3l14 9-14 9V3z"/></svg></button>` : ''}
                    <button class="btn-icon btn-ghost btn-edit" title="编辑"><svg class="icon" viewBox="0 0 24 24"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg></button>
                    <button class="btn-icon btn-ghost btn-delete" title="删除"><svg class="icon" viewBox="0 0 24 24"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg></button>
                </div>
            `;

            // 绑定列表项按钮事件
            item.querySelector('.btn-edit').onclick = () => this._openPresetModal(name, preset);
            item.querySelector('.btn-delete').onclick = () => this._deletePreset(name);
            if (!isActive) {
                const btnActivate = item.querySelector('.btn-activate');
                if (btnActivate) {
                    btnActivate.onclick = async () => {
                        // 防止重复点击
                        if (btnActivate.disabled) return;
                        
                        const originalHtml = btnActivate.innerHTML;
                        try {
                            btnActivate.disabled = true;
                            // 显示简易 Loading
                            btnActivate.innerHTML = '<span class="spinner-sm" style="width:14px;height:14px;border-width:2px;"></span>';
                            await this._activatePreset(name);
                        } catch (e) {
                            console.error('激活预设失败:', e);
                            toast.error('激活预设异常');
                            // 恢复按钮状态
                            btnActivate.disabled = false;
                            btnActivate.innerHTML = originalHtml;
                        }
                    };
                }
            }

            list.appendChild(item);
        });
    }

    _openPresetModal(name = null, preset = null) {
        const modal = this.$('#preset-modal');
        const isEdit = !!name;
        
        this.$('.modal-title').textContent = isEdit ? '编辑预设' : '新增预设';
        this.$('#edit-preset-original-name').value = name || '';
        this.$('#edit-preset-name').value = name || '';
        this.$('#edit-preset-name').disabled = isEdit; // 编辑时不允许改名(ID)

        // 填充模型下拉 - 智能联动
        const select = this.$('#edit-preset-model-select');
        const modelsMap = this._getProviderModels();
        let optionsHtml = '';
        
        // 确定要显示的模型组
        let targetProviderKey = null;
        if (name) {
            // 尝试模糊匹配 name 到 provider key
            const lowerName = name.toLowerCase();
            targetProviderKey = Object.keys(modelsMap).find(key => {
                const lowerKey = key.toLowerCase();
                // 处理 "Doubao (豆包)" 这种情况
                const cleanKey = lowerKey.split(' ')[0]; 
                return lowerName.includes(cleanKey) || cleanKey.includes(lowerName);
            });
        }

        // 如果找到了对应的 Provider，只显示该组
        if (targetProviderKey && modelsMap[targetProviderKey]) {
            const models = modelsMap[targetProviderKey];
            optionsHtml += `<optgroup label="${targetProviderKey}">`;
            models.forEach(m => {
                optionsHtml += `<option value="${m}">${m}</option>`;
            });
            optionsHtml += `</optgroup>`;
        } else {
            // 如果没找到（或者是新增模式且未输入），显示所有分组
            // 或者我们可以根据用户输入的 name 动态过滤？目前简化为显示所有
            for (const [provider, models] of Object.entries(modelsMap)) {
                if (models.length > 0) {
                    optionsHtml += `<optgroup label="${provider}">`;
                    models.forEach(m => {
                        optionsHtml += `<option value="${m}">${m}</option>`;
                    });
                    optionsHtml += `</optgroup>`;
                }
            }
        }

        // 始终添加自定义选项
        optionsHtml += `<option value="custom">自定义模型...</option>`;
        select.innerHTML = optionsHtml;

        if (preset) {
            this.$('#edit-preset-alias').value = preset.alias || '';
            this.$('#edit-preset-key').value = ''; // 不回显 Key
            
            const currentModel = preset.model;
            // 检查模型是否存在于列表中
            let found = false;
            for (const models of Object.values(modelsMap)) {
                if (models.includes(currentModel)) {
                    found = true;
                    break;
                }
            }
            
            if (found) {
                select.value = currentModel;
                this.$('#edit-preset-model-custom').style.display = 'none';
            } else {
                select.value = 'custom';
                this.$('#edit-preset-model-custom').style.display = 'block';
                this.$('#edit-preset-model-custom').value = currentModel;
            }
        } else {
            this.$('#edit-preset-alias').value = '';
            this.$('#edit-preset-key').value = '';
            // 默认选中第一个
            select.value = modelsMap['OpenAI'][0] || 'custom';
            this.$('#edit-preset-model-custom').style.display = 'none';
        }

        this._updateApiKeyHelp(this._getProviderNameForHelp());
        modal.classList.add('active');
    }

    _closePresetModal() {
        this.$('#preset-modal').classList.remove('active');
    }

    async _savePreset() {
        const originalName = this.$('#edit-preset-original-name').value;
        const name = this.$('#edit-preset-name').value.trim();
        const alias = this.$('#edit-preset-alias').value.trim();
        const key = this.$('#edit-preset-key').value.trim();
        
        const select = this.$('#edit-preset-model-select');
        let model = select.value;
        if (model === 'custom') {
            model = this.$('#edit-preset-model-custom').value.trim();
        }

        if (!name || !model) {
            toast.error('名称和模型不能为空');
            return;
        }

        // 构建新的预设对象
        const newPreset = {
            name,
            model,
            alias,
            // 如果提供了 key 则更新，否则保留(后端处理逻辑需支持)
            ...(key ? { api_key: key } : {}) 
        };
        
        // 获取当前预设列表
        let presets = [...(this.currentConfig.api.presets || [])];
        if (!Array.isArray(presets)) presets = [];

        // 查找原始预设
        const existingIndex = originalName 
            ? presets.findIndex(p => p.name === originalName)
            : -1;

        // 如果是编辑且没填key，需要保留原来的key
        if (existingIndex !== -1 && !key) {
            const existing = presets[existingIndex];
            // 注意：这里可能拿到的是 masked key，如果没填 key 且原 key 存在，应该保留原 key
            // 但如果原 key 是 masked (****)，发回给后端会被当成新 key 吗？
            // 后端逻辑：如果 key 是 ****，需要后端识别并保留？
            // 通常后端 config.py 不会存 masked key。后端返回给前端的是 masked。
            // 如果前端把 masked key 发回去，后端存下来就废了。
            // 解决办法：如果 key 没变（没填），我们在前端不发 api_key 字段？
            // 或者：newPreset 不包含 api_key 字段。
            // 下面的逻辑：...(key ? { api_key: key } : {})
            // 如果 key 为空，newPreset 没有 api_key 字段。
            // 那么后端更新时，如果不传 api_key，是会删除 api_key 还是保留？
            // 看后端 save_config 逻辑：它是直接替换整个 presets 列表。
            // 如果我们发回去的 preset 没有 api_key，后端存下来的就没有 api_key。
            // 所以我们必须把原来的 api_key 找回来？
            // 但前端拿到的 config 里只有 masked key。
            // 这是一个经典问题。
            // 通常做法：前端不发 api_key，后端合并时检查：如果新 preset 没有 api_key，则去旧配置里找同名 preset 的 api_key 填回去。
            // 后端 save_config 目前没有这个合并逻辑，它直接用 settings['presets'] 覆盖。
            // 这是一个后端 BUG。
            
            // 既然不能改后端，那前端能做什么？
            // 前端没法拿到原始 Key。
            // 等等，后端 api.py 里：
            // p['api_key_configured'] = True/False
            // p['api_key_masked'] = 'sk-****'
            // 原来的 'api_key' 被删了。
            
            // 所以，如果用户不改 Key，前端发回去的 preset 里没有 api_key 字段。
            // 后端直接保存，导致 Key 丢失。
            
            // 必须修后端。如果不修后端，用户只要编辑预设，Key 就丢了。
            // 除非用户每次都重新输入 Key。
            
            // 用户说“代码生成时默认添加注释”，且允许重构。
            // 我必须修复这个问题。
            // 方案：修改后端 save_config，在保存前合并旧 Key。
        }
        
        // 暂时先按原逻辑写，然后去修后端。
        // 原逻辑试图保留 Key：
        // if (originalName && !key && this.currentConfig.api.presets[originalName]) {
        //    newPreset.api_key = this.currentConfig.api.presets[originalName].api_key;
        // }
        // 但 this.currentConfig...api_key 是 undefined (被后端删了)。
        // 所以原逻辑也是坏的。

        // 既然如此，我先把前端改成 Array 结构，然后去修后端。
        
        // 更新列表
        if (existingIndex !== -1) {
            // 保留可能的其他字段（如果有）
            // newPreset = { ...presets[existingIndex], ...newPreset }; // 不，我们想要完全替换，除了 Key
            
            // 标记一下，让后端知道“我没改 Key”
            if (!key) {
                newPreset._keep_key = true; // 这是一个约定，需要后端支持
            }
            presets[existingIndex] = newPreset;
        } else {
            if (presets.some(p => p.name === name)) {
                toast.error('预设名称已存在');
                return;
            }
            presets.push(newPreset);
        }

        const newConfig = {
            ...this.currentConfig,
            api: {
                ...this.currentConfig.api,
                presets
            }
        };

        const result = await apiService.saveConfig(newConfig);
        if (result.success) {
            this.currentConfig = result.config;
            this._renderConfig(this.currentConfig);
            this._closePresetModal();
            toast.success('预设已保存');
        } else {
            toast.error('保存失败: ' + result.message);
        }
    }

    async _deletePreset(name) {
        if (!confirm(`确定要删除预设 "${name}" 吗？`)) return;

        let presets = [...(this.currentConfig.api.presets || [])];
        if (!Array.isArray(presets)) presets = [];
        
        presets = presets.filter(p => p.name !== name);

        const newConfig = {
            ...this.currentConfig,
            api: {
                ...this.currentConfig.api,
                presets
            }
        };

        const result = await apiService.saveConfig(newConfig);
        if (result.success) {
            this.currentConfig = result.config;
            this._renderConfig(this.currentConfig);
            toast.success('预设已删除');
        } else {
            toast.error('删除失败: ' + result.message);
        }
    }

    async _activatePreset(name) {
        try {
            const newConfig = {
                ...this.currentConfig,
                api: {
                    ...this.currentConfig.api,
                    active_preset: name
                }
            };

            const result = await apiService.saveConfig(newConfig);
            if (result.success) {
                // 1. 使用后端返回的最新配置更新本地状态
                this.currentConfig = result.config;
                
                // 2. 重新渲染界面
                this._renderConfig(this.currentConfig);
                
                // 3. 触发高亮特效
                const heroCard = this.$('.config-hero-card');
                if (heroCard) {
                    heroCard.classList.remove('highlight-pulse');
                    // 强制重绘以重置动画
                    void heroCard.offsetWidth;
                    heroCard.classList.add('highlight-pulse');
                    
                    // 动画结束后移除类(可选，但保持清洁更好)
                    setTimeout(() => {
                        heroCard.classList.remove('highlight-pulse');
                    }, 1500);
                }

                toast.success(`已切换到预设: ${name}`);
            } else {
                toast.error('切换失败: ' + result.message);
                throw new Error(result.message); // 抛出异常以便外层捕获恢复按钮状态
            }
        } catch (error) {
            console.error('切换预设异常:', error);
            // 如果是主动抛出的错误，可能已经 toast 过了，但这里统一处理也没事
            if (!error.message || !error.message.includes('切换失败')) {
                toast.error('切换预设操作发生错误');
            }
            throw error; // 继续抛出，让按钮点击事件捕获
        }
    }
}
