"""``tests/core/llm`` 共用夹具。"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.data.models.base import Base


@pytest.fixture()
def session_scope(tmp_path):
    """临时 SQLite 库，避免统计写入真实 ``db/TestAgents.db``。"""
    engine = create_engine(f"sqlite:///{tmp_path / 'llm.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def _scope() -> Generator[Session, None, None]:
        session = factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    yield _scope
    engine.dispose()
