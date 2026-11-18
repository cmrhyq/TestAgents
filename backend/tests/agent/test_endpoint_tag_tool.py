"""Agent 侧对接口标签的消费契约。

覆盖两处：``get_space_endpoints`` 可按标签取子集（防止一次读入整空间接口）、
system prompt 注入标签分布（让模型在选工具前就知道接口怎么分组）。
"""

from __future__ import annotations

import json
from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.agent.context import SpaceSnapshot, build_system_prompt
from src.agent.modes import policy_for
from src.agent.tools.db_tools import make_db_tools
from src.data.models.base import Base
from src.data.models.endpoint import Endpoint
from src.data.models.space import Space

SPACE_ID = 9201


@pytest.fixture()
def tools(tmp_path):
    """构造带三条接口的工具集：``用户`` / ``用户管理`` / 无标签。"""
    engine = create_engine(f"sqlite:///{tmp_path / 'tools.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    with factory() as session:
        session.add(Space(id=SPACE_ID, name="工具空间", workspace_path=f"workspaces/{SPACE_ID}"))
        session.add_all(
            [
                Endpoint(
                    id=1,
                    space_id=SPACE_ID,
                    operation_id="list_users",
                    name="用户列表",
                    path="/users",
                    method="GET",
                    tags='["用户"]',
                    responses="[]",
                ),
                Endpoint(
                    id=2,
                    space_id=SPACE_ID,
                    operation_id="admin_users",
                    name="用户管理",
                    path="/admin/users",
                    method="POST",
                    tags='["用户管理", "Auth"]',
                    responses="[]",
                ),
                Endpoint(
                    id=3,
                    space_id=SPACE_ID,
                    operation_id="health",
                    name="健康检查",
                    path="/health",
                    method="GET",
                    tags="[]",
                    responses="[]",
                ),
            ]
        )
        session.commit()

    @contextmanager
    def scope():
        session: Session = factory()
        try:
            yield session
        finally:
            session.close()

    bundle = {tool.name: tool for tool in make_db_tools(SPACE_ID, scope)}
    yield bundle
    engine.dispose()


def _call(tool, payload: dict) -> list:
    """调用工具并把返回的 JSON 字符串解析为对象。"""
    return json.loads(tool.invoke(payload))


class TestEndpointListTool:
    """``get_space_endpoints`` 的标签过滤。"""

    def test_without_tag_returns_all(self, tools):
        """不传标签时行为不变，返回全部启用接口。"""
        assert len(_call(tools["get_space_endpoints"], {})) == 3

    def test_filter_by_tag(self, tools):
        """传标签只返回该标签下的接口。"""
        result = _call(tools["get_space_endpoints"], {"tag": "用户"})
        assert [item["path"] for item in result] == ["/users"]

    def test_tag_match_is_case_insensitive(self, tools):
        """标签匹配不区分大小写，模型传 auth 也能命中 Auth。"""
        result = _call(tools["get_space_endpoints"], {"tag": "auth"})
        assert [item["path"] for item in result] == ["/admin/users"]

    def test_unknown_tag_returns_empty(self, tools):
        """无匹配时返回空数组，而不是报错。"""
        assert _call(tools["get_space_endpoints"], {"tag": "不存在的标签"}) == []

    def test_tags_are_arrays(self, tools):
        """工具输出里的 tags 是数组，模型读到的不是 JSON 字符串。"""
        result = _call(tools["get_space_endpoints"], {"tag": "用户管理"})
        assert result[0]["tags"] == ["用户管理", "Auth"]

    def test_detail_tool_returns_tag_array(self, tools):
        """详情工具的 tags 同样是数组。"""
        detail = _call(tools["get_endpoint_detail_by_id"], {"endpoint_id": 2})
        assert detail["tags"] == ["用户管理", "Auth"]


class TestPromptTags:
    """system prompt 的标签分布。"""

    def _prompt(self, tag_counts) -> str:
        snapshot = SpaceSnapshot(
            space_id=SPACE_ID,
            space_name="工具空间",
            endpoint_count=3,
            tag_counts=tag_counts,
        )
        return build_system_prompt(snapshot, policy_for("agent"))

    def test_renders_tag_distribution(self):
        """有标签时渲染成「名称(数量)」形式。"""
        prompt = self._prompt([("用户管理", 2), ("鉴权", 1)])
        assert "- 接口标签分布：用户管理(2)、鉴权(1)" in prompt

    def test_omits_line_when_empty(self):
        """无标签时不渲染空行，避免噪音。"""
        assert "接口标签分布" not in self._prompt([])
