#!/usr/bin/env python3
"""
微信机器人环境自检脚本。

运行方式:
    python check.py

功能:
    - 检测 Python 版本
    - 检测依赖安装
    - 检测 API 配置
    - 检测微信连接
    - 提供修复建议
"""

import os
import sys
from typing import List, Tuple

# 项目根目录（bot 目录的父目录）
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 添加到 Python 路径
sys.path.insert(0, PROJECT_ROOT)

# ═══════════════════════════════════════════════════════════════════════════════
#                               检测项
# ═══════════════════════════════════════════════════════════════════════════════


def check_python_version() -> Tuple[bool, str]:
    """检查 Python 版本"""
    version = sys.version_info
    version_str = f"{version.major}.{version.minor}.{version.micro}"
    if version >= (3, 8):
        return True, f"Python {version_str}"
    return False, f"Python {version_str}（需要 3.8+）"


def check_dependencies() -> Tuple[bool, str, List[str]]:
    """检查依赖安装"""
    required = ["httpx", "openai"]
    optional = ["wxauto"]
    missing = []
    installed = []
    
    for pkg in required:
        try:
            __import__(pkg)
            installed.append(pkg)
        except ImportError:
            missing.append(pkg)
    
    for pkg in optional:
        try:
            __import__(pkg)
            installed.append(pkg)
        except ImportError:
            pass  # 可选依赖不算缺失
    
    if missing:
        return False, f"缺少: {', '.join(missing)}", missing
    return True, f"已安装: {', '.join(installed)}", []


def check_wxauto() -> Tuple[bool, str]:
    """检查 wxauto 模块"""
    try:
        from wxauto import WeChat
        return True, "wxauto 可用"
    except ImportError:
        return False, "wxauto 未安装"
    except Exception as e:
        return False, f"wxauto 导入失败: {e}"


def check_wechat_connection() -> Tuple[bool, str]:
    """检查微信连接"""
    try:
        from wxauto import WeChat
        wx = WeChat()
        return True, "微信连接正常"
    except ImportError:
        return None, "跳过（wxauto 未安装）"
    except Exception as e:
        error_msg = str(e)
        if "找不到微信" in error_msg or "WeChat" in error_msg:
            return False, "未检测到微信客户端"
        return False, f"连接失败: {error_msg[:50]}"


def check_api_config() -> Tuple[bool, str, int]:
    """检查 API 配置"""
    config_path = os.path.join(PROJECT_ROOT, "backend", "config.py")
    if not os.path.exists(config_path):
        # Fallback to check app/config.py just in case
        config_path = os.path.join(PROJECT_ROOT, "app", "config.py")
        if not os.path.exists(config_path):
            return False, "config.py 不存在", 0
    
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("config", config_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        config = getattr(module, "CONFIG", {})
    except Exception as e:
        return False, f"配置加载失败: {e}", 0
    
    api_cfg = config.get("api", {})
    presets = api_cfg.get("presets", [])
    
    # 统计有效预设数量
    valid_count = 0
    for preset in presets:
        if not isinstance(preset, dict):
            continue
        api_key = preset.get("api_key", "")
        if api_key and not api_key.upper().startswith("YOUR_"):
            valid_count += 1
    
    # 检查 data/api_keys.py 中的密钥
    api_keys_path = os.path.join(PROJECT_ROOT, "data", "api_keys.py")
    if os.path.exists(api_keys_path):
        try:
            from data.api_keys import API_KEYS
            if isinstance(API_KEYS, dict):
                default_key = API_KEYS.get("default", "")
                if default_key and not default_key.upper().startswith("YOUR_"):
                    valid_count = max(valid_count, 1)
                preset_keys = API_KEYS.get("presets", {})
                if isinstance(preset_keys, dict):
                    for key in preset_keys.values():
                        if key and not str(key).upper().startswith("YOUR_"):
                            valid_count += 1
        except Exception:
            pass
    
    if valid_count > 0:
        return True, f"检测到 {valid_count} 个有效预设", valid_count
    return False, "未配置有效的 API 密钥", 0


def check_whitelist() -> Tuple[bool, str]:
    """检查白名单配置"""
    config_path = os.path.join(PROJECT_ROOT, "app", "config.py")
    if not os.path.exists(config_path):
        return None, "跳过"
    
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("config", config_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        config = getattr(module, "CONFIG", {})
    except Exception:
        return None, "跳过"
    
    bot_cfg = config.get("bot", {})
    whitelist_enabled = bot_cfg.get("whitelist_enabled", False)
    whitelist = bot_cfg.get("whitelist", [])
    
    if not whitelist_enabled:
        return None, "未启用（将回复所有消息）"
    
    if whitelist:
        return True, f"已配置 {len(whitelist)} 个白名单"
    return False, "已启用但列表为空"


# ═══════════════════════════════════════════════════════════════════════════════
#                               主程序
# ═══════════════════════════════════════════════════════════════════════════════


def main():
    """运行自检"""
    print()
    print("🔍 微信机器人环境检测")
    print("━" * 50)
    print()
    
    issues = []
    suggestions = []
    
    # 检查 Python 版本
    ok, msg = check_python_version()
    icon = "✅" if ok else "❌"
    print(f"{icon} Python 版本: {msg}")
    if not ok:
        issues.append("Python 版本过低")
        suggestions.append("请升级到 Python 3.8 或更高版本")
    
    # 检查依赖
    ok, msg, missing = check_dependencies()
    icon = "✅" if ok else "❌"
    print(f"{icon} 依赖安装: {msg}")
    if not ok:
        issues.append("缺少必要依赖")
        suggestions.append(f"运行: pip install {' '.join(missing)}")
    
    # 检查 wxauto
    ok, msg = check_wxauto()
    icon = "✅" if ok else "❌"
    print(f"{icon} wxauto: {msg}")
    if not ok:
        issues.append("wxauto 不可用")
        suggestions.append("运行: pip install wxauto")
    
    # 检查微信连接
    result, msg = check_wechat_connection()
    if result is None:
        icon = "⚠️"
    else:
        icon = "✅" if result else "❌"
    print(f"{icon} 微信连接: {msg}")
    if result is False:
        issues.append("微信连接失败")
        suggestions.append("确保微信 PC 版 3.9.x 已登录并运行")
        suggestions.append("4.x 版本不支持，请到 https://pc.weixin.qq.com 下载 3.9.x")
    
    # 检查 API 配置
    ok, msg, count = check_api_config()
    icon = "✅" if ok else "❌"
    print(f"{icon} API 配置: {msg}")
    if not ok:
        issues.append("API 未配置")
        suggestions.append("运行: python run.py setup")
    
    # 检查白名单
    result, msg = check_whitelist()
    if result is None:
        icon = "⚠️"
    else:
        icon = "✅" if result else "❌"
    print(f"{icon} 白名单: {msg}")
    
    # 总结
    print()
    print("━" * 50)
    
    if not issues:
        print("🎉 所有检测通过！可以运行: python run.py")
    else:
        print(f"❗ 发现 {len(issues)} 个问题:")
        for issue in issues:
            print(f"   • {issue}")
        
        if suggestions:
            print()
            print("📋 建议操作:")
            for suggestion in suggestions:
                print(f"   • {suggestion}")
    
    print()
    return 0 if not issues else 1


if __name__ == "__main__":
    sys.exit(main())
