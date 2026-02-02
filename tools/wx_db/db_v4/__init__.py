#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
@Time        : 2024/12/5 22:46 
@Author      : SiYuan 
@Email       : 863909694@qq.com 
@File        : MemoTrace-__init__.py.py 
@Description : 
"""

try:
    from .message import MessageDB
    from .contact import ContactDB
    from .session import SessionDB
    from .head_image import HeadImageDB
    from .hardlink import HardLinkDB
    _IMPORT_ERROR = None
except Exception as exc:
    MessageDB = ContactDB = SessionDB = HeadImageDB = HardLinkDB = None
    _IMPORT_ERROR = exc

if __name__ == '__main__':
    pass
