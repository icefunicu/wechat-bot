"""
微信AI助手 - Quart 异步 API 服务

为 Electron 客户端提供后端 API 接口。
使用 Quart（Flask 异步版本）实现统一的 asyncio 事件循环。
"""

from quart import Quart, jsonify, request
from quart_cors import cors
import logging
import os
import json
import asyncio

from .bot_manager import get_bot_manager
from backend.config import CONFIG
from backend.utils.logging import setup_logging, get_logging_settings

# 配置日志
level, log_file, max_bytes, backup_count, format_type = get_logging_settings(CONFIG)
setup_logging(level, log_file, max_bytes, backup_count, format_type)

logger = logging.getLogger(__name__)

# 创建 Quart 应用
app = Quart(__name__)
app = cors(app, allow_origin="*")

# 获取 BotManager 实例
manager = get_bot_manager()


# ═══════════════════════════════════════════════════════════════════════════════
#                               API 路由
# ═══════════════════════════════════════════════════════════════════════════════

@app.route('/api/status', methods=['GET'])
async def get_status():
    """获取机器人状态"""
    return jsonify(manager.get_status())


@app.route('/api/start', methods=['POST'])
async def start_bot():
    """启动机器人"""
    result = await manager.start()
    return jsonify(result)


@app.route('/api/stop', methods=['POST'])
async def stop_bot():
    """停止机器人"""
    result = await manager.stop()
    return jsonify(result)


@app.route('/api/pause', methods=['POST'])
async def pause_bot():
    """暂停机器人"""
    result = await manager.pause()
    return jsonify(result)


@app.route('/api/resume', methods=['POST'])
async def resume_bot():
    """恢复机器人"""
    result = await manager.resume()
    return jsonify(result)


@app.route('/api/restart', methods=['POST'])
async def restart_bot():
    """重启机器人"""
    result = await manager.restart()
    return jsonify(result)


@app.route('/api/messages', methods=['GET'])
async def get_messages():
    """获取消息历史"""
    try:
        import asyncio
        
        limit = request.args.get('limit', 50, type=int)
        
        # 使用共享的 MemoryManager 实例
        mem_mgr = manager.get_memory_manager()
        
        messages = await asyncio.to_thread(mem_mgr.get_global_recent_messages, limit=limit)
            
        return jsonify({'success': True, 'messages': messages})
    except Exception as e:
        logger.error(f"获取消息失败: {e}")
        return jsonify({'success': False, 'message': f'获取消息失败: {str(e)}'})

@app.route('/api/send', methods=['POST'])
async def send_message():
    """发送消息"""
    try:
        data = await request.get_json()
        target = data.get('target')
        content = data.get('content')
        
        if not target or not content:
            return jsonify({'success': False, 'message': '缺少目标或内容'})
            
        result = await manager.send_message(target, content)
        return jsonify(result)
    except Exception as e:
        logger.error(f"发送消息异常: {e}")
        return jsonify({'success': False, 'message': f'发送异常: {str(e)}'})

@app.route('/api/usage', methods=['GET'])
async def get_usage():
    """获取使用统计"""
    try:
        stats = manager.get_usage()
        return jsonify({'success': True, 'stats': stats})
    except Exception as e:
         return jsonify({'success': False, 'message': str(e)})


@app.route('/api/config', methods=['GET'])
async def get_config():
    """获取配置"""
    try:
        from backend.config import CONFIG
        
        # 提取 API 配置（隐藏敏感信息）
        api_cfg = CONFIG.get('api', {})
        
        # 处理预设列表 - 隐藏 API Key
        presets = []
        for preset in api_cfg.get('presets', []):
            p = preset.copy()
            key = p.get('api_key', '')
            # 检查是否配置了有效的 API Key
            if key and not key.startswith('YOUR_'):
                p['api_key_configured'] = True
                p['api_key_masked'] = key[:8] + '****' + key[-4:] if len(key) > 12 else '****'
            else:
                p['api_key_configured'] = False
                p['api_key_masked'] = ''
            
            # 删除实际 Key
            if 'api_key' in p:
                del p['api_key']
            presets.append(p)
            
        # 结果中替换处理后的 presets
        api_cfg_safe = api_cfg.copy()
        api_cfg_safe['presets'] = presets
        
        # 构造完整返回结构
        response = {
            'success': True,
            'api': api_cfg_safe,
            'bot': CONFIG.get('bot', {}),
            'logging': CONFIG.get('logging', {})
        }
        return jsonify(response)
    except Exception as e:
        logger.error(f"获取配置失败: {e}")
        return jsonify({'success': False, 'message': f'获取配置失败: {str(e)}'})





@app.route('/api/config', methods=['POST'])
async def save_config():
    """保存配置覆写"""
    try:
        data = await request.get_json()
        override_file = os.path.join('data', 'config_override.json')
        
        # 确保目录存在
        os.makedirs(os.path.dirname(override_file), exist_ok=True)
        
        # 读取现有覆写
        existing = {}
        if os.path.exists(override_file):
            try:
                with open(override_file, 'r', encoding='utf-8') as f:
                    existing = json.load(f)
            except Exception:
                pass
        
        # 合并新配置
        from backend.config import CONFIG
        
        for section, settings in data.items():
            if section not in existing:
                existing[section] = {}
            
            # 特殊处理 api.presets 的 API Key 保护
            if section == 'api' and 'presets' in settings:
                current_presets = CONFIG.get('api', {}).get('presets', [])
                new_presets = settings['presets']
                
                # 获取 override 文件中的旧配置，用于辅助判断
                existing_api = existing.get('api', {})
                existing_presets = existing_api.get('presets', [])

                for new_p in new_presets:
                    key = new_p.get('api_key')
                    
                    # 判断是否需要恢复 Key：
                    # 1. 带有 _keep_key 标记 (前端明确表示没改)
                    # 2. Key 为空 (前端没传)
                    # 3. Key 是掩码 (前端传回了掩码)
                    should_restore = new_p.get('_keep_key') or not key or '****' in key
                    
                    if should_restore:
                        p_name = new_p.get('name')
                        logger.info(f"尝试恢复预设 {p_name} 的 API Key")
                        # 查找内存中的真实 Key
                        mem_p = next((p for p in current_presets if p.get('name') == p_name), None)
                        
                        if mem_p and mem_p.get('api_key') and not mem_p.get('api_key').startswith('****'):
                            # 内存里有明文 Key，直接用
                            new_p['api_key'] = mem_p['api_key']
                            logger.info(f"从内存恢复了预设 {p_name} 的 Key")
                        else:
                            # 尝试从 existing file 里找
                            file_p = next((p for p in existing_presets if p.get('name') == p_name), None)
                            if file_p and file_p.get('api_key'):
                                new_p['api_key'] = file_p['api_key']
                                logger.info(f"从文件恢复了预设 {p_name} 的 Key")
                            else:
                                # 实在找不到，就只能删掉 key 字段了
                                logger.warning(f"未能恢复预设 {p_name} 的 Key")
                                if 'api_key' in new_p:
                                    del new_p['api_key']
                    
                    # 清理临时字段
                    for field in ['_keep_key', 'api_key_configured', 'api_key_masked']:
                        if field in new_p:
                            del new_p[field]
                
            if isinstance(settings, dict):
                existing[section].update(settings)
            else:
                existing[section] = settings
        
        # 保存
        with open(override_file, 'w', encoding='utf-8') as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
            
        # 实时更新内存中的配置
        from backend.config import _apply_config_overrides, _apply_api_keys, _apply_prompt_overrides
        _apply_config_overrides(CONFIG)
        _apply_api_keys(CONFIG) # 重新应用 Key 可能有变
        _apply_prompt_overrides(CONFIG)

        # 🔍 检测模型切换并输出高亮日志
        new_api_cfg = CONFIG.get('api', {})
        new_active = new_api_cfg.get('active_preset')
        
        # 简单的变化检测（基于内存中最新的 CONFIG）
        # 注意：这里无法直接对比旧值，除非我们之前存了。
        # 但我们可以通过 manager 获取当前运行时的 bot 状态来对比？
        # 或者简单地总是打印当前激活的模型，作为确认。
        if new_active:
             preset_info = next((p for p in new_api_cfg.get('presets', []) if p['name'] == new_active), {})
             model_name = preset_info.get('model', 'Unknown')
             alias = preset_info.get('alias', '')
             
             logger.info("\n" + "═"*50)
             logger.info(f"✨ 模型配置已更新 | 当前预设: {new_active}")
             logger.info(f"📦 模型: {model_name} | 👤 别名: {alias}")
             logger.info("═"*50 + "\n")

        # 构造完整返回结构 (复用 get_config 的逻辑)
        # 必须返回完整配置，否则前端状态会丢失
        response_data = await get_config() # 直接调用 get_config 获取处理好的安全配置
        if isinstance(response_data, tuple):
             # get_config 返回的是 (json, status) 或 Response 对象
             # 但这里它是 async 函数且返回 jsonify 结果
             # jsonify 返回的是 Response 对象
             # 我们需要重新构造数据，或者提取数据
             # 为避免复杂，直接复制 get_config 的逻辑更安全
             pass
        
        # 复用逻辑：构造安全的返回数据
        api_cfg_safe = new_api_cfg.copy()
        safe_presets = []
        for preset in new_api_cfg.get('presets', []):
            p = preset.copy()
            key = p.get('api_key', '')
            if key and not key.startswith('YOUR_'):
                p['api_key_configured'] = True
                p['api_key_masked'] = key[:8] + '****' + key[-4:] if len(key) > 12 else '****'
            else:
                p['api_key_configured'] = False
                p['api_key_masked'] = ''
            if 'api_key' in p: del p['api_key']
            safe_presets.append(p)
        api_cfg_safe['presets'] = safe_presets
        
        response = {
            'success': True,
            'message': '配置已保存',
            'config': { # 前端期望的是 config 字段包裹 api/bot/logging，还是直接平铺？
                        # 看前端：const { success, ...config } = result; 
                        # 前端SettingsPage.js: this.currentConfig = result.config;
                        # 所以这里应该返回一个 config 对象
                'api': api_cfg_safe,
                'bot': CONFIG.get('bot', {}),
                'logging': CONFIG.get('logging', {})
            }
        }
        
        return jsonify(response)
    except Exception as e:
        logger.error(f"保存配置失败: {e}")
        return jsonify({'success': False, 'message': f'保存失败: {str(e)}'})


@app.route('/api/test_connection', methods=['POST'])
async def test_connection():
    """测试 LLM 连接"""
    try:
        data = await request.get_json()
        preset_name = data.get('preset_name')
        
        # 获取配置
        from backend.config import CONFIG
        api_cfg = CONFIG.get('api', {})
        presets = api_cfg.get('presets', [])
        
        target_preset = None
        if preset_name:
            target_preset = next((p for p in presets if p['name'] == preset_name), None)
        else:
            # 如果未指定，使用当前激活的
            active_name = api_cfg.get('active_preset')
            target_preset = next((p for p in presets if p['name'] == active_name), None)
            
        if not target_preset:
            return jsonify({'success': False, 'message': '未找到指定的预设配置'})
            
        # 实例化 AIClient
        from backend.core.ai_client import AIClient
        
        # 构造参数，注意处理默认值
        # 注意：AIClient 需要完整的参数，这里做一些回退处理
        client = AIClient(
            base_url=target_preset.get('base_url') or api_cfg.get('base_url'),
            api_key=target_preset.get('api_key') or api_cfg.get('api_key'),
            model=target_preset.get('model') or api_cfg.get('model'),
            timeout_sec=(
                target_preset.get('timeout_sec')
                or target_preset.get('timeout')
                or api_cfg.get('timeout_sec')
                or api_cfg.get('timeout', 10.0)
            ),
            max_retries=0 # 测试时不重试
        )
        
        # 调用 probe
        success = await client.probe()
        
        if success:
            return jsonify({'success': True, 'message': '连接测试成功'})
        else:
            return jsonify({'success': False, 'message': '连接测试失败，请检查配置或网络'})
            
    except Exception as e:
        logger.error(f"连接测试异常: {e}")
        return jsonify({'success': False, 'message': f'测试异常: {str(e)}'})


@app.route('/api/logs', methods=['GET'])
async def get_logs():
    """获取日志"""
    try:
        from backend.config import CONFIG
        log_file = CONFIG.get('logging', {}).get('file', 'wxauto_logs/bot.log')
        
        if not os.path.exists(log_file):
            return jsonify({'success': True, 'logs': []})
            
        lines_count = request.args.get('lines', 500, type=int)
        
        def _read_logs():
            if lines_count <= 0:
                return []
            with open(log_file, 'rb') as f:
                f.seek(0, os.SEEK_END)
                end = f.tell()
                buffer = b''
                lines = []
                chunk_size = 8192
                while end > 0 and len(lines) <= lines_count:
                    read_size = min(chunk_size, end)
                    end -= read_size
                    f.seek(end)
                    buffer = f.read(read_size) + buffer
                    lines = buffer.splitlines()
                decoded = [line.decode('utf-8', errors='replace').strip() for line in lines if line.strip()]
                return decoded[-lines_count:]

        logs = await asyncio.to_thread(_read_logs)
        return jsonify({'success': True, 'logs': logs})
    except Exception as e:
        logger.error(f"读取日志失败: {e}")
        return jsonify({'success': False, 'message': f'读取日志失败: {str(e)}'})


@app.route('/api/logs/clear', methods=['POST'])
async def clear_logs():
    """清空日志"""
    try:
        from backend.config import CONFIG
        import asyncio
        
        log_file = CONFIG.get('logging', {}).get('file', 'wxauto_logs/bot.log')
        
        def _clear_file():
            # 清空文件内容
            with open(log_file, 'w', encoding='utf-8') as f:
                 f.write("")
                 
        await asyncio.to_thread(_clear_file)
             
        return jsonify({'success': True, 'message': '日志已清空'})
    except Exception as e:
        return jsonify({'success': False, 'message': f"清空日志失败: {str(e)}"})


# ═══════════════════════════════════════════════════════════════════════════════
#                               启动入口
# ═══════════════════════════════════════════════════════════════════════════════

async def run_server_async(host='0.0.0.0', port=5000):
    """异步启动 API 服务"""
    logger.info(f"API 服务启动于 http://{host}:{port}")
    await app.run_task(host=host, port=port)


def run_server(host='0.0.0.0', port=5000, debug=False):
    """启动 API 服务（同步入口）"""
    import asyncio
    logger.info(f"API 服务启动于 http://{host}:{port} (Debug={debug})")
    
    if debug:
        # Debug 模式下使用 app.run 启用 reloader
        # 注意：这会阻塞，直到服务停止
        app.run(host=host, port=port, debug=True, use_reloader=True)
    else:
        # 生产模式使用 asyncio.run
        asyncio.run(app.run_task(host=host, port=port))


if __name__ == '__main__':
    run_server(debug=True)
