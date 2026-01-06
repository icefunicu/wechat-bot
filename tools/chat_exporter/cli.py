from __future__ import annotations

import argparse
import os
from multiprocessing import freeze_support
from typing import Iterable, List, Optional

from tools.wx_db import DatabaseConnection

from .csv_exporter import CSVExporter


def is_exportable_contact(contact, include_chatrooms: bool) -> bool:
    if getattr(contact, "is_unknown", False):
        return False
    if contact.is_open_im() or contact.is_public():
        return False
    if not include_chatrooms and contact.is_chatroom():
        return False
    return True


def matches_filter(contact, filters: Optional[List[str]]) -> bool:
    if not filters:
        return True
    haystack = {
        str(contact.wxid or "").strip().lower(),
        str(contact.remark or "").strip().lower(),
        str(contact.nickname or "").strip().lower(),
        str(contact.alias or "").strip().lower(),
    }
    for term in filters:
        if str(term).strip().lower() in haystack:
            return True
    return False


def collect_contacts(database, filters: Optional[List[str]], include_chatrooms: bool):
    contacts = database.get_contacts()
    selected = []
    for contact in contacts:
        if not is_exportable_contact(contact, include_chatrooms):
            continue
        if not matches_filter(contact, filters):
            continue
        selected.append(contact)
    return selected


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export WeChat chat history to CSV (WeChatMsg format)."
    )
    parser.add_argument(
        "--db-dir",
        required=True,
        help="Decrypted WeChat DB directory, e.g. E:\\wxid_xxx\\Msg",
    )
    parser.add_argument(
        "--db-version",
        type=int,
        default=4,
        choices=[3, 4],
        help="WeChat DB version (3 or 4).",
    )
    parser.add_argument(
        "--output-dir",
        default="chat_exports",
        help="Export output directory (default: chat_exports).",
    )
    parser.add_argument(
        "--contact",
        action="append",
        help="Contact remark/nickname/wxid to export (repeatable).",
    )
    parser.add_argument(
        "--include-chatrooms",
        action="store_true",
        help="Include chatrooms in export (default: only friends).",
    )
    parser.add_argument("--start", default=None, help="Start time, e.g. 2020-01-01 00:00:00")
    parser.add_argument("--end", default=None, help="End time, e.g. 2035-03-12 00:00:00")
    return parser.parse_args()


def export_contacts(
    db_dir: str,
    db_version: int,
    output_dir: str,
    filters: Optional[List[str]],
    include_chatrooms: bool,
    time_range,
) -> None:
    if not os.path.exists(db_dir):
        raise SystemExit(f"db-dir not found: {db_dir}")
    conn = DatabaseConnection(db_dir, db_version)
    database = conn.get_interface()
    if database is None:
        raise SystemExit("db init failed: check db_dir/db_version")

    os.makedirs(output_dir, exist_ok=True)
    contacts = collect_contacts(database, filters, include_chatrooms)
    if not contacts:
        raise SystemExit("no contacts matched the filter")

    for contact in contacts:
        exporter = CSVExporter(
            database=database,
            contact=contact,
            output_dir=output_dir,
            message_types=None,
            time_range=time_range,
            group_members=None,
        )
        exporter.start()

    print(f"exported contacts: {len(contacts)}")


if __name__ == "__main__":
    freeze_support()
    args = parse_args()
    if (args.start and not args.end) or (args.end and not args.start):
        raise SystemExit("start and end must be provided together")
    time_range = [args.start, args.end] if args.start and args.end else None
    export_contacts(
        db_dir=args.db_dir,
        db_version=args.db_version,
        output_dir=args.output_dir,
        filters=args.contact,
        include_chatrooms=args.include_chatrooms,
        time_range=time_range,
    )
