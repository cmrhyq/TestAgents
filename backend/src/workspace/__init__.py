"""空间工作目录子系统。

对外暴露 ``WorkspaceManager``（目录生命周期与沙箱）与 ``get_workspace_manager()`` 单例。
"""

from src.workspace.manager import (
    PathEscapeError,
    WorkspaceManager,
    get_workspace_manager,
    reset_workspace_manager,
)

__all__ = [
    "PathEscapeError",
    "WorkspaceManager",
    "get_workspace_manager",
    "reset_workspace_manager",
]
