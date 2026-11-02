"""Agent 运行时：手写 ReAct 循环。

**为什么不用 LangGraph**：这里只需要「模型 ↔ 工具」两节点循环，
StateGraph / reducer / checkpoint 全都用不上，却要额外维护一套 state schema
和事件映射。手写约 200 行，事件粒度完全可控（``tool_call`` 要带 args、
``tool_result`` 要带耗时），单测也更直接。

三条硬规则：

1. **模式在执行路径上生效**。工具列表进模型前再按模式过滤一次，不依赖调用方
   是否已经裁过——`ask` 模式下模型手里根本不存在 `send_request`，
   它就不可能"违抗指令"去发请求。
2. **工具异常不打断流**。异常转成 ``ok=False`` 的工具结果回灌给模型，
   让模型自己纠偏（换个参数、换个接口、或如实报告失败）。整条流因为
   一次工具报错而中断，是比失败更糟的体验。
3. **工具调用分片交给 LangChain 合并**。流式下参数是 ``{"val`` + ``ue": 1}``
   这样分片到达的，手写拼接极易错位；``AIMessageChunk.__add__`` 已经把
   分片累积与 JSON 解析做对了。
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any

from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from pydantic import ValidationError

from src.agent.context import SpaceSnapshot, build_system_prompt
from src.agent.events import (
    AgentEvent,
    ErrorEvent,
    FinalEvent,
    StartEvent,
    TextDeltaEvent,
    ToolCallEvent,
    ToolResultEvent,
)
from src.agent.modes import filter_tools
from src.agent.recording import RunRecorder, ToolOutcome
from src.agent.tools.registry import ToolBundle, build_tools
from src.core.logging import get_logger

logger = get_logger(__name__)

__all__ = ["RunRequest", "run"]


@dataclass(slots=True)
class RunRequest:
    """一轮对话的输入。

    这里刻意**不收** ORM 对象：运行时只依赖纯数据，才能在没有数据库的情况下
    单测，也避免 session 生命周期跨进异步生成器（很容易拿到已关闭的 session）。

    Attributes:
        instruction: 用户本轮指令
        space_id: 空间 ID
        space_name: 空间名（进 prompt）
        conversation_id: 会话 ID，None 表示新会话
        mode: 工作模式（agent / ask / plan）
        skill_names: 选中的 skill
        environment_id: 指定测试环境
        endpoint_count: 空间接口数（进 prompt）
        environments: 环境清单（进 prompt）
        agents_md: 空间约定全文
        memories: 待注入的跨会话记忆
        skill_blocks: 已渲染的 skill 文本块
        history: 历史消息
        run_id: 执行记录 ID，由调用方在 recorder.start() 后回填（供 llm_log 归因）
    """

    instruction: str
    space_id: int | str = 0
    space_name: str = ""
    conversation_id: int | None = None
    mode: str = "agent"
    skill_names: list[str] = field(default_factory=list)
    environment_id: int | None = None
    endpoint_count: int = 0
    environments: list[dict[str, Any]] = field(default_factory=list)
    agents_md: str = ""
    memories: list[dict[str, Any]] = field(default_factory=list)
    skill_blocks: str = ""
    history: list[BaseMessage] = field(default_factory=list)
    run_id: int | None = None


async def run(
    request: RunRequest,
    *,
    model: Any | None = None,
    bundle: ToolBundle | None = None,
    recorder: RunRecorder | None = None,
) -> AsyncIterator[AgentEvent]:
    """执行一轮对话，逐事件产出。

    Args:
        request: 本轮输入
        model: 聊天模型（测试注入用）；None 时取全局 gateway
        bundle: 工具集合（测试注入用）；None 时按请求装配
        recorder: 执行记录器；None 表示不落库（单测、无 DB 场景）

    Yields:
        AgentEvent：start → (text_delta | tool_call | tool_result)* → final | error
    """
    tools = bundle or build_tools(
        space_id=request.space_id,
        mode=request.mode,
        skill_names=request.skill_names,
        conversation_id=request.conversation_id,
        environment_id=request.environment_id,
    )
    policy = tools.policy
    # 再裁一次：bundle 可能是调用方手工构造的，模式保证必须在执行路径上闭环
    allowed = filter_tools(tools.tools, policy, tools.skill_allowed)

    yield StartEvent(
        conversation_id=request.conversation_id,
        space_id=request.space_id,
        mode=policy.mode.value,
        skills=list(request.skill_names),
        run_id=request.run_id,
    )

    messages: list[BaseMessage] = [
        SystemMessage(content=_system_prompt(request, tools)),
        *request.history,
        HumanMessage(content=request.instruction),
    ]
    chat = _make_streamer(model, allowed, request)
    tool_map = {tool.name: tool for tool in allowed}
    # seq 用局部计数器，别用模块级全局（并发多轮会互相污染）
    seq_counter = iter(range(1, 1_000_000))

    logger.info(
        "Agent 轮次开始",
        space_id=str(request.space_id),
        mode=policy.mode.value,
        tools=len(allowed),
        max_steps=policy.max_steps,
    )

    for step in range(policy.max_steps):
        try:
            accumulated = None
            async for chunk in chat(messages):
                text = _chunk_text(chunk)
                if text:
                    yield TextDeltaEvent(content=text)
                accumulated = _merge(accumulated, chunk)
        except Exception as exc:  # 模型/网络层失败，本轮无法继续
            logger.warning("模型调用失败", error=str(exc), step=step)
            yield ErrorEvent(message=f"模型调用失败：{exc}")
            return

        calls = list(getattr(accumulated, "tool_calls", None) or [])
        if not calls:
            answer = _chunk_text(accumulated) if accumulated is not None else ""
            logger.info("Agent 轮次结束", steps=step + 1, answer_chars=len(answer))
            yield FinalEvent(answer=answer, usage=_usage(accumulated))
            return

        messages.append(_assistant_message(accumulated, calls))

        for call in calls:
            name = str(call.get("name") or "")
            args = call.get("args") if isinstance(call.get("args"), dict) else {}
            call_id = str(call.get("id") or f"call_{step}_{name}")

            yield ToolCallEvent(id=call_id, name=name, args=dict(args))

            started = perf_counter()
            outcome: ToolOutcome | None = None
            try:
                outcome = await _execute(tool_map, name, args)
            finally:
                # 记录放在 finally：即便恰在此刻被断流，已完成的调用也要留痕。
                # 这里只做同步调用（recorder 内部是短事务），不 await、不 yield。
                duration_ms = int((perf_counter() - started) * 1000)
                if outcome is not None and recorder is not None:
                    try:
                        recorder.tool_call(
                            step=step,
                            seq=next(seq_counter),
                            call_id=call_id,
                            name=name,
                            args=dict(args),
                            outcome=outcome,
                            duration_ms=duration_ms,
                        )
                    except Exception:  # 记录层内部已兜，这里防未知错误打断流
                        logger.warning("工具调用记录失败", tool=name)

            # 模型看到的内容与前端看到的内容必须一致，否则排障时必然误判
            content = _for_model(outcome.text)
            yield ToolResultEvent(id=call_id, name=name, ok=outcome.ok, content=content, duration_ms=duration_ms)
            messages.append(ToolMessage(content=content, tool_call_id=call_id, name=name or None))

    logger.warning("Agent 超过最大轮次", max_steps=policy.max_steps)
    yield ErrorEvent(message=f"超过最大工具调用轮次（{policy.max_steps}），已中止本轮")


# ---------------------------------------------------------------------------
# 组装
# ---------------------------------------------------------------------------

def _system_prompt(request: RunRequest, tools: ToolBundle) -> str:
    snapshot = SpaceSnapshot(
        space_id=request.space_id,
        space_name=request.space_name or f"空间 {request.space_id}",
        endpoint_count=request.endpoint_count,
        environments=list(request.environments),
        agents_md=request.agents_md,
    )
    return build_system_prompt(
        snapshot,
        tools.policy,
        memories=request.memories,
        skill_blocks=request.skill_blocks,
    )


def _make_streamer(model: Any | None, tools: list[BaseTool], request: RunRequest) -> Any:
    """返回「发一轮消息 → 产出 chunk 流」的可调用对象。
    """
    if model is not None:
        bound = model.bind_tools(tools) if tools else model
        return bound.astream

    from src.core.llm.llm_gateway import get_llm_gateway

    gateway = get_llm_gateway()

    def _stream(messages: list[BaseMessage]) -> Any:
        return gateway.astream_with_tools(
            messages,
            tools,
            space_id=request.space_id,
            conversation_id=request.conversation_id,
            run_id=request.run_id,
        )

    return _stream


# ---------------------------------------------------------------------------
# 流式分片处理
# ---------------------------------------------------------------------------

def _merge(accumulated: Any, chunk: Any) -> Any:
    """把流式 chunk 累积起来。

    优先用 LangChain 的 ``+``（会累积 content 与 tool_call_chunks 并解析参数）；
    遇到不可加的 provider 私有 chunk 时退化为「只保留 content」。
    """
    if accumulated is None:
        return chunk
    try:
        return accumulated + chunk
    except Exception:  # 少数 provider 的 chunk 不可相加
        text = _chunk_text(accumulated) + _chunk_text(chunk)
        return AIMessageChunk(content=text)


def _chunk_text(chunk: Any) -> str:
    """取 chunk 的纯文本。多模态 content 是 list，拼掉非文本部分。"""
    content = getattr(chunk, "content", "") if chunk is not None else ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict) and isinstance(part.get("text"), str):
                parts.append(part["text"])
        return "".join(parts)
    return ""


def _usage(accumulated: Any) -> dict[str, Any]:
    usage = getattr(accumulated, "usage_metadata", None) if accumulated is not None else None
    return dict(usage) if usage else {}


def _assistant_message(accumulated: Any, calls: list[dict]) -> AIMessage:
    """把累积结果固化成 AIMessage 回写上下文。

    只保留 ``id/name/args/type`` 四个键：provider 附加字段（如
    ``index``、``provider_specific_fields``）回传时会被部分模型拒绝。
    """
    return AIMessage(
        content=_chunk_text(accumulated),
        tool_calls=[
            {
                "id": str(call.get("id") or ""),
                "name": str(call.get("name") or ""),
                "args": call.get("args") if isinstance(call.get("args"), dict) else {},
                "type": "tool_call",
            }
            for call in calls
        ],
    )


# ---------------------------------------------------------------------------
# 工具执行
# ---------------------------------------------------------------------------

async def _execute(tool_map: dict[str, BaseTool], name: str, args: dict[str, Any]) -> ToolOutcome:
    """执行单个工具调用，返回 ``ToolOutcome``。

    任何异常都在这里被吃掉并转成文本——工具失败是**正常业务分支**，
    不是链路故障。模型需要看到失败原因才能自我修正。

    同时把异常类型与原文一并带出（``ToolOutcome.error_type`` /
    ``error_message``）：记录层需要它才能回答「这个工具为什么常年失败」，
    而这些信息一旦被压成话术就再也拿不回来了。
    """
    tool = tool_map.get(name)
    if tool is None:
        return ToolOutcome(
            False,
            f"工具 {name} 不存在。当前可用工具：{', '.join(sorted(tool_map)) or '（无）'}。"
            f"请只调用列表中存在的工具。",
            "not_found",
            f"tool {name} not found",
        )

    try:
        result = await _ainvoke(tool, args)
    except ValidationError as exc:  # 参数不符合 schema：最常见的模型失误
        message = _validation_message(exc)
        return ToolOutcome(False, f"工具 {name} 参数不合法：{message}", "validation", message)
    except Exception as exc:
        logger.warning("工具执行失败", tool=name, error=str(exc))
        return ToolOutcome(
            False,
            f"工具 {name} 执行失败：{type(exc).__name__}: {exc}",
            type(exc).__name__,
            str(exc),
        )

    # ⚠️ 这里返回**全量**文本：落库需要它。给模型的截断在 _for_model 里做。
    return ToolOutcome(True, _raw_text(result))


def _validation_message(exc: Exception) -> str:
    """把 pydantic 校验错误压成模型能读懂的一行。"""
    errors = getattr(exc, "errors", None)
    if callable(errors):
        try:
            details = [
                f"{'.'.join(str(p) for p in err.get('loc', ())) or '参数'}: {err.get('msg', '')}"
                for err in errors()
            ]
            if details:
                return "；".join(details)
        except Exception:
            pass
    return str(exc)


async def _ainvoke(tool: BaseTool, args: dict[str, Any]) -> Any:
    """统一的工具调用入口。

    LangChain 的 ``ainvoke`` 对同步工具会走线程池，但对某些自定义 tool 实现
    可能不存在——这里做一次降级，避免单测里注入的假工具直接 AttributeError。
    """
    ainvoke = getattr(tool, "ainvoke", None)
    if callable(ainvoke):
        return await ainvoke(args)
    return tool.invoke(args)


_MAX_RESULT_CHARS = 8_000


def _raw_text(result: Any) -> str:
    """工具返回值归一化为文本，**不做长度限制**（供落库与后续截断复用）。"""
    if isinstance(result, str):
        return result
    try:
        return json.dumps(result, ensure_ascii=False, default=str)
    except Exception:
        return str(result)


def _for_model(raw: str) -> str:
    """给模型看的版本：8000 字符上限。

    上限比 SSE 下发（4k）更宽：模型看到的内容要多于用户看到的内容，
    否则模型会以为自己读到的就是全部。落库则由 recorder 单独限 2MB，
    三者是各自独立的三级台阶，不要互相复用同一个常量。
    """
    if len(raw) <= _MAX_RESULT_CHARS:
        return raw
    return raw[:_MAX_RESULT_CHARS] + f"\n…（工具结果已截断，原始长度 {len(raw)} 字符）"
