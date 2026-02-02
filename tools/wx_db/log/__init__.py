#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
@Time        : 2025/1/7 21:44 
@Author      : SiYuan 
@Email       : 863909694@qq.com 
@File        : MemoTrace-__init__.py.py 
@Description : 
"""

try:
    from wxManager.log.logger import log, logger
    _IMPORT_ERROR = None
except Exception as exc:
    log = None
    logger = None
    _IMPORT_ERROR = exc

__all__ = ["logger", "log"]
