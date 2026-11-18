from collections import Counter
from collections.abc import Iterable

from sqlalchemy import ColumnElement, and_, literal, or_, select
from sqlalchemy.orm import Session

from src.data.enum.workflow import DataStatus
from src.data.models.endpoint import Endpoint
from src.data.repositories.base import BaseRepository
from src.utils.json_utils import as_str_list

# LIKE 语句的转义符，需与 SQL 中 ``ESCAPE`` 的取值保持一致
_TAG_LIKE_ESCAPE = "\\"


def _escape_like(text: str) -> str:
    """转义 LIKE 模式中的通配符，使标签按字面量匹配。

    必须先转义反斜杠再转义 ``%`` 与 ``_``，否则会二次转义。

    Args:
        text: 标签原文

    Returns:
        可直接拼进 LIKE 模式的文本
    """
    return (
        text.replace(_TAG_LIKE_ESCAPE, _TAG_LIKE_ESCAPE * 2)
        .replace("%", f"{_TAG_LIKE_ESCAPE}%")
        .replace("_", f"{_TAG_LIKE_ESCAPE}_")
    )


def _tag_pattern(tag: str) -> str:
    """构造标签精确匹配的 LIKE 模式。

    库内存的是 JSON 数组字符串（如 ``["用户","鉴权"]``）。以双引号作为边界，
    ``LIKE '%%"用户"%%'`` 就不会命中 ``"用户管理"``——这是在不具备 JSON1 扩展
    （``json_each`` 不可用）时实现精确元素匹配的办法。标签本身禁止双引号，
    因此边界不会歧义。

    Args:
        tag: 标签原文

    Returns:
        形如 ``%"用户"%`` 的 LIKE 模式
    """
    return f'%"{_escape_like(tag)}"%'


class EndpointRepository(BaseRepository[Endpoint]):
    """接口定义表数据访问。"""

    def __init__(self, session: Session) -> None:
        """绑定接口模型。

        Args:
            session: 调用方持有的会话
        """
        super().__init__(Endpoint, session)

    @staticmethod
    def tag_condition(tags: Iterable[str], match_all: bool = False) -> ColumnElement[bool] | None:
        """构造按标签过滤的查询条件。

        Args:
            tags: 标签集合；空集合返回 None，调用方应跳过该条件
            match_all: True 时要求同时带全部标签（AND），False 时命中任一即可（OR）

        Returns:
            SQLAlchemy 过滤表达式；``tags`` 为空时返回 None
        """
        conditions = [
            Endpoint.tags.like(_tag_pattern(tag), escape=_TAG_LIKE_ESCAPE) for tag in tags if tag
        ]
        if not conditions:
            return None
        return and_(*conditions) if match_all else or_(*conditions)

    def get_tag_facets(self, space_id: int) -> list[tuple[str, int]]:
        """统计空间内每个标签下的接口数量。

        SQLite 未编译 JSON1 扩展，无法在 SQL 层展开数组做 ``GROUP BY``，因此在
        Python 侧聚合。单个空间的接口数量有限（数十至数百），代价可接受。
        已删除的接口不参与统计，避免把废标签推荐给用户。

        Args:
            space_id: 空间主键

        Returns:
            ``(标签名, 接口数)`` 列表，按数量降序、标签名升序排列
        """
        stmt = select(Endpoint.tags).where(
            and_(
                Endpoint.space_id == space_id,
                Endpoint.status != DataStatus.DELETED.value,
            )
        )
        counter: Counter[str] = Counter()
        for raw in self._session.scalars(stmt).all():
            # 同一接口内的重复标签只计一次
            counter.update(set(as_str_list(raw)))
        return sorted(counter.items(), key=lambda item: (-item[1], item[0]))

    def check_duplicate(self, space_id: int, path: str, method: str) -> bool:
        """判断同一空间内是否已存在相同路径与方法的接口。

        Args:
            space_id: 空间主键
            path: 接口路径
            method: HTTP 方法，内部统一转大写后比较

        Returns:
            已存在返回 True
        """
        stmt = (
            select(literal(1))
            .select_from(Endpoint)
            .where(
                and_(
                    Endpoint.space_id == space_id,
                    Endpoint.path == path,
                    Endpoint.method == method.upper(),
                )
            )
            .limit(1)
        )
        return self._session.scalar(stmt) is not None

    def bulk_query(self, space_ids: set, paths: set, methods: set) -> list[Endpoint]:
        """按空间、路径、方法三个集合批量查询，单条 SQL 完成。

        Args:
            space_ids: 空间主键集合
            paths: 接口路径集合
            methods: HTTP 方法集合，使用调用方传入的大小写

        Returns:
            匹配的接口列表
        """
        stmt = select(Endpoint).where(
            and_(
                Endpoint.space_id.in_(space_ids),
                Endpoint.path.in_(paths),
                Endpoint.method.in_(methods),
            )
        )
        return list(self._session.scalars(stmt).all())

    def get_by_space(self, space_id: int, active_only: bool = True) -> list[Endpoint]:
        """查询空间下的接口。

        Args:
            space_id: 空间主键
            active_only: 为 True 时只返回启用状态的接口

        Returns:
            接口列表，不排序
        """
        conditions = [Endpoint.space_id == space_id]
        if active_only:
            conditions.append(Endpoint.status == DataStatus.ENABLE.value)
        stmt = select(Endpoint).where(and_(*conditions))
        return list(self._session.scalars(stmt).all())

    def find_by_identity(self, space_id: int, path: str, method: str) -> list[Endpoint]:
        """按空间、路径、方法查询全部匹配记录，供查重时排除自身。

        Args:
            space_id: 空间主键
            path: 接口路径
            method: HTTP 方法，内部统一转大写后比较

        Returns:
            匹配的接口列表
        """
        stmt = select(Endpoint).where(
            and_(
                Endpoint.space_id == space_id,
                Endpoint.path == path,
                Endpoint.method == method.upper(),
            )
        )
        return list(self._session.scalars(stmt).all())

    def get_active_by_ids(self, endpoint_ids: list[int]) -> list[Endpoint]:
        """按主键列表取启用状态的接口。

        Args:
            endpoint_ids: 接口主键列表

        Returns:
            启用的接口列表；已停用或不存在的主键被忽略
        """
        stmt = select(Endpoint).where(
            and_(
                Endpoint.id.in_(endpoint_ids),
                Endpoint.status == DataStatus.ENABLE.value,
            )
        )
        return list(self._session.scalars(stmt).all())
