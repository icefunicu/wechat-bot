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
            'Zhipu (智谱)': ['glm-4v', 'glm-4v-plus', 'glm-4', 'glm-4-air', 'glm-4-flash', 'glm-3-turbo'],
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
            toast.error(toast.getErrorMessage(error, '加载配置异常'));
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
                         toast.error(toast.getErrorMessage(e, '连接测试异常'));
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

        const systemPrompt = this.$('#setting-system-prompt');
        if (systemPrompt) {
            systemPrompt.value = bot.system_prompt || '';
        }
        const overridesInput = this.$('#setting-system-prompt-overrides');
        if (overridesInput) {
            const overrides = bot.system_prompt_overrides || {};
            const lines = Object.entries(overrides).map(([key, value]) => {
                const text = String(value ?? '').replace(/\n/g, '\\n');
                return `${key}|${text}`;
            });
            overridesInput.value = lines.join('\n');
        }

        const emojiPolicy = this.$('#setting-emoji-policy');
        if (emojiPolicy) {
            emojiPolicy.value = bot.emoji_policy || 'mixed';
        }
        const emojiReplacements = this.$('#setting-emoji-replacements');
        if (emojiReplacements) {
            const replacements = bot.emoji_replacements || {};
            const lines = Object.entries(replacements).map(([key, value]) => `${key}=${value}`);
            emojiReplacements.value = lines.join('\n');
        }
        const voiceToText = this.$('#setting-voice-to-text');
        if (voiceToText) {
            voiceToText.checked = bot.voice_to_text !== false;
        }
        const voiceFailReply = this.$('#setting-voice-to-text-fail-reply');
        if (voiceFailReply) {
            voiceFailReply.value = bot.voice_to_text_fail_reply || '';
        }

        const memoryDbPath = this.$('#setting-memory-db-path');
        if (memoryDbPath) {
            memoryDbPath.value = bot.memory_db_path || '';
        }
        const memoryContextLimit = this.$('#setting-memory-context-limit');
        if (memoryContextLimit) {
            memoryContextLimit.value = bot.memory_context_limit ?? 0;
        }
        const memoryTtl = this.$('#setting-memory-ttl-sec');
        if (memoryTtl) {
            memoryTtl.value = bot.memory_ttl_sec ?? '';
        }
        const memoryCleanup = this.$('#setting-memory-cleanup-interval-sec');
        if (memoryCleanup) {
            memoryCleanup.value = bot.memory_cleanup_interval_sec ?? 0;
        }
        const memorySeedFirst = this.$('#setting-memory-seed-on-first-reply');
        if (memorySeedFirst) {
            memorySeedFirst.checked = bot.memory_seed_on_first_reply !== false;
        }
        const memorySeedLimit = this.$('#setting-memory-seed-limit');
        if (memorySeedLimit) {
            memorySeedLimit.value = bot.memory_seed_limit ?? 0;
        }
        const memorySeedLoadMore = this.$('#setting-memory-seed-load-more');
        if (memorySeedLoadMore) {
            memorySeedLoadMore.value = bot.memory_seed_load_more ?? 0;
        }
        const memorySeedLoadMoreInterval = this.$('#setting-memory-seed-load-more-interval-sec');
        if (memorySeedLoadMoreInterval) {
            memorySeedLoadMoreInterval.value = bot.memory_seed_load_more_interval_sec ?? 0;
        }
        const memorySeedGroup = this.$('#setting-memory-seed-group');
        if (memorySeedGroup) {
            memorySeedGroup.checked = !!bot.memory_seed_group;
        }
        const contextRounds = this.$('#setting-context-rounds');
        if (contextRounds) {
            contextRounds.value = bot.context_rounds ?? 0;
        }
        const contextMaxTokens = this.$('#setting-context-max-tokens');
        if (contextMaxTokens) {
            contextMaxTokens.value = bot.context_max_tokens ?? 0;
        }
        const historyMaxChats = this.$('#setting-history-max-chats');
        if (historyMaxChats) {
            historyMaxChats.value = bot.history_max_chats ?? 0;
        }
        const historyTtl = this.$('#setting-history-ttl-sec');
        if (historyTtl) {
            historyTtl.value = bot.history_ttl_sec ?? '';
        }
        const historyLogInterval = this.$('#setting-history-log-interval-sec');
        if (historyLogInterval) {
            historyLogInterval.value = bot.history_log_interval_sec ?? 0;
        }

        const pollInterval = this.$('#setting-poll-interval-sec');
        if (pollInterval) {
            pollInterval.value = bot.poll_interval_sec ?? 0;
        }
        const pollMin = this.$('#setting-poll-interval-min-sec');
        if (pollMin) {
            pollMin.value = bot.poll_interval_min_sec ?? 0;
        }
        const pollMax = this.$('#setting-poll-interval-max-sec');
        if (pollMax) {
            pollMax.value = bot.poll_interval_max_sec ?? 0;
        }
        const pollBackoff = this.$('#setting-poll-interval-backoff-factor');
        if (pollBackoff) {
            pollBackoff.value = bot.poll_interval_backoff_factor ?? 0;
        }
        const minReplyInterval = this.$('#setting-min-reply-interval-sec');
        if (minReplyInterval) {
            minReplyInterval.value = bot.min_reply_interval_sec ?? 0;
        }
        const randomDelayMin = this.$('#setting-random-delay-min-sec');
        const randomDelayMax = this.$('#setting-random-delay-max-sec');
        if (Array.isArray(bot.random_delay_range_sec)) {
            if (randomDelayMin) randomDelayMin.value = bot.random_delay_range_sec[0] ?? 0;
            if (randomDelayMax) randomDelayMax.value = bot.random_delay_range_sec[1] ?? 0;
        } else {
            if (randomDelayMin) randomDelayMin.value = 0;
            if (randomDelayMax) randomDelayMax.value = 0;
        }

        const mergeSec = this.$('#setting-merge-user-messages-sec');
        if (mergeSec) {
            mergeSec.value = bot.merge_user_messages_sec ?? 0;
        }
        const mergeMaxWait = this.$('#setting-merge-user-messages-max-wait-sec');
        if (mergeMaxWait) {
            mergeMaxWait.value = bot.merge_user_messages_max_wait_sec ?? 0;
        }
        const replyChunkSize = this.$('#setting-reply-chunk-size');
        if (replyChunkSize) {
            replyChunkSize.value = bot.reply_chunk_size ?? 0;
        }
        const replyChunkDelay = this.$('#setting-reply-chunk-delay-sec');
        if (replyChunkDelay) {
            replyChunkDelay.value = bot.reply_chunk_delay_sec ?? 0;
        }
        const maxConcurrency = this.$('#setting-max-concurrency');
        if (maxConcurrency) {
            maxConcurrency.value = bot.max_concurrency ?? 0;
        }

        const naturalSplitEnabled = this.$('#setting-natural-split-enabled');
        if (naturalSplitEnabled) {
            naturalSplitEnabled.checked = !!bot.natural_split_enabled;
        }
        const naturalMin = this.$('#setting-natural-split-min-chars');
        if (naturalMin) {
            naturalMin.value = bot.natural_split_min_chars ?? 0;
        }
        const naturalMax = this.$('#setting-natural-split-max-chars');
        if (naturalMax) {
            naturalMax.value = bot.natural_split_max_chars ?? 0;
        }
        const naturalSegments = this.$('#setting-natural-split-max-segments');
        if (naturalSegments) {
            naturalSegments.value = bot.natural_split_max_segments ?? 0;
        }
        const naturalDelayMin = this.$('#setting-natural-split-delay-min-sec');
        const naturalDelayMax = this.$('#setting-natural-split-delay-max-sec');
        if (Array.isArray(bot.natural_split_delay_sec)) {
            if (naturalDelayMin) naturalDelayMin.value = bot.natural_split_delay_sec[0] ?? 0;
            if (naturalDelayMax) naturalDelayMax.value = bot.natural_split_delay_sec[1] ?? 0;
        } else {
            if (naturalDelayMin) naturalDelayMin.value = 0;
            if (naturalDelayMax) naturalDelayMax.value = 0;
        }

        const streamBuffer = this.$('#setting-stream-buffer-chars');
        if (streamBuffer) {
            streamBuffer.value = bot.stream_buffer_chars ?? 0;
        }
        const streamChunkMax = this.$('#setting-stream-chunk-max-chars');
        if (streamChunkMax) {
            streamChunkMax.value = bot.stream_chunk_max_chars ?? 0;
        }

        const configReload = this.$('#setting-config-reload-sec');
        if (configReload) {
            configReload.value = bot.config_reload_sec ?? 0;
        }
        const reloadClient = this.$('#setting-reload-ai-client-on-change');
        if (reloadClient) {
            reloadClient.checked = bot.reload_ai_client_on_change !== false;
        }
        const reloadModule = this.$('#setting-reload-ai-client-module');
        if (reloadModule) {
            reloadModule.checked = !!bot.reload_ai_client_module;
        }
        const keepaliveIdle = this.$('#setting-keepalive-idle-sec');
        if (keepaliveIdle) {
            keepaliveIdle.value = bot.keepalive_idle_sec ?? 0;
        }
        const reconnectRetries = this.$('#setting-reconnect-max-retries');
        if (reconnectRetries) {
            reconnectRetries.value = bot.reconnect_max_retries ?? 0;
        }
        const reconnectBackoff = this.$('#setting-reconnect-backoff-sec');
        if (reconnectBackoff) {
            reconnectBackoff.value = bot.reconnect_backoff_sec ?? 0;
        }
        const reconnectMaxDelay = this.$('#setting-reconnect-max-delay-sec');
        if (reconnectMaxDelay) {
            reconnectMaxDelay.value = bot.reconnect_max_delay_sec ?? 0;
        }

        const groupIncludeSender = this.$('#setting-group-include-sender');
        if (groupIncludeSender) {
            groupIncludeSender.checked = !!bot.group_include_sender;
        }
        const sendExactMatch = this.$('#setting-send-exact-match');
        if (sendExactMatch) {
            sendExactMatch.checked = !!bot.send_exact_match;
        }
        const sendFallback = this.$('#setting-send-fallback-current-chat');
        if (sendFallback) {
            sendFallback.checked = !!bot.send_fallback_current_chat;
        }

        const filterMute = this.$('#setting-filter-mute');
        if (filterMute) {
            filterMute.checked = !!bot.filter_mute;
        }
        const ignoreOfficial = this.$('#setting-ignore-official');
        if (ignoreOfficial) {
            ignoreOfficial.checked = !!bot.ignore_official;
        }
        const ignoreService = this.$('#setting-ignore-service');
        if (ignoreService) {
            ignoreService.checked = !!bot.ignore_service;
        }
        const ignoreNames = this.$('#setting-ignore-names');
        if (ignoreNames) {
            ignoreNames.value = (bot.ignore_names || []).join('\n');
        }
        const ignoreKeywords = this.$('#setting-ignore-keywords');
        if (ignoreKeywords) {
            ignoreKeywords.value = (bot.ignore_keywords || []).join('\n');
        }

        const personalizationEnabled = this.$('#setting-personalization-enabled');
        if (personalizationEnabled) {
            personalizationEnabled.checked = !!bot.personalization_enabled;
        }
        const profileUpdateFrequency = this.$('#setting-profile-update-frequency');
        if (profileUpdateFrequency) {
            profileUpdateFrequency.value = bot.profile_update_frequency ?? 0;
        }
        const rememberFactsEnabled = this.$('#setting-remember-facts-enabled');
        if (rememberFactsEnabled) {
            rememberFactsEnabled.checked = !!bot.remember_facts_enabled;
        }
        const maxContextFacts = this.$('#setting-max-context-facts');
        if (maxContextFacts) {
            maxContextFacts.value = bot.max_context_facts ?? 0;
        }
        const profileInject = this.$('#setting-profile-inject-in-prompt');
        if (profileInject) {
            profileInject.checked = !!bot.profile_inject_in_prompt;
        }

        const controlCommands = this.$('#setting-control-commands-enabled');
        if (controlCommands) {
            controlCommands.checked = !!bot.control_commands_enabled;
        }
        const controlPrefix = this.$('#setting-control-command-prefix');
        if (controlPrefix) {
            controlPrefix.value = bot.control_command_prefix ?? '';
        }
        const controlReplyVisible = this.$('#setting-control-reply-visible');
        if (controlReplyVisible) {
            controlReplyVisible.checked = bot.control_reply_visible !== false;
        }
        const controlAllowedUsers = this.$('#setting-control-allowed-users');
        if (controlAllowedUsers) {
            controlAllowedUsers.value = (bot.control_allowed_users || []).join('\n');
        }

        const quietEnabled = this.$('#setting-quiet-hours-enabled');
        if (quietEnabled) {
            quietEnabled.checked = !!bot.quiet_hours_enabled;
        }
        const quietStart = this.$('#setting-quiet-hours-start');
        if (quietStart) {
            quietStart.value = bot.quiet_hours_start ?? '';
        }
        const quietEnd = this.$('#setting-quiet-hours-end');
        if (quietEnd) {
            quietEnd.value = bot.quiet_hours_end ?? '';
        }
        const quietReply = this.$('#setting-quiet-hours-reply');
        if (quietReply) {
            quietReply.value = bot.quiet_hours_reply ?? '';
        }

        const usageTracking = this.$('#setting-usage-tracking-enabled');
        if (usageTracking) {
            usageTracking.checked = !!bot.usage_tracking_enabled;
        }
        const dailyTokenLimit = this.$('#setting-daily-token-limit');
        if (dailyTokenLimit) {
            dailyTokenLimit.value = bot.daily_token_limit ?? 0;
        }
        const tokenWarning = this.$('#setting-token-warning-threshold');
        if (tokenWarning) {
            tokenWarning.value = bot.token_warning_threshold ?? 0;
        }

        const emotionEnabled = this.$('#setting-emotion-detection-enabled');
        if (emotionEnabled) {
            emotionEnabled.checked = !!bot.emotion_detection_enabled;
        }
        const emotionMode = this.$('#setting-emotion-detection-mode');
        if (emotionMode) {
            emotionMode.value = bot.emotion_detection_mode || 'keywords';
        }
        const emotionInject = this.$('#setting-emotion-inject-in-prompt');
        if (emotionInject) {
            emotionInject.checked = !!bot.emotion_inject_in_prompt;
        }
        const emotionLog = this.$('#setting-emotion-log-enabled');
        if (emotionLog) {
            emotionLog.checked = !!bot.emotion_log_enabled;
        }

        const loggingCfg = config.logging || {};
        const logLevel = this.$('#setting-log-level');
        if (logLevel) {
            logLevel.value = loggingCfg.level || 'INFO';
        }
        const logFormat = this.$('#setting-log-format');
        if (logFormat) {
            logFormat.value = loggingCfg.format || 'text';
        }
        const logFile = this.$('#setting-log-file');
        if (logFile) {
            logFile.value = loggingCfg.file || '';
        }
        const logMaxBytes = this.$('#setting-log-max-bytes');
        if (logMaxBytes) {
            logMaxBytes.value = loggingCfg.max_bytes ?? 0;
        }
        const logBackup = this.$('#setting-log-backup-count');
        if (logBackup) {
            logBackup.value = loggingCfg.backup_count ?? 0;
        }
        const logMessageContent = this.$('#setting-log-message-content');
        if (logMessageContent) {
            logMessageContent.checked = !!loggingCfg.log_message_content;
        }
        const logReplyContent = this.$('#setting-log-reply-content');
        if (logReplyContent) {
            logReplyContent.checked = !!loggingCfg.log_reply_content;
        }

        const quoteMode = this.$('#setting-reply-quote-mode');
        if (quoteMode) {
            quoteMode.value = bot.reply_quote_mode || 'wechat';
        }
        const quoteTemplate = this.$('#setting-reply-quote-template');
        if (quoteTemplate) {
            quoteTemplate.value = bot.reply_quote_template || '引用：{content}\n';
        }
        const quoteMaxChars = this.$('#setting-reply-quote-max-chars');
        if (quoteMaxChars) {
            const maxChars = bot.reply_quote_max_chars ?? 120;
            quoteMaxChars.value = Number.isFinite(maxChars) ? String(maxChars) : '120';
        }
        const quoteTimeout = this.$('#setting-reply-quote-timeout');
        if (quoteTimeout) {
            const timeoutSec = bot.reply_quote_timeout_sec ?? 5.0;
            quoteTimeout.value = Number.isFinite(timeoutSec) ? String(timeoutSec) : '5';
        }
        const quoteFallback = this.$('#setting-reply-quote-fallback');
        if (quoteFallback) {
            quoteFallback.checked = bot.reply_quote_fallback_to_text !== false;
        }

        // 渲染预设列表
        this._renderPresetList(api.presets || {});
    }

    async _saveConfig() {
        if (!this.currentConfig) return;

        try {
            // 收集表单数据
            const parseNumber = (value) => {
                if (value === '' || value == null) return undefined;
                const num = Number(value);
                return Number.isNaN(num) ? undefined : num;
            };
            const parseNumberOrNull = (value) => {
                if (value === '' || value == null) return null;
                const num = Number(value);
                return Number.isNaN(num) ? null : num;
            };
            const parseLines = (value) => value.split('\n').map(s => s.trim()).filter(s => s);
            const parseRange = (minVal, maxVal) => {
                if (minVal == null || maxVal == null) return undefined;
                const minNum = Number(minVal);
                const maxNum = Number(maxVal);
                if (Number.isNaN(minNum) || Number.isNaN(maxNum)) return undefined;
                return [minNum, maxNum];
            };

            const quoteMaxCharsRaw = this.$('#setting-reply-quote-max-chars')?.value;
            const quoteTimeoutRaw = this.$('#setting-reply-quote-timeout')?.value;
            const quoteMaxChars = quoteMaxCharsRaw === '' || quoteMaxCharsRaw == null ? undefined : Number(quoteMaxCharsRaw);
            const quoteTimeoutSec = quoteTimeoutRaw === '' || quoteTimeoutRaw == null ? undefined : Number(quoteTimeoutRaw);

            const overridesInput = this.$('#setting-system-prompt-overrides')?.value || '';
            const overridesLines = parseLines(overridesInput);
            const overrides = {};
            overridesLines.forEach(line => {
                const idx = line.indexOf('|');
                if (idx <= 0) return;
                const key = line.slice(0, idx).trim();
                const value = line.slice(idx + 1).trim().replace(/\\n/g, '\n');
                if (key) overrides[key] = value;
            });

            const emojiReplacementInput = this.$('#setting-emoji-replacements')?.value || '';
            const emojiReplacementLines = parseLines(emojiReplacementInput);
            const emojiReplacements = {};
            emojiReplacementLines.forEach(line => {
                const idx = line.indexOf('=');
                if (idx <= 0) return;
                const key = line.slice(0, idx).trim();
                const value = line.slice(idx + 1).trim();
                if (key) emojiReplacements[key] = value;
            });

            const botSettings = {
                self_name: this.$('#setting-self-name').value,
                system_prompt: this.$('#setting-system-prompt')?.value ?? '',
                system_prompt_overrides: overrides,
                reply_suffix: this.$('#setting-reply-suffix').value,
                emoji_policy: this.$('#setting-emoji-policy')?.value,
                emoji_replacements: emojiReplacements,
                stream_reply: this.$('#setting-stream-reply')?.checked,
                group_reply_only_when_at: this.$('#setting-group-at-only').checked,
                whitelist_enabled: this.$('#setting-whitelist-enabled').checked,
                whitelist: parseLines(this.$('#setting-whitelist').value),
                voice_to_text: this.$('#setting-voice-to-text')?.checked,
                voice_to_text_fail_reply: this.$('#setting-voice-to-text-fail-reply')?.value,
                memory_db_path: this.$('#setting-memory-db-path')?.value,
                memory_context_limit: parseNumber(this.$('#setting-memory-context-limit')?.value),
                memory_ttl_sec: parseNumberOrNull(this.$('#setting-memory-ttl-sec')?.value),
                memory_cleanup_interval_sec: parseNumber(this.$('#setting-memory-cleanup-interval-sec')?.value),
                memory_seed_on_first_reply: this.$('#setting-memory-seed-on-first-reply')?.checked,
                memory_seed_limit: parseNumber(this.$('#setting-memory-seed-limit')?.value),
                memory_seed_load_more: parseNumber(this.$('#setting-memory-seed-load-more')?.value),
                memory_seed_load_more_interval_sec: parseNumber(this.$('#setting-memory-seed-load-more-interval-sec')?.value),
                memory_seed_group: this.$('#setting-memory-seed-group')?.checked,
                context_rounds: parseNumber(this.$('#setting-context-rounds')?.value),
                context_max_tokens: parseNumber(this.$('#setting-context-max-tokens')?.value),
                history_max_chats: parseNumber(this.$('#setting-history-max-chats')?.value),
                history_ttl_sec: parseNumberOrNull(this.$('#setting-history-ttl-sec')?.value),
                history_log_interval_sec: parseNumber(this.$('#setting-history-log-interval-sec')?.value),
                poll_interval_sec: parseNumber(this.$('#setting-poll-interval-sec')?.value),
                poll_interval_min_sec: parseNumber(this.$('#setting-poll-interval-min-sec')?.value),
                poll_interval_max_sec: parseNumber(this.$('#setting-poll-interval-max-sec')?.value),
                poll_interval_backoff_factor: parseNumber(this.$('#setting-poll-interval-backoff-factor')?.value),
                min_reply_interval_sec: parseNumber(this.$('#setting-min-reply-interval-sec')?.value),
                merge_user_messages_sec: parseNumber(this.$('#setting-merge-user-messages-sec')?.value),
                merge_user_messages_max_wait_sec: parseNumber(this.$('#setting-merge-user-messages-max-wait-sec')?.value),
                reply_chunk_size: parseNumber(this.$('#setting-reply-chunk-size')?.value),
                reply_chunk_delay_sec: parseNumber(this.$('#setting-reply-chunk-delay-sec')?.value),
                max_concurrency: parseNumber(this.$('#setting-max-concurrency')?.value),
                natural_split_enabled: this.$('#setting-natural-split-enabled')?.checked,
                natural_split_min_chars: parseNumber(this.$('#setting-natural-split-min-chars')?.value),
                natural_split_max_chars: parseNumber(this.$('#setting-natural-split-max-chars')?.value),
                natural_split_max_segments: parseNumber(this.$('#setting-natural-split-max-segments')?.value),
                stream_buffer_chars: parseNumber(this.$('#setting-stream-buffer-chars')?.value),
                stream_chunk_max_chars: parseNumber(this.$('#setting-stream-chunk-max-chars')?.value),
                config_reload_sec: parseNumber(this.$('#setting-config-reload-sec')?.value),
                reload_ai_client_on_change: this.$('#setting-reload-ai-client-on-change')?.checked,
                reload_ai_client_module: this.$('#setting-reload-ai-client-module')?.checked,
                keepalive_idle_sec: parseNumber(this.$('#setting-keepalive-idle-sec')?.value),
                reconnect_max_retries: parseNumber(this.$('#setting-reconnect-max-retries')?.value),
                reconnect_backoff_sec: parseNumber(this.$('#setting-reconnect-backoff-sec')?.value),
                reconnect_max_delay_sec: parseNumber(this.$('#setting-reconnect-max-delay-sec')?.value),
                group_include_sender: this.$('#setting-group-include-sender')?.checked,
                send_exact_match: this.$('#setting-send-exact-match')?.checked,
                send_fallback_current_chat: this.$('#setting-send-fallback-current-chat')?.checked,
                filter_mute: this.$('#setting-filter-mute')?.checked,
                ignore_official: this.$('#setting-ignore-official')?.checked,
                ignore_service: this.$('#setting-ignore-service')?.checked,
                ignore_names: parseLines(this.$('#setting-ignore-names')?.value || ''),
                ignore_keywords: parseLines(this.$('#setting-ignore-keywords')?.value || ''),
                personalization_enabled: this.$('#setting-personalization-enabled')?.checked,
                profile_update_frequency: parseNumber(this.$('#setting-profile-update-frequency')?.value),
                remember_facts_enabled: this.$('#setting-remember-facts-enabled')?.checked,
                max_context_facts: parseNumber(this.$('#setting-max-context-facts')?.value),
                profile_inject_in_prompt: this.$('#setting-profile-inject-in-prompt')?.checked,
                control_commands_enabled: this.$('#setting-control-commands-enabled')?.checked,
                control_command_prefix: this.$('#setting-control-command-prefix')?.value,
                control_allowed_users: parseLines(this.$('#setting-control-allowed-users')?.value || ''),
                control_reply_visible: this.$('#setting-control-reply-visible')?.checked,
                quiet_hours_enabled: this.$('#setting-quiet-hours-enabled')?.checked,
                quiet_hours_start: this.$('#setting-quiet-hours-start')?.value,
                quiet_hours_end: this.$('#setting-quiet-hours-end')?.value,
                quiet_hours_reply: this.$('#setting-quiet-hours-reply')?.value,
                usage_tracking_enabled: this.$('#setting-usage-tracking-enabled')?.checked,
                daily_token_limit: parseNumber(this.$('#setting-daily-token-limit')?.value),
                token_warning_threshold: parseNumber(this.$('#setting-token-warning-threshold')?.value),
                emotion_detection_enabled: this.$('#setting-emotion-detection-enabled')?.checked,
                emotion_detection_mode: this.$('#setting-emotion-detection-mode')?.value,
                emotion_inject_in_prompt: this.$('#setting-emotion-inject-in-prompt')?.checked,
                emotion_log_enabled: this.$('#setting-emotion-log-enabled')?.checked
            };

            const randomDelay = parseRange(
                this.$('#setting-random-delay-min-sec')?.value,
                this.$('#setting-random-delay-max-sec')?.value
            );
            if (randomDelay) botSettings.random_delay_range_sec = randomDelay;

            const naturalDelay = parseRange(
                this.$('#setting-natural-split-delay-min-sec')?.value,
                this.$('#setting-natural-split-delay-max-sec')?.value
            );
            if (naturalDelay) botSettings.natural_split_delay_sec = naturalDelay;

            const replyQuoteMode = this.$('#setting-reply-quote-mode')?.value;
            if (replyQuoteMode) botSettings.reply_quote_mode = replyQuoteMode;

            const replyQuoteTemplate = this.$('#setting-reply-quote-template')?.value;
            if (replyQuoteTemplate != null) botSettings.reply_quote_template = replyQuoteTemplate;

            if (quoteMaxChars !== undefined && !Number.isNaN(quoteMaxChars)) {
                botSettings.reply_quote_max_chars = quoteMaxChars;
            }
            if (quoteTimeoutSec !== undefined && !Number.isNaN(quoteTimeoutSec)) {
                botSettings.reply_quote_timeout_sec = quoteTimeoutSec;
            }
            const quoteFallback = this.$('#setting-reply-quote-fallback');
            if (quoteFallback) {
                botSettings.reply_quote_fallback_to_text = quoteFallback.checked;
            }

            const loggingSettings = {
                level: this.$('#setting-log-level')?.value,
                format: this.$('#setting-log-format')?.value,
                file: this.$('#setting-log-file')?.value,
                max_bytes: parseNumber(this.$('#setting-log-max-bytes')?.value),
                backup_count: parseNumber(this.$('#setting-log-backup-count')?.value),
                log_message_content: this.$('#setting-log-message-content')?.checked,
                log_reply_content: this.$('#setting-log-reply-content')?.checked
            };

            // 合并到当前配置
            let newConfig = {
                ...this.currentConfig,
                bot: {
                    ...this.currentConfig.bot,
                    ...botSettings
                },
                logging: {
                    ...this.currentConfig.logging,
                    ...loggingSettings
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
            toast.error(toast.getErrorMessage(error, '保存配置异常'));
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
                            toast.error(toast.getErrorMessage(e, '激活预设异常'));
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
                toast.error(toast.getErrorMessage(error, '切换预设操作发生错误'));
            }
            throw error; // 继续抛出，让按钮点击事件捕获
        }
    }
}
