"""用量统计 API 测试。

重点验证「成本未知」不会被伪装成 0：``cost_usd`` 只累加有定价的调用，
``unpriced_calls`` 单独暴露未计价次数。
"""

from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.api.deps import get_db
from src.data.models.base import Base
from src.data.models.llm_log import LLMLog

SPACE_ID = 5001
OTHER_SPACE = 5002
CONVERSATION_ID = 6001


def _ago(days: int = 0, minutes: int = 0) -> str:
    return (datetime.now() - timedelta(days=days, minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]


@pytest.fixture()
def session_factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'usage_api.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield factory
    engine.dispose()


@pytest.fixture()
def client(session_factory) -> Generator[TestClient, None, None]:
    from app import app

    def _get_db() -> Generator[Session, None, None]:
        session = session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    app.dependency_overrides[get_db] = _get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)


def _log(
    session_factory,
    *,
    model: str = "zai/glm-4-flash",
    tokens: int = 100,
    cost: float | None = None,
    space_id: int | None = SPACE_ID,
    conversation_id: int | None = CONVERSATION_ID,
    tier: str = "SIMPLE",
    success: int = 1,
    created_at: str | None = None,
) -> None:
    with session_factory() as session:
        session.add(
            LLMLog(
                model_name=model,
                request_type="tools",
                prompt_tokens=tokens,
                completion_tokens=0,
                total_tokens=tokens,
                space_id=space_id,
                conversation_id=conversation_id,
                routing_tier=tier,
                cost_usd=cost,
                success=success,
                created_at=created_at or _ago(),
            )
        )
        session.commit()


class TestEmpty:
    def test_returns_zeros(self, client):
        body = client.get("/api/v1/usage/stats").json()
        assert body["total_calls"] == 0
        assert body["total_tokens"] == 0
        assert body["cost_usd"] is None
        assert body["unpriced_calls"] == 0
        assert body["by_model"] == []


class TestAggregation:
    def test_sums_tokens_and_calls(self, client, session_factory):
        _log(session_factory, tokens=100)
        _log(session_factory, tokens=250)

        body = client.get("/api/v1/usage/stats").json()

        assert body["total_calls"] == 2
        assert body["total_tokens"] == 350
        assert body["prompt_tokens"] == 350

    def test_counts_failures(self, client, session_factory):
        _log(session_factory, success=1)
        _log(session_factory, success=0)

        body = client.get("/api/v1/usage/stats").json()

        assert body["failed_calls"] == 1

    def test_cost_unknown_is_not_zero(self, client, session_factory):
        """全部未计价：cost_usd 必须是 null，unpriced_calls 等于总调用数。"""
        _log(session_factory)
        _log(session_factory)

        body = client.get("/api/v1/usage/stats").json()

        assert body["cost_usd"] is None
        assert body["unpriced_calls"] == 2

    def test_cost_sums_only_priced_calls(self, client, session_factory):
        """混合场景：cost 只累加有值的，unpriced 单独计数。"""
        _log(session_factory, cost=0.001)
        _log(session_factory, cost=0.002)
        _log(session_factory, cost=None)

        body = client.get("/api/v1/usage/stats").json()

        assert body["cost_usd"] == pytest.approx(0.003)
        assert body["unpriced_calls"] == 1
        assert body["total_calls"] == 3


class TestFiltering:
    def test_filter_by_space(self, client, session_factory):
        _log(session_factory, tokens=100, space_id=SPACE_ID)
        _log(session_factory, tokens=900, space_id=OTHER_SPACE)

        body = client.get(f"/api/v1/usage/stats?space_id={SPACE_ID}").json()

        assert body["total_calls"] == 1
        assert body["total_tokens"] == 100
        assert body["space_id"] == str(SPACE_ID)

    def test_filter_by_conversation(self, client, session_factory):
        _log(session_factory, tokens=100, conversation_id=CONVERSATION_ID)
        _log(session_factory, tokens=900, conversation_id=None)

        body = client.get(f"/api/v1/usage/stats?conversation_id={CONVERSATION_ID}").json()

        assert body["total_calls"] == 1
        assert body["total_tokens"] == 100

    def test_window_excludes_old_rows(self, client, session_factory):
        _log(session_factory, tokens=100, created_at=_ago(days=1))
        _log(session_factory, tokens=900, created_at=_ago(days=40))

        body = client.get("/api/v1/usage/stats?days=7").json()

        assert body["total_calls"] == 1
        assert body["total_tokens"] == 100

    def test_rejects_invalid_days(self, client):
        assert client.get("/api/v1/usage/stats?days=0").status_code == 422
        assert client.get("/api/v1/usage/stats?days=999").status_code == 422


class TestGrouping:
    def test_by_model(self, client, session_factory):
        _log(session_factory, model="zai/glm-4-flash", tokens=100)
        _log(session_factory, model="zai/glm-4-flash", tokens=100)
        _log(session_factory, model="deepseek/deepseek-v4-flash", tokens=50, cost=0.01)

        body = client.get("/api/v1/usage/stats").json()
        groups = {row["key"]: row for row in body["by_model"]}

        assert groups["zai/glm-4-flash"]["calls"] == 2
        assert groups["zai/glm-4-flash"]["cost_usd"] is None
        assert groups["zai/glm-4-flash"]["unpriced_calls"] == 2
        assert groups["deepseek/deepseek-v4-flash"]["cost_usd"] == pytest.approx(0.01)

    def test_by_tier(self, client, session_factory):
        _log(session_factory, tier="SIMPLE")
        _log(session_factory, tier="REASONING")

        body = client.get("/api/v1/usage/stats").json()
        assert {row["key"] for row in body["by_tier"]} == {"SIMPLE", "REASONING"}

    def test_empty_tier_is_skipped(self, client, session_factory):
        """非路由模型的调用没有档位，不应出现一个空的 ``unknown`` 桶。"""
        _log(session_factory, tier="")

        body = client.get("/api/v1/usage/stats").json()
        assert body["by_tier"] == []
