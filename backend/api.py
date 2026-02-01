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

from .bot_manager import get_bot_manager
from backend.config import CONFIG
from backend.utils.logging import setup_logging, get_logging_settings

# 配置日志
level, log_file, max_bytes, backup_count = get_logging_settings(CONFIG)
setup_logging(level, log_file, max_bytes, backup_count)

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
        from backend.config import CONFIG
        from backend.core.memory import MemoryManager
        
        db_path = CONFIG.get('bot', {}).get('sqlite_db_path', 'data/chat_memory.db')
        limit = request.args.get('limit', 50, type=int)
        
        # 使用临时 MemoryManager 实例读取（Context Manager 自动关闭）
        with MemoryManager(db_path) as mem:
            messages = mem.get_global_recent_messages(limit=limit)
            
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
                
                for new_p in new_presets:
                    # 查找内存中对应的旧预设
                    old_p = next((p for p in current_presets if p.get('name') == new_p.get('name')), None)
                    if old_p:
                        # 如果新 key 为空或为掩码，且旧 key 存在，则恢复旧 key
                        new_key = new_p.get('api_key', '')
                        if not new_key or new_key.startswith('****') or '****' in new_key:
                             # 从内存配置中恢复原始 key
                             # 注意：内存中的 key 可能是已经加载了 api_keys.py 的
                             # 如果想保存到 override，我们需要决定是保存真实 key 还是保留引用
                             # 这里为了简单，如果用户没改，就不覆盖（如果 config_override 里本来就没 key，那就没 key）
                             # 但如果 config_override 里有 key，我们需要保持它
                             
                             # 更稳妥的做法：
                             # 如果是隐藏状态，我们如果在 override 里也找不到 key，那就不写入这个字段
                             # 让下次加载时继续用 config.py 或 api_keys.py 的
                             
                             # 只有用户输入了新的 clear text key，我们才写入 override
                             
                             # 但如果用户改了别的字段（比如 alias），我们必须保存 preset 的其他信息
                             # 所以如果 key 没变，我们应该尽量从 existing (文件里) 拿 key，
                             # 或者如果文件里没有，就不写 key 字段
                             
                             pass
                        else:
                            # 用户输入了新 key，正常保存
                            pass
                    
                    # 实际逻辑简化：
                    # 遍历 new_presets，处理 api_key
                    key = new_p.get('api_key')
                    if not key:
                         # 没传 key，可能是前端为了安全没发
                         # 我们删掉这个字段，这样 python dict update 时就不会覆盖掉文件里已有的（如果有）
                         # 但等等，我们是整存整取 presets list
                         # 所以 list 里的 object 必须包含完整信息
                         
                         # 我们需要构造一个完整的 presets list 写入 file
                         # 如果 new_p['api_key'] 是空的/掩码，我们需要填入 "correct" value to save
                         
                         # Case 1: 用户没改 key。我们应该保持 file 里原有的 key (如果有) 
                         # 或者如果 file 里没有 (用的 api_keys.py)，那 file 里也不该有。
                         
                         # 让我们看看 existing (file content)
                         existing_api = existing.get('api', {})
                         existing_presets = existing_api.get('presets', [])
                         existing_p_file = next((p for p in existing_presets if p.get('name') == new_p.get('name')), None)
                         
                         if existing_p_file and 'api_key' in existing_p_file:
                             # 文件里原本有 key，保持它
                             new_p['api_key'] = existing_p_file['api_key']
                         else:
                             # 文件里原本没 key (用的默认或 api_keys.py)
                             # 那就不存 api_key 字段
                             if 'api_key' in new_p:
                                 del new_p['api_key']
                    elif '****' in key:
                         # 是掩码，说明没改
                         # 同上
                         if existing_p_file and 'api_key' in existing_p_file:
                             new_p['api_key'] = existing_p_file['api_key']
                         else:
                             if 'api_key' in new_p:
                                 del new_p['api_key']
                    
                    # 移除前端可能传来的辅助字段
                    if 'api_key_configured' in new_p: del new_p['api_key_configured']
                    if 'api_key_masked' in new_p: del new_p['api_key_masked']
                
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
        
        return jsonify({'success': True, 'message': '配置已保存'})
    except Exception as e:
        logger.error(f"保存配置失败: {e}")
        return jsonify({'success': False, 'message': f'保存失败: {str(e)}'})


@app.route('/api/logs', methods=['GET'])
async def get_logs():
    """获取日志"""
    try:
        from backend.config import CONFIG
        log_file = CONFIG.get('logging', {}).get('file', 'wxauto_logs/bot.log')
        
        if not os.path.exists(log_file):
            return jsonify({'success': True, 'logs': []})
            
        lines_count = request.args.get('lines', 500, type=int)
        
        # 简单读取最后 N 行 (对于大文件可能需要优化，但日志轮转已限制了大小)
        with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
            # 过滤空行
            lines = [line.strip() for line in lines if line.strip()]
            return jsonify({'success': True, 'logs': lines[-lines_count:]})
    except Exception as e:
        logger.error(f"读取日志失败: {e}")
        return jsonify({'success': False, 'message': f'读取日志失败: {str(e)}'})


@app.route('/api/logs/clear', methods=['POST'])
async def clear_logs():
    """清空日志"""
    try:
        from backend.config import CONFIG
        log_file = CONFIG.get('logging', {}).get('file', 'wxauto_logs/bot.log')
        
        # 清空文件内容
        with open(log_file, 'w', encoding='utf-8') as f:
             f.write("")
             
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
