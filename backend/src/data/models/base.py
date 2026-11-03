from datetime import datetime

from sqlalchemy.orm import DeclarativeBase


def local_now() -> str:
    """当前本地时间的字符串表示，用作时间列默认值。

    时间列统一为 ``Text``，格式 ``YYYY-MM-DDTHH:MM:SS.mmm``，可直接按字符串排序与比较。

    Returns:
        毫秒精度的本地时间字符串
    """
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]


class Base(DeclarativeBase):
    """所有 ORM 模型的声明性基类。"""

    pass
