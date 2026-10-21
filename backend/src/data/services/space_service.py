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
    def __init__(self, session: Session):
        super().__init__(session, SpaceRepository(session))

    def create_space(self, data: SpaceCreate) -> Space:
        """创建空间，并同步落地工作目录与初始文件。

        顺序很关键：先落库拿到雪花 ID，再用 ID 建目录。
        ID 是客户端生成的（``next_id``），``flush`` 后即可用，无需等 commit。

        目录创建失败会向上抛，让 ``get_db`` 回滚事务——不允许出现
        「数据库有空间、磁盘没目录」的半残状态。
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
        filters = []
        if status is not None:
            filters.append(Space.status == status)
        if keyword:
            pattern = f"%{keyword}%"
            filters.append(or_(Space.name.ilike(pattern), Space.description.ilike(pattern)))
        return self.list(page, page_size, *filters)

    def update_space(self, space_id: int, fields: dict) -> Space:
        if "name" in fields:
            existing = self.repo.get_by_name(fields["name"])
            if existing is not None and existing.id != space_id:
                raise ConflictError(f"空间名称已存在: {fields['name']}")
        space = self.update(space_id, **fields)
        # 目录缺失时补建（例如手工删过、或从别处恢复的库）
        get_workspace_manager().ensure(space.id)
        return space

    def delete_space(self, space_id: int) -> None:
        """删除空间：先删库，再归档工作目录。

        目录只改名不物理删（``.deleted-{ts}``），给误删留可恢复窗口。
        若随后事务回滚，空间仍在、目录在归档处——下次访问会由
        ``ensure()`` 重建空骨架，文件本身没丢。
        """
        if not self.repo.delete_cascade(space_id):
            raise NotFoundError("空间不存在")
        self._session.flush()
        get_workspace_manager().archive(space_id)

    def get_space(self, space_id: int) -> Space | None:
        return self.get(space_id)

    # ─── 内部 ────────────────────────────────────────────────────────────

    @staticmethod
    def _workspace_path(space_id: int) -> str:
        """计算入库用的相对路径（相对 backend 根；不在根下时退回绝对路径）。"""
        space_dir = get_workspace_manager().space_dir(space_id)
        try:
            return space_dir.resolve().relative_to(get_backend_root()).as_posix()
        except ValueError:
            return str(space_dir)
