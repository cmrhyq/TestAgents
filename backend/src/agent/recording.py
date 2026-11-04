"""执行记录协议。

只定义记录契约与数据结构，写库实现位于 ``src.data.recording``。
三个方法均为同步：断流收尾时 ``await`` 会被取消，写库无法完成。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(slots=True)
class ToolOutcome:
    """一次工具执行的结果。

    ``error_type`` / ``error_message`` 保留原始异常信息，供留痕层归因，
    避免被 ``runner`` 转成给模型的话术后无法追溯。
    """

    ok: bool
    text: str = ""  # 全量结果文本，不截断
    error_type: str = ""  # 异常类名 / 'validation' / 'not_found'
    error_message: str = ""  # 异常原文，不截断


@runtime_checkable
class RunRecorder(Protocol):
    """执行记录器契约，全部为同步方法。"""

    run_id: int | None

    def start(
        self,
        *,
        space_id: int,
        environment_id: int | None = None,
        conversation_id: int | None = None,
        mode: str = "agent",
        title: str = "",
        trigger_type: str = "chat",
    ) -> int | None:
        """开启一条执行记录。

        副作用：写入记录存储。

        Returns:
            新记录的 ID；无法落库时返回 None
        """
        ...

    def tool_call(
        self,
        *,
        step: int,
        seq: int,
        call_id: str,
        name: str,
        args: dict[str, Any],
        outcome: ToolOutcome,
        duration_ms: int,
    ) -> None:
        """记录一次工具调用结果。

        副作用：写入记录存储。
        """
        ...

    def finish(self, *, status: str, error_message: str = "") -> None:
        """收尾记录并写入最终状态。

        副作用：写入记录存储。

        Args:
            status: 终态标识，取值由调用方约定
            error_message: 失败原因，成功时为空
        """
        ...


class NullRecorder:
    """不落库的实现：runner 单测、DB 不可用时的降级都走它。"""

    run_id: int | None = None

    def start(self, **_: Any) -> int | None:
        """不落库，固定返回 None。"""
        return None

    def tool_call(self, **_: Any) -> None:
        """空实现。"""
        return

    def finish(self, **_: Any) -> None:
        """空实现。"""
        return
