"""chat 流式编排服务：组装输入并落库输出，决策逻辑在 ``src/agent/runner.py``。

时序为 ``ensure_conversation``、``prepare``、``runner.run``、``render``、``save_answer``。
``prepare`` 同步一次性备齐上下文，异步生成器内不持有 DB session，因为客户端可能随时中断。
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
from src.data.recording import AgentRunRecorder
from src.data.schemas.conversation import ConversationCreate
from src.data.services.conversation_service import ConversationService
from src.data.services.environment_service import EnvironmentService

logger = get_logger(__name__)

# 注入 LLM 的历史消息条数上限，同时控制 token 成本与超长上下文带来的指令漂移
MAX_HISTORY_MESSAGES = 20

# 空间约定文件与记忆镜像的路径，相对空间根目录
AGENTS_FILE = "AGENTS.md"
MEMORY_FILE = "memory/MEMORY.md"


class ChatStreamService:
    """chat 会话编排：会话落库、上下文装配、事件下发、回答落库。"""

    # 落库

    def ensure_conversation(self, body) -> int:
        """确保会话存在并返回 ``conversation_id``，同时把 user 消息落库。

        在独立的数据库事务中完成，事务随上下文退出提交。``body.conversation_id``
        为空时新建会话。落库失败只记日志并返回原 ID（或 0），不阻断对话。

        副作用：写库并提交。

        Args:
            body: ``ChatStreamRequest``，需含 ``space_id``、``instruction``、``mode``

        Returns:
            会话主键；持久化失败时返回入参已有的 ID，没有则返回 0
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

        落库失败只记日志，不影响已下发给客户端的内容。会话 ID 为 0 或回答为空白时
        直接跳过。

        副作用：写库并提交。

        Args:
            conversation_id: 会话主键
            answer: 回答文本
        """
        if not conversation_id or not answer.strip():
            return
        try:
            with get_db_manager().get_session() as session:
                ConversationService(session).append_message(conversation_id, role="assistant", content=answer)
        except Exception as exc:
            logger.error("回答落库失败", error=str(exc), conversation_id=conversation_id)

    # 上下文装配

    def load_history(self, conversation_id: int, *, exclude_trailing_user: bool = False) -> list[BaseMessage]:
        """读取会话历史并转换为 LangChain 消息。

        Args:
            conversation_id: 会话主键
            exclude_trailing_user: 是否剔除末尾的 user 消息。``ensure_conversation``
                已把本轮提问落库，不剔除会让同一问题在上下文中出现两次

        Returns:
            按时间升序的 ``HumanMessage`` / ``AIMessage`` 列表，最多
            ``MAX_HISTORY_MESSAGES`` 条；读取失败时返回空列表，本轮按单轮处理
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
        """收集一轮对话所需上下文并构造 ``RunRequest``。

        所有外部读取均降级：空间查不到给占位名，记忆读失败视为无记忆，
        ``AGENTS.md`` 缺失则跳过。单块上下文缺失不影响整轮对话。

        Args:
            body: ``ChatStreamRequest``
            conversation_id: 已落库的会话主键

        Returns:
            可直接交给 ``runner.run`` 的请求对象
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
        """读取空间名、接口数与环境清单。

        Args:
            space_id: 空间主键，0 或空表示未指定空间

        Returns:
            ``(空间名, 接口数, 环境字典列表)``；空间不存在或读取失败时返回空值
        """
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
        """读取空间目录下的文本文件。

        Args:
            space_id: 空间主键
            relative: 相对空间根目录的路径

        Returns:
            文件内容；文件不存在、空间未指定或读取失败时返回空串
        """
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
        """召回跨会话记忆并转为 prompt 使用的字典结构。

        Args:
            space_id: 空间主键
            instruction: 本轮用户输入，作为召回查询

        Returns:
            记忆条目字典列表；空间未指定或召回失败时返回空列表
        """
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
        """渲染选中 skill 的正文块。

        Args:
            names: skill 名列表
            space_id: 空间主键，0 时按无空间处理

        Returns:
            拼接后的 skill 正文；名称为空或读取失败时返回空串
        """
        if not names:
            return ""
        try:
            from src.skill.service import get_skill_service

            return get_skill_service().build_prompt_blocks(names, space_id or None)
        except Exception as exc:
            logger.warning("skill 正文读取失败，本轮不注入技能", skills=names, error=str(exc))
            return ""

    # 流式执行

    async def stream_answer(self, body, conversation_id: int) -> AsyncIterator[str]:
        """执行一轮 Agent 并产出 SSE 帧。

        事件顺序为 ``start``、若干 ``text_delta`` 或 ``tool_call`` + ``tool_result``、
        最后 ``final`` 或 ``error``。每帧为 ``id:`` / ``event:`` / ``data:`` 三行加空行，
        ``id`` 为递增序号，供 ``Last-Event-ID`` 续传使用。

        副作用：创建并收尾执行记录（写库并提交）、成功后落库回答（写库并提交）。

        Args:
            body: ``ChatStreamRequest``
            conversation_id: 已落库的会话主键

        Yields:
            可直接写入 ``StreamingResponse`` 的 SSE 文本帧
        """
        started = perf_counter()
        seq = 0
        answer = ""
        failed = False
        settled = False  # 是否走到明确终态（final / error / 未捕获异常）
        error_message = ""

        try:
            request = await run_in_threadpool(self.prepare, body, conversation_id)
        except Exception as exc:
            logger.error("上下文装配失败", error=str(exc), conversation_id=conversation_id)
            yield render(ErrorEvent(message=f"上下文准备失败：{exc}"), 0)
            return

        # 必须在 prepare 成功之后创建记录：否则装配失败会留下永久 running 的记录，
        # 那时 finally 尚未建立
        recorder = AgentRunRecorder()
        request.run_id = recorder.start(
            space_id=int(body.space_id),
            environment_id=getattr(body, "environment_id", None),
            conversation_id=conversation_id or None,
            mode=request.mode,
            title=(body.instruction or "").strip().replace("\n", " ")[:50],
        )

        try:
            async for event in run_agent(request, recorder=recorder):
                if isinstance(event, FinalEvent):
                    answer = event.answer
                    settled = True
                elif isinstance(event, ErrorEvent):
                    failed = True
                    settled = True
                    error_message = event.message
                yield render(event, seq)
                seq += 1
        except Exception as exc:  # runner 内部已处理大多数异常，这里兜底
            logger.error("流式执行失败", error=str(exc), conversation_id=conversation_id)
            error_message = str(exc)
            failed = True
            settled = True
            yield render(ErrorEvent(message=str(exc)), seq)
        finally:
            # 客户端断流时本块在 GeneratorExit 状态下执行：不能 await（抛 CancelledError）、
            # 不能 yield（抛 RuntimeError）、不能外抛（覆盖 GeneratorExit）；settled=False 记为 cancelled
            try:
                recorder.finish(
                    status=("cancelled" if not settled else ("failed" if failed else "completed")),
                    error_message=error_message,
                )
            except Exception:  # finish 内部已吞异常，这里防未知错误影响后续收尾
                logger.warning("执行记录收尾异常", conversation_id=conversation_id)

            try:
                if settled and not failed:
                    self.save_answer(conversation_id, answer)
                logger.info(
                    "对话流结束",
                    conversation_id=conversation_id,
                    mode=request.mode,
                    run_id=request.run_id,
                    events=seq,
                    failed=failed,
                    settled=settled,
                    duration_ms=int((perf_counter() - started) * 1000),
                )
            except Exception:
                logger.warning("对话收尾落库异常", conversation_id=conversation_id)
