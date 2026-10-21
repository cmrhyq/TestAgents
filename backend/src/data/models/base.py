from datetime import datetime

from sqlalchemy.orm import DeclarativeBase


def local_now() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]


class Base(DeclarativeBase):
    """所有模型的声明性基类"""

    pass
