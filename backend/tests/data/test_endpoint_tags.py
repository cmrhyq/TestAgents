"""接口标签的存取与过滤契约。

覆盖三件事：写入时结构字段统一序列化为 JSON 字符串、标签过滤具备精确语义
（``用户`` 不得命中 ``用户管理``）、标签聚合只统计未删除接口。
"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.data.enum.workflow import DataStatus
from src.data.models.base import Base
from src.data.models.space import Space
from src.data.repositories.endpoint_repository import EndpointRepository, _tag_pattern
from src.data.schemas.endpoint import EndpointCreate
from src.data.services.endpoint_service import EndpointService

SPACE_ID = 9001


@pytest.fixture()
def session(tmp_path):
    """建临时库并预置一个空间。"""
    engine = create_engine(f"sqlite:///{tmp_path / 'tags.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as s:
        s.add(Space(id=SPACE_ID, name="标签空间", workspace_path=f"workspaces/{SPACE_ID}"))
        s.commit()

    s = factory()
    try:
        yield s
    finally:
        s.close()
        engine.dispose()


def _make(service: EndpointService, path: str, tags, method: str = "GET") -> None:
    """按给定标签创建一条接口，方法名即路径末段，便于断言。"""
    service.create_one(
        EndpointCreate(
            space_id=SPACE_ID,
            operation_id=path.strip("/").replace("/", "_") or "root",
            name=path,
            path=path,
            method=method,
            tags=tags,
        )
    )


class TestWrite:
    """写入侧：归一化与序列化。"""

    def test_tags_stored_as_json_string(self, session):
        """落库形态必须是 JSON 数组字符串，读出来才是数组。"""
        service = EndpointService(session)
        _make(service, "/a", ["用户", "鉴权"])
        session.commit()

        endpoints = service.list_active(SPACE_ID)
        assert json.loads(endpoints[0].tags) == ["用户", "鉴权"]

    def test_tags_normalized_on_create(self, session):
        """去首尾空白、去空项、不区分大小写去重，保留首次出现的写法。"""
        service = EndpointService(session)
        _make(service, "/a", [" 用户 ", "用户", "", "Auth", "auth"])
        session.commit()

        assert json.loads(service.list_active(SPACE_ID)[0].tags) == ["用户", "Auth"]

    def test_batch_create_serializes_and_uppercases(self, session):
        """批量创建与小批量走同一套序列化，method 一并转大写。"""
        service = EndpointService(session)
        created = service.create_endpoint(
            [
                EndpointCreate(
                    space_id=SPACE_ID,
                    operation_id="op1",
                    name="批量一",
                    path="/batch/one",
                    method="post",
                    tags=["批量"],
                )
            ]
        )
        session.commit()

        assert len(created) == 1
        assert created[0].method == "POST"
        assert json.loads(created[0].tags) == ["批量"]

    def test_update_tags(self, session):
        """更新标签同样序列化，且不影响未提交的字段。"""
        service = EndpointService(session)
        _make(service, "/a", ["旧"])
        session.commit()
        endpoint_id = service.list_active(SPACE_ID)[0].id

        service.update_endpoint(endpoint_id, {"tags": ["新", "标签"]})
        session.commit()

        assert json.loads(service.get_or_raise(endpoint_id, "x").tags) == ["新", "标签"]


class TestTagFilter:
    """标签过滤：精确匹配与通配符转义。"""

    def test_exact_match_does_not_hit_prefix(self, session):
        """``用户`` 不能命中 ``用户管理``——这是引号边界方案的核心断言。"""
        service = EndpointService(session)
        _make(service, "/exact", ["用户"])
        _make(service, "/super", ["用户管理"])
        _make(service, "/reverse", ["管理用户"])
        session.commit()

        items, total = service.list_endpoints(SPACE_ID, None, None, 1, 20, tags=["用户"])
        assert total == 1
        assert items[0].path == "/exact"

    def test_any_and_all_modes(self, session):
        """any 命中任一标签，all 要求全部命中。"""
        service = EndpointService(session)
        _make(service, "/both", ["用户", "鉴权"])
        _make(service, "/only-user", ["用户"])
        _make(service, "/only-auth", ["鉴权"])
        session.commit()

        _, any_total = service.list_endpoints(SPACE_ID, None, None, 1, 20, tags=["用户", "鉴权"])
        assert any_total == 3

        items, all_total = service.list_endpoints(
            SPACE_ID, None, None, 1, 20, tags=["用户", "鉴权"], tags_mode="all"
        )
        assert all_total == 1
        assert items[0].path == "/both"

    def test_wildcard_is_escaped(self, session):
        """标签里的 ``%`` 按字面量匹配，不能当通配符。"""
        service = EndpointService(session)
        _make(service, "/percent", ["a%b"])
        _make(service, "/plain", ["axb"])
        session.commit()

        items, total = service.list_endpoints(SPACE_ID, None, None, 1, 20, tags=["a%b"])
        assert total == 1
        assert items[0].path == "/percent"

    def test_keyword_covers_tags(self, session):
        """关键字搜索要能命中标签，否则用户搜标签名会得到空结果。"""
        service = EndpointService(session)
        _make(service, "/a", ["风控校验"])
        _make(service, "/b", ["其他"])
        session.commit()

        _, total = service.list_endpoints(SPACE_ID, None, "风控", 1, 20)
        assert total == 1

    def test_empty_tags_means_no_filter(self, session):
        """空标签集合不产生过滤条件。"""
        service = EndpointService(session)
        _make(service, "/a", ["x"])
        _make(service, "/b", [])
        session.commit()

        assert EndpointRepository.tag_condition([]) is None
        _, total = service.list_endpoints(SPACE_ID, None, None, 1, 20, tags=[])
        assert total == 2

    def test_tag_pattern_shape(self):
        """模式必须是 ``%"标签"%``，否则精确语义不成立。"""
        assert _tag_pattern("用户") == '%"用户"%'
        assert _tag_pattern("100%") == '%"100\\%"%'


class TestTagFacets:
    """标签聚合。"""

    def test_counts_and_order(self, session):
        """按接口数降序、同名升序，同一接口内的重复标签只计一次。"""
        service = EndpointService(session)
        _make(service, "/a", ["用户", "用户", "鉴权"])
        _make(service, "/b", ["用户"])
        _make(service, "/c", ["订单"])
        session.commit()

        assert service.list_tag_facets(SPACE_ID) == [("用户", 2), ("订单", 1), ("鉴权", 1)]

    def test_deleted_endpoints_excluded(self, session):
        """已删除接口不参与统计，避免把废标签推荐给用户。"""
        service = EndpointService(session)
        _make(service, "/a", ["有效"])
        _make(service, "/b", ["废弃"])
        session.commit()

        deleted = next(ep for ep in service.list_active(SPACE_ID) if ep.path == "/b")
        service.update_endpoint(deleted.id, {"status": DataStatus.DELETED.value})
        session.commit()

        assert service.list_tag_facets(SPACE_ID) == [("有效", 1)]

    def test_scoped_to_space(self, session):
        """聚合按空间隔离，不串空间。"""
        session.add(Space(id=SPACE_ID + 1, name="另一个空间", workspace_path="workspaces/x"))
        session.commit()

        EndpointService(session).create_one(
            EndpointCreate(
                space_id=SPACE_ID + 1,
                operation_id="other",
                name="别家接口",
                path="/other",
                method="GET",
                tags=["别家标签"],
            )
        )
        session.commit()

        assert EndpointService(session).list_tag_facets(SPACE_ID) == []
