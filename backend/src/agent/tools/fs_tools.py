"""空间沙箱文件工具。

和旧实现的三点区别：

1. **路径基准从「仓库根」改成「空间目录」**。旧实现允许 Agent 读整个仓库，
   在测试 Agent 场景里等于把后端源码和密钥都暴露给模型。
2. **工具按空间绑定**。``space_id`` 由运行时注入闭包，不出现在工具参数里——
   让模型传 space_id 只会增加幻觉空间（它会编一个不存在的 ID）。
3. **写能力独立成型**。旧实现只有读；测试 Agent 必须能把用例、报告落到
   ``testcases/`` 与 ``artifacts/``，否则产物只活在对话里。

所有失败都返回**字符串错误**而不是抛异常：工具异常会打断 ReAct 循环，
而「这个文件不存在」恰恰是模型应该看到并自行调整策略的信息。
"""

from __future__ import annotations

from pathlib import Path

from langchain_core.tools import BaseTool, tool

from src.core.logging import get_logger
from src.workspace.manager import PathEscapeError, WorkspaceManager

logger = get_logger(__name__)

# 单次读取上限：再大就会把上下文挤爆，宁可截断并明确告知
MAX_READ_CHARS = 200 * 1024
# 单次写入上限：防止模型一次吐一个巨型文件把磁盘写满
MAX_WRITE_CHARS = 1024 * 1024
# 列表最多显示的条目数
MAX_LIST_ENTRIES = 200

# 核心约定文件：Agent 可读可改，但不许删（删了空间就丢了「长期约定」）
PROTECTED_FILES = frozenset({"AGENTS.md", "memory/MEMORY.md"})

_SKIP_DIRS = frozenset({"__pycache__", ".git", ".idea", ".pytest_cache", ".ruff_cache", "node_modules"})


def make_fs_tools(space_id: int | str, workspace: WorkspaceManager | None = None) -> list[BaseTool]:
    """构造绑定到某个空间的读写文件工具集。"""
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
        """在当前空间目录内写入文件（父目录会自动创建，已存在则覆盖）。

        适合把测试用例、执行结果、报告落盘为可复用的资产。

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
        """删除当前空间目录内的单个文件（不可恢复，请谨慎）。

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
    from src.workspace.manager import get_workspace_manager

    return get_workspace_manager()
