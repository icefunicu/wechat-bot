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
