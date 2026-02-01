from __future__ import annotations

import asyncio
import os
import sys

# 将项目根目录加入模块搜索路径，确保可以直接运行此文件
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from app.bot import WeChatBot


async def main():
    config_path = os.path.join(base_dir, "app", "config.py")
    bot = WeChatBot(config_path)
    await bot.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
