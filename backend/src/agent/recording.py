"""执行记录协议。

**为什么协议放在 agent 层、实现在 data 层**：``runner`` 的 docstring 立了规矩
——不依赖 ORM、没有数据库也能单测。记录器如果直接 import Model，这条规矩就废了。
这里只定义「什么叫记录」，由 ``src.data.recording`` 提供真正写库的实现。

**为什么三个方法全是同步的**：``stream_answer`` 的 ``finally`` 会在客户端断流
（``GeneratorExit``）时执行，那个状态下 ``await`` 会立刻被 ``CancelledError``
打断，收尾写库就石沉大海，记录永远停在 ``running``。同步调用不让出控制权，
一定能写完。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(slots=True)
class ToolOutcome:
    """一次工具执行的结果。

    为什么不用 ``(bool, str)`` 元组：``runner._execute`` 会把异常吃掉、转成
    一句给模型看的话术，异常类型与原文就此丢失。留痕层必须拿到 ``error_type``
    才能回答「这个工具到底为什么常年失败」。
    """

    ok: bool
    text: str = ""  # 全量结果文本，**不截断**
    error_type: str = ""  # 异常类名 / 'validation' / 'not_found'
    error_message: str = ""  # 异常原文，不截断


@runtime_checkable
class RunRecorder(Protocol):
    """执行记录器契约。全部同步方法。"""

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
    ) -> int | None: ...

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
    ) -> None: ...

    def finish(self, *, status: str, error_message: str = "") -> None: ...


class NullRecorder:
    """不落库的实现：runner 单测、DB 不可用时的降级都走它。"""

    run_id: int | None = None

    def start(self, **_: Any) -> int | None:
        return None

    def tool_call(self, **_: Any) -> None:
        return

    def finish(self, **_: Any) -> None:
        return
