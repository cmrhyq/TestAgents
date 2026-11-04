"""FastAPI 公共依赖。

当前仅提供请求级数据库 Session。
"""

from collections.abc import Generator

from sqlalchemy.orm import Session

from src.core.database.database_manager import get_db_manager


def get_db() -> Generator[Session, None, None]:
    """提供请求级数据库 Session 依赖。

    Yields:
        会话对象；请求正常结束时提交，抛异常时回滚，最终关闭。
    """
    manager = get_db_manager()
    session = manager.create_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
