import json
import os
import time
import uuid
import logging
from collections import deque
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class IPCManager:
    """进程间通信管理器 (基于文件)"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.cmd_file = os.path.join(data_dir, "commands.json")
        self.msg_file = os.path.join(data_dir, "chat_history.jsonl")
        os.makedirs(data_dir, exist_ok=True)
        
    # ══════════════════════════════════════════════════════════════════════
    #                               命令处理
    # ══════════════════════════════════════════════════════════════════════
    
    def send_command(self, cmd_type: str, data: Dict) -> str:
        """(Web端) 发送命令"""
        cmd_id = str(uuid.uuid4())
        command = {
            "id": cmd_id,
            "timestamp": time.time(),
            "type": cmd_type,
            "data": data
        }
        
        # 读取现有命令 (简单文件锁机制: 重试)
        for _ in range(3):
            try:
                commands = []
                if os.path.exists(self.cmd_file):
                    with open(self.cmd_file, "r", encoding="utf-8") as f:
                        try:
                            commands = json.load(f)
                            if not isinstance(commands, list): commands = []
                        except: commands = []
                
                commands.append(command)
                
                with open(self.cmd_file, "w", encoding="utf-8") as f:
                    json.dump(commands, f, ensure_ascii=False)
                return cmd_id
            except PermissionError:
                time.sleep(0.1)
        return ""

    def get_commands(self) -> List[Dict]:
        """(Bot端) 获取并清除命令"""
        if not os.path.exists(self.cmd_file):
            return []
            
        try:
            with open(self.cmd_file, "r", encoding="utf-8") as f:
                try:
                    commands = json.load(f)
                except: return []
            
            if not commands:
                return []
                
            # 清空命令文件
            with open(self.cmd_file, "w", encoding="utf-8") as f:
                json.dump([], f)
                
            return commands
        except Exception as e:
            print(f"IPC Error: {e}")
            return []

    # ══════════════════════════════════════════════════════════════════════
    #                               消息记录
    # ══════════════════════════════════════════════════════════════════════

    def log_message(self, sender: str, content: str, msg_type: str = "incoming", recipient: str = ""):
        """(Bot端) 记录每一条消息"""
        entry = {
            "id": str(uuid.uuid4()),
            "timestamp": time.time(),
            "sender": sender,
            "recipient": recipient,
            "type": msg_type, # incoming / outgoing / system
            "content": content
        }
        
        try:
            with open(self.msg_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"写入 IPC 消息失败: {e}")

    def get_recent_messages(self, limit: int = 50) -> List[Dict]:
        """(Web端) 获取最近消息"""
        messages = []
        if not os.path.exists(self.msg_file):
            return []
            
        try:
            with open(self.msg_file, "r", encoding="utf-8") as f:
                # 使用 deque 高效读取最后 N 行，避免读取整个文件
                last_lines = deque(f, maxlen=limit)
                for line in last_lines:
                    try:
                        messages.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
            return messages
        except Exception as e:
            logger.error(f"读取最近消息失败: {e}")
            return []
