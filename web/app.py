"""
微信机器人 Web 状态面板。

运行方式:
    python -m web.app

功能:
    - 查看机器人运行状态
    - 今日回复统计
    - Token 用量监控
    - 暂停/恢复控制
"""

from __future__ import annotations

import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from flask import Flask, render_template, jsonify, request
except ImportError:
    print("❌ Flask 未安装，请运行: pip install flask")
    sys.exit(1)

from app.core.bot_control import get_bot_state, get_usage_tracker


app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False

@app.template_filter('number_format')
def number_format(value):
    try:
        return "{:,}".format(int(value))
    except (ValueError, TypeError):
        return value


# ═══════════════════════════════════════════════════════════════════════════════
#                               进程管理 (Unified Logging)
# ═══════════════════════════════════════════════════════════════════════════════


import subprocess
import signal
import json
import psutil
from app.utils.ipc import IPCManager

class ProcessManager:
    """管理机器人子进程"""
    def __init__(self):
        self.process = None
        # 使用统一的日志文件路径
        self.log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "wxauto_logs")
        os.makedirs(self.log_dir, exist_ok=True)
        self.log_file_path = os.path.join(self.log_dir, "bot.log")
        self.ipc = IPCManager()

    def _get_system_process(self):
        """通过 psutil 查找系统中的机器人进程"""
        for proc in psutil.process_iter(['pid', 'cmdline', 'create_time']):
            try:
                cmdline = proc.info.get('cmdline', [])
                # 匹配 run.py start
                if cmdline and 'run.py' in cmdline and 'start' in cmdline:
                    return proc
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return None

    def is_running(self):
        """检查进程是否在运行"""
        # 1. Check managed process object
        if self.process is not None:
            if self.process.poll() is None:
                return True
            else:
                self.process = None # Clean up dead handle
        
        # 2. Check system process (orphan adoption)
        return self._get_system_process() is not None

    def start_bot(self):
        """启动机器人进程"""
        if self.is_running():
            return False, "机器人已在运行中"
        
        try:
            # 打开日志文件 (append mode), 强制 UTF-8
            log_file = open(self.log_file_path, "a", encoding="utf-8")
            
            # 使用新进程启动机器人，强制 UTF-8 环境
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            
            # 获取项目根目录
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
            # 使用虚拟环境中的 Python 解释器
            if sys.platform == 'win32':
                venv_python = os.path.join(project_root, ".venv", "Scripts", "python.exe")
            else:
                venv_python = os.path.join(project_root, ".venv", "bin", "python")
            
            # 如果虚拟环境 Python 不存在，回退到当前 Python
            if not os.path.exists(venv_python):
                venv_python = sys.executable

            cmd = [venv_python, "run.py", "start"]
            
            # Windows: 使用 CREATE_NO_WINDOW 在后台运行，不弹出窗口
            # 注意：不能用 CREATE_NEW_CONSOLE，否则日志无法重定向
            creationflags = 0
            if sys.platform == 'win32':
                creationflags = subprocess.CREATE_NO_WINDOW
            
            self.process = subprocess.Popen(
                cmd,
                cwd=project_root,
                stdout=log_file,
                stderr=log_file,
                creationflags=creationflags,
                env=env
            )
            return True, f"启动指令已在后台执行 (PID: {self.process.pid})"
        except Exception as e:
            return False, f"启动失败: {str(e)}"

    def stop_bot(self):
        """停止机器人进程"""
        # Get handle: either self.process or psutil process
        proc = self.process if (self.process and self.process.poll() is None) else self._get_system_process()
        
        if not proc:
            return False, "未找到运行中的机器人进程"

        try:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except: 
                # Popen uses subprocess.TimeoutExpired, psutil uses psutil.TimeoutExpired
                # generic catch is fine here
                proc.kill()
            
            self.process = None
            return True, "机器人已停止"
        except Exception as e:
            return False, f"停止失败: {str(e)}"
    
    def get_process_uptime(self):
        """获取进程运行时长(秒)"""
        # 优先使用 managed process
        if self.process and self.process.poll() is None:
            try:
                p = psutil.Process(self.process.pid)
                return time.time() - p.create_time()
            except: pass
            
        # 尝试查找系统进程
        proc = self._get_system_process()
        if proc:
            try:
                return time.time() - proc.info['create_time']
            except: pass
            
        return 0

# 全局进程管理器实例
pm = ProcessManager()


@app.route("/")
def index():
    """首页仪表盘"""
    state = get_bot_state()
    # 强制重新加载文件状态，确保多进程同步
    state.load() 
    
    is_running = pm.is_running()
    # 如果没运行，Uptime 为 "未运行" 或 0
    uptime_str = state.get_uptime_str() if is_running else "未运行"

    return render_template(
        "dashboard.html",
        state=state,
        is_paused=state.is_paused,
        is_running=is_running,
        uptime=uptime_str,
        today_replies=state.today_replies,
        today_tokens=state.today_tokens,
        total_replies=state.total_replies,
    )

@app.route("/settings")
def page_settings():
    """设置页面"""
    # 只读取覆盖配置，不读取默认配置，避免“覆盖默认”
    override_path = os.path.join("data", "config_override.json")
    if os.path.exists(override_path):
        try:
            with open(override_path, "r", encoding="utf-8") as f:
                display_config = json.load(f)
        except:
            display_config = {}
    else:
        display_config = {}

    return render_template("settings.html", config=display_config)


@app.route("/chat")
def page_chat():
    """聊天控制台页面"""
    return render_template("chat.html")


@app.route("/logs")
def page_logs():
    """系统日志页面"""
    return render_template("logs.html")



# ═══════════════════════════════════════════════════════════════════════════════
#                               API 路由 - 进程控制
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/start", methods=["POST"])
def api_start():
    success, msg = pm.start_bot()
    return jsonify({"success": success, "message": msg})


@app.route("/api/stop", methods=["POST"])
def api_stop():
    success, msg = pm.stop_bot()
    return jsonify({"success": success, "message": msg})


@app.route("/api/restart", methods=["POST"])
def api_restart():
    # 停止
    pm.stop_bot()
        
    # 启动
    success, msg = pm.start_bot()
    return jsonify({"success": success, "message": "重启指令已发送: " + msg})



@app.route("/api/status")
def api_status():
    """获取机器人状态"""
    state = get_bot_state()
    state.load() # 重新加载
    
    is_running = pm.is_running()
    
    # 修复 Uptime 逻辑：如果进程不在运行，uptime 应该是 0 或提示信息
    # 且不能自动增加
    uptime_str = state.get_uptime_str()
    if not is_running:
        uptime_str = "未运行"
    
    return jsonify({
        "running": is_running,
        "is_paused": state.is_paused,
        "pause_reason": state.pause_reason,
        "uptime": uptime_str,
        "today_replies": state.today_replies,
        "today_tokens": state.today_tokens,
        "total_replies": state.total_replies,
    })


from app.config import CONFIG

@app.route("/api/config", methods=["GET", "POST"])
def api_config():
    override_path = os.path.join("data", "config_override.json")
    
    if request.method == "POST":
        try:
            new_config = request.json
            # 确保目录存在
            os.makedirs("data", exist_ok=True)
            # 写入覆盖配置
            with open(override_path, "w", encoding="utf-8") as f:
                json.dump(new_config, f, indent=4, ensure_ascii=False)
            return jsonify({"success": True, "message": "配置已保存 (仅保存变更项)，请重启机器人生效"})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)})
            
    # GET - Return defaults, overrides, and presets
    overrides = {}
    if os.path.exists(override_path):
        try:
            with open(override_path, "r", encoding="utf-8") as f:
                overrides = json.load(f)
        except Exception:
            overrides = {}
            
    return jsonify({
        "defaults": CONFIG,
        "overrides": overrides,
        "presets": CONFIG.get("api", {}).get("presets", [])
    })


@app.route("/api/pause", methods=["POST"])
def api_pause():
    state = get_bot_state()
    state.load()
    state.set_paused(True, request.json.get("reason", "Web 控制台暂停") if request.json else "Web 控制台暂停")
    return jsonify({"success": True, "message": "机器人已暂停"})


@app.route("/api/resume", methods=["POST"])
def api_resume():
    state = get_bot_state()
    state.load()
    state.set_paused(False)
    return jsonify({"success": True, "message": "机器人已恢复"})


# ═══════════════════════════════════════════════════════════════════════════════
#                               API 路由 - 日志
# ═══════════════════════════════════════════════════════════════════════════════


@app.route("/api/logs", methods=["GET", "DELETE"])
def api_logs():
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "wxauto_logs")
    log_file = os.path.join(log_dir, "bot.log")
    
    if request.method == "DELETE":
        try:
            if os.path.exists(log_file):
                # 清空文件内容而不是删除文件，防止文件占用锁
                with open(log_file, "w", encoding="utf-8") as f:
                    f.write("")
                return jsonify({"success": True, "message": "日志已清空"})
            return jsonify({"success": False, "error": "日志文件不存在"})
        except Exception as e:
            return jsonify({"success": False, "error": f"清空失败: {e}"})

    # GET logic (same as before)
    try:
        if not os.path.exists(log_file):
            return jsonify({"success": True, "logs": []})
        
        lines_count = int(request.args.get("lines", 100))
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            all_lines = f.readlines()
            logs = [line.strip() for line in all_lines[-lines_count:]]
        return jsonify({"success": True, "logs": logs})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/usage")
def api_usage():
    try:
        tracker = get_usage_tracker()
        daily = tracker.get_daily_usage()
        return jsonify({
            "today": daily,
            "success": True,
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/messages")
def api_messages():
    """获取聊天记录"""
    msgs = pm.ipc.get_recent_messages(limit=100)
    return jsonify({"success": True, "messages": msgs})


@app.route("/api/send", methods=["POST"])
def api_send():
    """发送消息"""
    data = request.json
    target = data.get("target")
    content = data.get("content")
    
    if not target or not content:
        return jsonify({"success": False, "error": "Missing target or content"})
        
    pm.ipc.send_command("send_msg", {"target": target, "content": content})
    return jsonify({"success": True})



def main():
    """启动 Web 服务"""
    # 确保日志目录存在
    os.makedirs("wxauto_logs", exist_ok=True)
    
    print("🌐 启动 Web 状态面板...")
    print("📍 访问地址: http://localhost:5000")
    print("按 Ctrl+C 停止服务\n")
    
    app.run(host="0.0.0.0", port=5000, debug=False)


if __name__ == "__main__":
    main()
