from sqlalchemy import or_
from sqlalchemy.orm import Session

from src.core.config import get_backend_root
from src.core.errors import ConflictError, NotFoundError
from src.core.logging import get_logger
from src.data.models.space import Space
from src.data.repositories import SpaceRepository
from src.data.schemas.space import SpaceCreate
from src.data.services.base_service import BaseService
from src.workspace.manager import get_workspace_manager

logger = get_logger(__name__)


class SpaceService(BaseService[Space, SpaceRepository]):
    """空间业务逻辑。

    空间的数据库记录与工作区目录需保持一致：建库后立刻建目录，删库后归档目录。
    """

    def __init__(self, session: Session):
        """绑定会话与空间仓储。

        Args:
            session: 调用方持有的会话
        """
        super().__init__(session, SpaceRepository(session))

    def create_space(self, data: SpaceCreate) -> Space:
        """创建空间并同步创建工作区目录与初始文件。

        必须先落库拿到 ID 再建目录，因为 ID 由客户端 ``next_id`` 生成，
        ``flush`` 后即可使用。建目录失败会向上抛出，由 ``get_db`` 回滚事务，
        避免出现库中有记录而磁盘无目录的状态。

        副作用：写库（未提交）、写磁盘目录。

        Args:
            data: 空间创建参数

        Returns:
            已写入 ``workspace_path`` 的空间实体

        Raises:
            ConflictError: 同名空间已存在
        """
        if self.repo.get_by_name(data.name) is not None:
            raise ConflictError(f"空间名称已存在: {data.name}")

        space = self.create(Space(**data.model_dump()))
        space.workspace_path = self._workspace_path(space.id)
        self._session.flush()

        get_workspace_manager().create(space.id, space.name)
        logger.info("空间已创建", space_id=str(space.id), name=space.name)
        return space

    def list_spaces(self, keyword: str | None, status: int | None, page: int, page_size: int):
        """按名称/描述关键字与状态分页查询空间。

        Args:
            keyword: 模糊匹配名称与描述；空值表示不过滤
            status: 状态过滤；None 表示不过滤
            page: 页码，从 1 开始
            page_size: 每页条数

        Returns:
            当前页空间列表与总数
        """
        filters = []
        if status is not None:
            filters.append(Space.status == status)
        if keyword:
            pattern = f"%{keyword}%"
            filters.append(or_(Space.name.ilike(pattern), Space.description.ilike(pattern)))
        return self.list(page, page_size, *filters)

    def update_space(self, space_id: int, fields: dict) -> Space:
        """局部更新空间，改名时校验同名冲突。

        副作用：写库（未提交）、必要时补建缺失的工作区目录。

        Args:
            space_id: 空间主键
            fields: 待更新字段

        Returns:
            更新后的空间

        Raises:
            ConflictError: 新名称已被其他空间占用
            NotFoundError: 空间不存在
        """
        if "name" in fields:
            existing = self.repo.get_by_name(fields["name"])
            if existing is not None and existing.id != space_id:
                raise ConflictError(f"空间名称已存在: {fields['name']}")
        space = self.update(space_id, **fields)
        # 目录可能被手工删除或来自其他副本，更新时补齐
        get_workspace_manager().ensure(space.id)
        return space

    def delete_space(self, space_id: int) -> None:
        """删除空间记录并归档工作区目录。

        目录只重命名为 ``.deleted-{ts}``，不物理删除，保留恢复窗口；若事务随后回滚，
        目录由 ``ensure()`` 在下次访问时重建骨架。

        副作用：写库（未提交）、重命名磁盘目录。

        Args:
            space_id: 空间主键

        Raises:
            NotFoundError: 空间不存在
        """
        if not self.repo.delete_cascade(space_id):
            raise NotFoundError("空间不存在")
        self._session.flush()
        get_workspace_manager().archive(space_id)

    def get_space(self, space_id: int) -> Space | None:
        """按主键取空间。

        Args:
            space_id: 空间主键

        Returns:
            空间实体；不存在时返回 None
        """
        return self.get(space_id)

    # 内部方法

    @staticmethod
    def _workspace_path(space_id: int) -> str:
        """计算入库用的工作区路径。

        优先返回相对 backend 根的 POSIX 路径；目录不在根下时回退为绝对路径。

        Args:
            space_id: 空间主键

        Returns:
            入库用的路径字符串
        """
        space_dir = get_workspace_manager().space_dir(space_id)
        try:
            return space_dir.resolve().relative_to(get_backend_root()).as_posix()
        except ValueError:
            return str(space_dir)
