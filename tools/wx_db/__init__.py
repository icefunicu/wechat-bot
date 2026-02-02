# -*- coding: utf-8 -*-
"""
@File    : __init__.py.py
@Author  : Shuaikang Zhou
@Time    : 2023/1/5 0:10
@IDE     : Pycharm
@Version : Python3.10
@comment : ···
"""
try:
    from .log import logger
    from .model import Me, MessageType, Message, Person, Contact, TextMessage, ImageMessage
    from .db_main import DataBaseInterface
    from .manager_v4 import DataBaseV4
    from .manager_v3 import DataBaseV3
    _IMPORT_ERROR = None
except Exception as exc:
    logger = None
    Me = MessageType = Message = Person = Contact = TextMessage = ImageMessage = None
    DataBaseInterface = None
    DataBaseV4 = None
    DataBaseV3 = None
    _IMPORT_ERROR = exc

__version__ = '3.0.0'


class DatabaseConnection:
    def __init__(self, db_dir, db_version=4):
        self.db_dir = db_dir
        self.db_version = db_version
        self.database_interface = self._initialize_database()

    def _initialize_database(self) -> DataBaseInterface:
        if DataBaseV4 is None or DataBaseV3 is None or DataBaseInterface is None:
            if _IMPORT_ERROR:
                raise RuntimeError(str(_IMPORT_ERROR))
            raise RuntimeError("wx_db 依赖未安装")
        if self.db_version == 4:
            database0 = DataBaseV4()
        else:
            database0 = DataBaseV3()
        if database0.init_database(self.db_dir):
            return database0
        else:
            logger.error(f'数据库初始化失败, 请检查路径或数据库版本是否正确, db_dir:{self.db_dir},db_version:{self.db_version}')
            return None

    def get_interface(self) -> DataBaseInterface:
        return self._initialize_database()


"""
使用示例：
conn = DatabaseConnection(USER_DB_DIR, 4)
database: DataBaseInterface = conn.get_interface()
"""
