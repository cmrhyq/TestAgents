"""chat 流式编排服务。

职责边界很清楚：**组装输入 + 落库输出**，不含任何决策逻辑。
具体「模型怎么想、工具怎么调」全在 ``src/agent/runner.py``。

一轮对话的完整时序::

    ensure_conversation  会话落库 + user 消息落库（流开始前，同步）
        ↓
    prepare              从 DB / 文件系统 / 记忆库收集 RunRequest（同步，线程池）
        ↓
    runner.run           产出 AgentEvent（异步生成器）
        ↓
    render               事件 → SSE 帧
        ↓
    save_answer          回答落库（流结束后）

``prepare`` 是同步的、在读取前一次性把上下文备齐：**异步生成器里不要持着 DB
session**——生成器可能被客户端随时中断，session 的生命周期会变得不可预测。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from time import perf_counter
from typing import Any

from fastapi.concurrency import run_in_threadpool
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from src.agent.events import FinalEvent, ErrorEvent, render
from src.agent.modes import normalize_mode
from src.agent.runner import RunRequest, run as run_agent
from src.core.database.database_manager import get_db_manager
from src.core.logging import get_logger
from src.data.models.space import Space
from src.data.schemas.conversation import ConversationCreate
from src.data.services.conversation_service import ConversationService
from src.data.services.environment_service import EnvironmentService

logger = get_logger(__name__)

# 注入 LLM 的历史消息条数上限：问答场景不需要无穷长的上下文，
# 截断同时控制了 token 成本与超长上下文带来的指令漂移。
MAX_HISTORY_MESSAGES = 20

# 空间约定文件与记忆镜像的路径（相对空间根目录）
AGENTS_FILE = "AGENTS.md"
MEMORY_FILE = "memory/MEMORY.md"


class ChatStreamService:
    """chat 会话编排：会话落库、上下文装配、事件下发、回答落库。"""

    # ─── 落库 ────────────────────────────────────────────────────────────

    def ensure_conversation(self, body) -> int:
        """确保存在会话并返回 conversation_id；同时把 user 消息落库。

        若 ``body.conversation_id`` 为空则新建会话。整个操作在独立 DB 事务中完成。

        落库失败（DB 未初始化等）不阻断对话——宁可丢历史，也不要让用户
        连一句回答都拿不到。
        """
        try:
            with get_db_manager().get_session() as session:
                service = ConversationService(session)
                conversation_id = body.conversation_id
                if conversation_id is None:
                    conversation = service.create_conversation(
                        ConversationCreate(
                            space_id=body.space_id,
                            title="",
                            mode=normalize_mode(body.mode).value,
                            skill_names=list(getattr(body, "skill_names", None) or []),
                            environment_id=getattr(body, "environment_id", None),
                        )
                    )
                    conversation_id = conversation.id
                service.append_message(conversation_id, role="user", content=body.instruction)
                return conversation_id
        except RuntimeError as exc:
            logger.warning("会话持久化暂不可用，继续执行流式对话", error=str(exc))
            return body.conversation_id or 0
        except Exception as exc:
            logger.error("会话持久化失败，继续执行流式对话", error=str(exc))
            return body.conversation_id or 0

    def save_answer(self, conversation_id: int, answer: str) -> None:
        """把最终回答落库为 assistant 消息。

        落库失败只记日志，不影响已经下发给用户的流式内容。

        Args:
            conversation_id: 会话 ID
            answer: 回答文本
        """
        if not conversation_id or not answer.strip():
            return
        try:
            with get_db_manager().get_session() as session:
                ConversationService(session).append_message(conversation_id, role="assistant", content=answer)
        except Exception as exc:
            logger.error("回答落库失败", error=str(exc), conversation_id=conversation_id)

    # ─── 上下文装配 ──────────────────────────────────────────────────────

    def load_history(self, conversation_id: int, *, exclude_trailing_user: bool = False) -> list[BaseMessage]:
        """读取会话历史并转换为 LangChain 消息。

        Args:
            conversation_id: 会话 ID
            exclude_trailing_user: 是否剔除末尾的 user 消息。
                ``ensure_conversation`` 已把本轮提问落库，若不剔除，
                本轮问题会在上下文中出现两次（一次在历史、一次作为本轮输入）。

        Returns:
            HumanMessage / AIMessage 列表（按时间升序）；读取失败时返回空列表按单轮处理
        """
        if not conversation_id:
            return []

        try:
            with get_db_manager().get_session() as session:
                messages = ConversationService(session).list_messages(conversation_id)
        except Exception as exc:
            logger.warning("会话历史读取失败，本轮按单轮处理", error=str(exc), conversation_id=conversation_id)
            return []

        if exclude_trailing_user and messages and messages[-1].role == "user":
            messages = messages[:-1]
        messages = messages[-MAX_HISTORY_MESSAGES:]

        history: list[BaseMessage] = []
        for message in messages:
            content = message.content or ""
            if not content.strip():
                continue
            if message.role == "user":
                history.append(HumanMessage(content=content))
            elif message.role == "assistant":
                history.append(AIMessage(content=content))
        return history

    def prepare(self, body, conversation_id: int) -> RunRequest:
        """收集一轮对话需要的全部上下文，构造 ``RunRequest``。

        这里的每一次外部读取都做了降级：空间查不到就只给个占位名，
        记忆读失败就当没有记忆，AGENTS.md 缺失就跳过。
        **上下文缺一块不该导致整轮对话失败**。

        Args:
            body: ``ChatStreamRequest``
            conversation_id: 已落库的会话 ID

        Returns:
            RunRequest
        """
        space_id = int(body.space_id) if body.space_id is not None else 0
        mode = normalize_mode(body.mode).value
        skill_names = list(getattr(body, "skill_names", None) or [])

        space_name, endpoint_count, environments = self._load_space(space_id)
        agents_md = self._read_space_file(space_id, AGENTS_FILE)
        memories = self._load_memories(space_id, body.instruction)
        skill_blocks = self._load_skill_blocks(skill_names, space_id)

        return RunRequest(
            instruction=body.instruction,
            space_id=space_id,
            space_name=space_name,
            conversation_id=conversation_id,
            mode=mode,
            skill_names=skill_names,
            environment_id=getattr(body, "environment_id", None),
            endpoint_count=endpoint_count,
            environments=environments,
            agents_md=agents_md,
            memories=memories,
            skill_blocks=skill_blocks,
            history=self.load_history(conversation_id, exclude_trailing_user=True),
        )

    def _load_space(self, space_id: int) -> tuple[str, int, list[dict[str, Any]]]:
        """读空间名、接口数、环境清单。"""
        if not space_id:
            return "", 0, []

        try:
            with get_db_manager().get_session() as session:
                space = session.get(Space, space_id)
                if space is None:
                    return "", 0, []
                name = space.name or ""
                endpoints = len(space.endpoints) if space.endpoints is not None else 0
                environments = [
                    {
                        "id": env.id,
                        "name": env.name,
                        "base_url": env.base_url,
                        "is_production": bool(env.is_production),
                    }
                    for env in EnvironmentService(session).list_by_space(space_id)
                ]
            return name, endpoints, environments
        except Exception as exc:
            logger.warning("空间上下文读取失败，按空空间处理", space_id=str(space_id), error=str(exc))
            return "", 0, []

    def _read_space_file(self, space_id: int, relative: str) -> str:
        """读空间目录里的文本文件；不存在或读失败返回空串。"""
        if not space_id:
            return ""
        try:
            from src.workspace.manager import get_workspace_manager

            path = get_workspace_manager().resolve(space_id, relative)
            if not path.is_file():
                return ""
            return path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            logger.debug("空间文件读取失败", relative=relative, error=str(exc))
            return ""

    def _load_memories(self, space_id: int, instruction: str) -> list[dict[str, Any]]:
        """召回跨会话记忆，转成 prompt 需要的 dict 形态。"""
        if not space_id:
            return []
        try:
            from src.memory import get_long_term_memory

            entries = get_long_term_memory().recall(space_id, instruction)
        except Exception as exc:
            logger.warning("记忆召回失败，本轮不注入记忆", space_id=str(space_id), error=str(exc))
            return []

        return [
            {
                "id": entry.id,
                "title": entry.title,
                "content": entry.content,
                "category": entry.category,
            }
            for entry in entries
        ]

    def _load_skill_blocks(self, names: list[str], space_id: int) -> str:
        """渲染选中 skill 的正文块。"""
        if not names:
            return ""
        try:
            from src.skill.service import get_skill_service

            return get_skill_service().build_prompt_blocks(names, space_id or None)
        except Exception as exc:
            logger.warning("skill 正文读取失败，本轮不注入技能", skills=names, error=str(exc))
            return ""

    # ─── 流式执行 ────────────────────────────────────────────────────────

    async def stream_answer(self, body, conversation_id: int) -> AsyncIterator[str]:
        """跑一轮 Agent 并产出 SSE 帧。

        事件序列::

            start → (text_delta | tool_call → tool_result)* → final
                                                            ↘ error

        帧格式为标准的 ``id:`` / ``event:`` / ``data:`` 三行 + 空行，
        其中 ``id`` 是递增的事件序号，为后续断线续传（``Last-Event-ID``）预留。

        Args:
            body: ``ChatStreamRequest``
            conversation_id: 已落库的会话 ID

        Yields:
            可直接写入 ``StreamingResponse`` 的 SSE 文本帧
        """
        started = perf_counter()
        seq = 0
        answer = ""
        failed = False

        try:
            request = await run_in_threadpool(self.prepare, body, conversation_id)
        except Exception as exc:
            logger.error("上下文装配失败", error=str(exc), conversation_id=conversation_id)
            yield render(ErrorEvent(message=f"上下文准备失败：{exc}"), 0)
            return

        try:
            async for event in run_agent(request):
                if isinstance(event, FinalEvent):
                    answer = event.answer
                elif isinstance(event, ErrorEvent):
                    failed = True
                yield render(event, seq)
                seq += 1
        except Exception as exc:  # runner 内部已兜住绝大多数异常，这里兜最后一道
            logger.error("流式执行失败", error=str(exc), conversation_id=conversation_id)
            yield render(ErrorEvent(message=str(exc)), seq)
            failed = True

        logger.info(
            "对话流结束",
            conversation_id=conversation_id,
            mode=request.mode,
            events=seq,
            failed=failed,
            duration_ms=int((perf_counter() - started) * 1000),
        )

        if not failed:
            self.save_answer(conversation_id, answer)
