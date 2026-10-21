"""空间工作目录子系统。

对外只暴露两个东西：``WorkspaceManager``（目录生命周期与沙箱）和
``get_workspace_manager()``（无状态单例）。
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
