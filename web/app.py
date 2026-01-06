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

from core.bot_control import get_bot_state, get_usage_tracker


app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False


# ═══════════════════════════════════════════════════════════════════════════════
#                               页面路由
# ═══════════════════════════════════════════════════════════════════════════════


@app.route("/")
def index():
    """首页仪表盘"""
    state = get_bot_state()
    state.reset_daily_stats()
    
    return render_template(
        "dashboard.html",
        state=state,
        is_paused=state.is_paused,
        uptime=state.get_uptime_str(),
        today_replies=state.today_replies,
        today_tokens=state.today_tokens,
        total_replies=state.total_replies,
    )


@app.route("/logs")
def page_logs():
    """日志查看页面"""
    return render_template("logs.html")


# ═══════════════════════════════════════════════════════════════════════════════
#                               API 路由
# ═══════════════════════════════════════════════════════════════════════════════


@app.route("/api/status")
def api_status():
    """获取机器人状态"""
    state = get_bot_state()
    state.reset_daily_stats()
    
    return jsonify({
        "is_paused": state.is_paused,
        "pause_reason": state.pause_reason,
        "uptime": state.get_uptime_str(),
        "today_replies": state.today_replies,
        "today_tokens": state.today_tokens,
        "total_replies": state.total_replies,
        "total_tokens": state.total_tokens,
    })


@app.route("/api/pause", methods=["POST"])
def api_pause():
    """暂停机器人"""
    state = get_bot_state()
    state.is_paused = True
    state.pause_reason = request.json.get("reason", "Web 控制台暂停") if request.json else "Web 控制台暂停"
    
    return jsonify({"success": True, "message": "机器人已暂停"})


@app.route("/api/resume", methods=["POST"])
def api_resume():
    """恢复机器人"""
    state = get_bot_state()
    state.is_paused = False
    state.pause_reason = ""
    
    return jsonify({"success": True, "message": "机器人已恢复"})


@app.route("/api/usage")
def api_usage():
    """获取用量统计"""
    try:
        tracker = get_usage_tracker()
        daily = tracker.get_daily_usage()
        return jsonify({
            "today": daily,
            "success": True,
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/logs")
def api_logs():
    """获取最新日志"""
    try:
        # 确定日志文件路径 (优先使用 wxauto_logs/bot.log)
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "wxauto_logs")
        log_file = os.path.join(log_dir, "bot.log")
        
        if not os.path.exists(log_file):
            return jsonify({"success": False, "error": "Log file not found"})
        
        lines_count = int(request.args.get("lines", 100))
        
        # 读取最后 N 行
        logs = []
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            # 简单的读取所有行取最后 N 行 (对于小日志文件足以)
            # 生产环境可以使用 deque(f, lines_count) 或 seek 优化
            all_lines = f.readlines()
            logs = [line.strip() for line in all_lines[-lines_count:]]
            
        return jsonify({"success": True, "logs": logs})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ═══════════════════════════════════════════════════════════════════════════════
#                               入口
# ═══════════════════════════════════════════════════════════════════════════════


def main():
    """启动 Web 服务"""
    print("🌐 启动 Web 状态面板...")
    print("📍 访问地址: http://localhost:5000")
    print("按 Ctrl+C 停止服务\n")
    
    app.run(host="0.0.0.0", port=5000, debug=False)


if __name__ == "__main__":
    main()
