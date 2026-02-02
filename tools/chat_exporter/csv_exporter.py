from __future__ import annotations

import csv
import os
from typing import Callable, Optional, Set, Tuple

try:
    from wxManager.db_main import DataBaseInterface
    from wxManager.model import Contact, Me, Message, MessageType
    _IMPORT_ERROR = None
except Exception as exc:
    DataBaseInterface = None
    Contact = Me = Message = MessageType = None
    _IMPORT_ERROR = exc

CSV_COLUMNS = ["消息ID", "类型", "发送人", "时间", "内容", "备注", "昵称", "更多信息"]


def get_new_filename(filename: str) -> str:
    """Return a non-conflicting filename by appending (n) when needed."""
    if not os.path.exists(filename):
        return filename
    for i in range(1, 10086):
        base_name = os.path.basename(filename)
        name, ext = os.path.splitext(base_name)
        candidate = os.path.join(os.path.dirname(filename), f"{name}({i}){ext}")
        if not os.path.exists(candidate):
            return candidate
    return filename


def ensure_export_dirs(path: str) -> None:
    os.makedirs(path, exist_ok=True)
    for sub_dir in ("image", "emoji", "video", "voice", "file", "avatar", "music", "icon"):
        os.makedirs(os.path.join(path, sub_dir), exist_ok=True)


def _noop(*_args: object, **_kwargs: object) -> None:
    return None


class CSVExporter:
    _exporter_id = 0

    def __init__(
        self,
        database: DataBaseInterface,
        contact: Contact,
        output_dir: str,
        message_types: Optional[Set[MessageType]] = None,
        time_range: Optional[Tuple[object, object]] = None,
        group_members: Optional[Set[str]] = None,
        progress_callback: Optional[Callable[[float], None]] = None,
        finish_callback: Optional[Callable[[int], None]] = None,
    ) -> None:
        if DataBaseInterface is None:
            if _IMPORT_ERROR:
                raise RuntimeError(str(_IMPORT_ERROR))
            raise RuntimeError("wxManager 依赖未安装")
        CSVExporter._exporter_id += 1
        self.exporter_id = CSVExporter._exporter_id
        self.database = database
        self.contact = contact
        self.message_types = message_types
        self.time_range = time_range
        self.group_members = group_members
        self.update_progress_callback = progress_callback or _noop
        self.finish_callback = finish_callback or _noop
        self.origin_path = os.path.join(
            output_dir, "聊天记录", f"{self.contact.remark}({self.contact.wxid})"
        )
        ensure_export_dirs(self.origin_path)
        self.group_contacts = self._init_group_contacts()

    def _init_group_contacts(self) -> dict[str, Contact]:
        if self.contact.is_chatroom():
            contacts = self.database.get_chatroom_members(self.contact.wxid) or {}
            contacts[Me().wxid] = Me()
            return contacts
        return {Me().wxid: Me(), self.contact.wxid: self.contact}

    def _is_select_by_type(self, message: Message) -> bool:
        if not self.message_types:
            return True
        return message.type in self.message_types

    def _is_select_by_contact(self, message: Message) -> bool:
        if self.contact.is_chatroom() and self.group_members:
            return message.sender_id in self.group_members
        return True

    def is_selected(self, message: Message) -> bool:
        return self._is_select_by_type(message) and self._is_select_by_contact(message)

    def message_to_list(self, message: Message) -> list[str]:
        remark = message.display_name
        nickname = message.display_name
        if self.contact.is_chatroom():
            contact = self.group_contacts.get(message.sender_id)
            if contact:
                remark = contact.remark
                nickname = contact.nickname
        else:
            contact = Me() if message.is_sender else self.contact
            remark = contact.remark
            nickname = contact.nickname
        return [
            str(message.server_id),
            message.type_name(),
            message.display_name,
            message.str_time,
            message.to_text(),
            remark,
            nickname,
            "more",
        ]

    def export(self) -> str:
        print(f"【开始导出 CSV {self.contact.remark}】")
        os.makedirs(self.origin_path, exist_ok=True)
        filename = os.path.join(self.origin_path, f"{self.contact.remark}.csv")
        filename = get_new_filename(filename)
        messages = self.database.get_messages(self.contact.wxid, time_range=self.time_range)
        total_steps = len(messages)
        with open(filename, mode="w", newline="", encoding="utf-8-sig") as file:
            writer = csv.writer(file)
            writer.writerow(CSV_COLUMNS)
            # Optimize: Write row by row to save memory
            for index, message in enumerate(messages):
                if total_steps and index and index % 1000 == 0:
                    self.update_progress_callback(index / total_steps)
                if not self.is_selected(message):
                    continue
                writer.writerow(self.message_to_list(message))
        self.update_progress_callback(1.0)
        self.finish_callback(self.exporter_id)
        print(f"【完成导出 CSV {self.contact.remark}】")
        return filename

    def start(self) -> str:
        return self.export()
