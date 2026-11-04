"""空间工作目录管理。

一个空间对应 ``workspaces/{space_id}/`` 目录，同时是 Agent 的文件沙箱、
测试资产落地处与空间级约定（``AGENTS.md``）的载体。

安全边界是本模块的核心职责：``resolve()`` 是把外部相对路径转为真实路径的唯一入口，
越界一律抛 ``PathEscapeError``。
"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from src.core.config import resolve_backend_path
from src.core.logging import get_logger
from src.workspace import templates

logger = get_logger(__name__)

# 目录树与文件遍历时跳过的噪音目录
_SKIP_DIRS = frozenset({"__pycache__", ".git", ".idea", ".mypy_cache", ".pytest_cache", ".ruff_cache", "node_modules"})

# 归档目录前缀：删除空间时只改名保留现场
_ARCHIVE_PREFIX = ".deleted-"


class PathEscapeError(ValueError):
    """路径越出空间工作目录。"""


class WorkspaceManager:
    """空间工作目录的创建、解析、归档与遍历。

    Args:
        root: 工作目录根。默认取配置 ``workspace.root``（相对 backend 根），
            测试时可直接传 ``tmp_path`` 下的目录。
    """

    def __init__(self, root: str | Path | None = None) -> None:
        if root is None:
            from src.core.config import get_config

            root = resolve_backend_path(get_config().workspace.root)
        self.root = Path(root).resolve()

    # ─── 路径 ────────────────────────────────────────────────────────────

    def space_dir(self, space_id: int | str) -> Path:
        """空间目录路径（不保证存在）。"""
        return self.root / str(space_id)

    def resolve(self, space_id: int | str, relative: str) -> Path:
        """把相对路径解析成空间内的绝对路径，越界即拒绝。

        沙箱唯一入口：文件工具与知识库上传统一走这里，不要自行拼接 ``space_dir / path``。

        Args:
            space_id: 空间 ID
            relative: 相对空间根的路径，如 ``docs/a.md``

        Returns:
            解析后的绝对路径，可能尚不存在

        Raises:
            PathEscapeError: 传入绝对路径或带盘符，或解析后越出空间根
        """
        raw = (relative or "").strip()
        if not raw:
            return self.space_dir(space_id).resolve()

        candidate = Path(raw)
        # Windows 下 "C:\x" 在 POSIX 语义里不是绝对路径，必须显式判盘符
        if candidate.is_absolute() or candidate.drive:
            raise PathEscapeError(f"禁止使用绝对路径: {relative}")

        base = self.space_dir(space_id).resolve()
        resolved = (base / candidate).resolve()

        if not resolved.is_relative_to(base):
            raise PathEscapeError(f"路径越出空间目录: {relative}")
        return resolved

    def relative(self, space_id: int | str, path: Path) -> str:
        """把空间内的绝对路径转回 POSIX 相对路径，用于持久化与展示。"""
        return path.resolve().relative_to(self.space_dir(space_id).resolve()).as_posix()

    # ─── 生命周期 ────────────────────────────────────────────────────────

    def create(self, space_id: int | str, space_name: str = "") -> Path:
        """创建空间目录与初始文件，已存在的文件不覆盖。

        幂等；副作用是写目录与骨架文件，重复调用不会冲掉已有编辑。

        Args:
            space_id: 空间 ID
            space_name: 空间名，用于渲染 ``AGENTS.md``

        Returns:
            空间目录绝对路径
        """
        space_dir = self.space_dir(space_id)
        already = space_dir.is_dir()

        (space_dir / "memory").mkdir(parents=True, exist_ok=True)
        (space_dir / "docs").mkdir(parents=True, exist_ok=True)
        (space_dir / "testcases").mkdir(parents=True, exist_ok=True)
        (space_dir / "artifacts").mkdir(parents=True, exist_ok=True)

        self._write_if_absent(
            space_dir / "AGENTS.md",
            templates.AGENTS_MD_TEMPLATE.format(
                space_id=space_id,
                space_name=space_name or f"空间 {space_id}",
                endpoint_count=0,
                environment_summary="尚未配置",
            ),
        )
        self._write_if_absent(space_dir / "memory" / "MEMORY.md", templates.MEMORY_MD_TEMPLATE)
        self._write_if_absent(space_dir / "docs" / "README.md", templates.DOCS_README_TEMPLATE)
        self._write_if_absent(space_dir / "testcases" / ".gitkeep", templates.GITKEEP)
        self._write_if_absent(space_dir / "artifacts" / ".gitkeep", templates.GITKEEP)

        logger.info(
            "空间工作目录就绪",
            space_id=str(space_id),
            space_dir=str(space_dir),
            created=not already,
        )
        return space_dir

    def ensure(self, space_id: int | str) -> Path:
        """确保空间目录存在，缺失时按默认内容补齐。"""
        return self.create(space_id)

    def archive(self, space_id: int | str) -> Path | None:
        """归档空间目录：改名为 ``.deleted-{space_id}-{ts}``，不物理删除。

        Args:
            space_id: 空间 ID

        Returns:
            归档后的路径；目录不存在时返回 None
        """
        space_dir = self.space_dir(space_id)
        if not space_dir.is_dir():
            return None

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        target = self.root / f"{_ARCHIVE_PREFIX}{space_id}-{timestamp}"
        space_dir.rename(target)
        logger.warning("空间目录已归档", space_id=str(space_id), archived=str(target))
        return target

    def purge(self, space_id: int | str) -> bool:
        """物理删除空间目录，不可恢复。

        Args:
            space_id: 空间 ID

        Returns:
            是否实际删除；目录不存在时返回 False
        """
        space_dir = self.space_dir(space_id)
        if not space_dir.is_dir():
            return False
        shutil.rmtree(space_dir)
        logger.warning("空间目录已物理删除", space_id=str(space_id))
        return True

    # ─── 遍历 ────────────────────────────────────────────────────────────

    def tree(self, space_id: int | str, max_depth: int | None = None) -> list[dict[str, Any]]:
        """返回工作目录树，供前端展示。

        Args:
            space_id: 空间 ID
            max_depth: 展开层数，不传时取配置；1 表示只返回根层

        Returns:
            ``[{"name", "type", "path", "size", "children"}]``，目录在前并按名排序；
            目录不存在时返回空列表
        """
        if max_depth is None:
            from src.core.config import get_config

            max_depth = get_config().workspace.tree_max_depth

        space_dir = self.space_dir(space_id)
        if not space_dir.is_dir():
            return []
        return self._walk(space_dir, max_depth)

    def _walk(self, directory: Path, remaining: int) -> list[dict[str, Any]]:
        """递归收集目录条目，``remaining`` 为剩余可展开层数，条目数受配置上限约束。"""
        from src.core.config import get_config

        limit = get_config().workspace.tree_max_entries

        try:
            entries = sorted(
                directory.iterdir(),
                key=lambda p: (not p.is_dir(), p.name.lower()),
            )
        except (PermissionError, OSError):
            return []

        nodes: list[dict[str, Any]] = []
        for entry in entries[:limit]:
            if entry.name in _SKIP_DIRS:
                continue
            is_dir = entry.is_dir()
            node: dict[str, Any] = {
                "name": entry.name,
                "type": "dir" if is_dir else "file",
                "path": entry.relative_to(self.root).as_posix(),
                "size": 0 if is_dir else _safe_size(entry),
                "children": [],
            }
            if is_dir and remaining > 1:
                node["children"] = self._walk(entry, remaining - 1)
            nodes.append(node)
        return nodes

    # ─── 内部 ────────────────────────────────────────────────────────────

    @staticmethod
    def _write_if_absent(path: Path, content: str) -> None:
        """文件不存在时才写入，避免覆盖已有内容。"""
        if path.exists():
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def _safe_size(path: Path) -> int:
    """返回文件字节数；取不到时返回 0，兼容悬空符号链接。"""
    try:
        return path.stat().st_size
    except OSError:
        return 0


_manager: WorkspaceManager | None = None


def get_workspace_manager() -> WorkspaceManager:
    """返回全局 WorkspaceManager 实例（无状态，可复用）。"""
    global _manager
    if _manager is None:
        _manager = WorkspaceManager()
    return _manager


def reset_workspace_manager() -> None:
    """重置全局单例，仅供测试使用。"""
    global _manager
    _manager = None
