"""FastAPI 依赖注入模块。

提供数据库 Session 和其他公共依赖。
"""

from collections.abc import Generator

from sqlalchemy.orm import Session

from src.core.database.database_manager import get_db_manager


def get_db() -> Generator[Session, None, None]:
    """获取数据库会话依赖（请求级生命周期）。

    Yields:
        SQLAlchemy Session，请求结束后自动提交/回滚并关闭。
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
