"""空间沙箱文件工具。

路径基准是空间目录，越界访问被拒绝；所有失败返回错误字符串而不抛异常，
以便模型自行调整策略。写操作会落盘，必要时自动创建父目录。
"""

from __future__ import annotations

from pathlib import Path

from langchain_core.tools import BaseTool, tool

from src.core.logging import get_logger
from src.workspace.manager import PathEscapeError, WorkspaceManager

logger = get_logger(__name__)

# 单次读取上限，超出部分截断并告知
MAX_READ_CHARS = 200 * 1024
# 单次写入上限，防止一次写入巨型文件
MAX_WRITE_CHARS = 1024 * 1024
# 列表最多显示的条目数
MAX_LIST_ENTRIES = 200

# 核心约定文件：可读可改，不可删除
PROTECTED_FILES = frozenset({"AGENTS.md", "memory/MEMORY.md"})

_SKIP_DIRS = frozenset({"__pycache__", ".git", ".idea", ".pytest_cache", ".ruff_cache", "node_modules"})


def make_fs_tools(space_id: int | str, workspace: WorkspaceManager | None = None) -> list[BaseTool]:
    """构造绑定到某个空间的读写文件工具集。

    Args:
        space_id: 空间 ID，所有路径都相对该空间目录解析
        workspace: 工作区管理器；None 时使用全局实例

    Returns:
        工具列表：``read_file``、``write_file``、``list_directory``、``delete_file``
    """
    manager = workspace or _default_workspace()

    def _resolve(path: str) -> tuple[Path | None, str | None]:
        """统一解析入口；越界时返回 (None, 错误文案)。"""
        try:
            return manager.resolve(space_id, path), None
        except PathEscapeError as exc:
            return None, f"错误: {exc}（只能访问当前空间目录内的文件）"

    @tool
    def read_file(path: str) -> str:
        """读取当前空间目录内的文件内容。

        超过 ``MAX_READ_CHARS`` 时截断，并在开头注明原始大小。

        Args:
            path: 相对空间根目录的路径，如 "AGENTS.md"、"artifacts/report.md"
        """
        target, error = _resolve(path)
        if error:
            return error
        assert target is not None

        if not target.exists():
            return f"错误: 文件不存在 - {path}（先用 list_directory 看看有什么）"
        if target.is_dir():
            return f"错误: {path} 是目录，请用 list_directory"

        try:
            content = target.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return f"错误: 读取失败 - {exc}"

        if len(content) > MAX_READ_CHARS:
            return (
                f"[文件过大({len(content)}字符)，已截断至前 {MAX_READ_CHARS} 字符]\n"
                f"{content[:MAX_READ_CHARS]}"
            )
        return content

    @tool
    def write_file(path: str, content: str) -> str:
        """在当前空间目录内写入文件（父目录自动创建，已存在则覆盖）。

        副作用：写入或覆盖磁盘文件。

        Args:
            path: 相对空间根目录的路径，建议放在 testcases/ 或 artifacts/ 下
            content: 完整文件内容
        """
        if len(content) > MAX_WRITE_CHARS:
            return f"错误: 内容过大（{len(content)} 字符），单次上限 {MAX_WRITE_CHARS}"

        target, error = _resolve(path)
        if error:
            return error
        assert target is not None

        if target.is_dir():
            return f"错误: {path} 是目录"

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        except OSError as exc:
            return f"错误: 写入失败 - {exc}"

        return f"已写入 {path}（{len(content)} 字符）"

    @tool
    def list_directory(path: str = ".") -> str:
        """列出当前空间目录下某个目录的条目。

        Args:
            path: 相对空间根目录的目录路径，默认根目录
        """
        target, error = _resolve(path)
        if error:
            return error
        assert target is not None

        if not target.exists():
            return f"错误: 目录不存在 - {path}"
        if not target.is_dir():
            return f"错误: {path} 不是目录，请用 read_file"

        try:
            entries = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except OSError as exc:
            return f"错误: 无法列目录 - {exc}"

        lines = [f"目录: {path}"]
        shown = 0
        for entry in entries:
            if entry.name in _SKIP_DIRS:
                continue
            if shown >= MAX_LIST_ENTRIES:
                lines.append(f"  …（条目超过 {MAX_LIST_ENTRIES}，已截断）")
                break
            if entry.is_dir():
                lines.append(f"  [DIR]  {entry.name}/")
            else:
                lines.append(f"  [FILE] {entry.name}  ({_human_size(entry)})")
            shown += 1

        if shown == 0:
            lines.append("  (空目录)")
        return "\n".join(lines)

    @tool
    def delete_file(path: str) -> str:
        """删除当前空间目录内的单个文件，删除后不可恢复。

        副作用：删除磁盘文件。``PROTECTED_FILES`` 中的文件会被拒绝。

        Args:
            path: 相对空间根目录的文件路径
        """
        normalized = path.replace("\\", "/").lstrip("./")
        if normalized in PROTECTED_FILES:
            return f"错误: {path} 是空间核心约定文件，不允许删除"

        target, error = _resolve(path)
        if error:
            return error
        assert target is not None

        if not target.exists():
            return f"错误: 文件不存在 - {path}"
        if target.is_dir():
            return f"错误: {path} 是目录，delete_file 只删文件"

        try:
            target.unlink()
        except OSError as exc:
            return f"错误: 删除失败 - {exc}"
        return f"已删除 {path}"

    return [read_file, write_file, list_directory, delete_file]


def _human_size(path: Path) -> str:
    """返回人类可读的文件大小；读取失败返回 ``?``。"""
    try:
        size = path.stat().st_size
    except OSError:
        return "?"
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


def _default_workspace() -> WorkspaceManager:
    """返回全局工作区管理器。"""
    from src.workspace.manager import get_workspace_manager

    return get_workspace_manager()
