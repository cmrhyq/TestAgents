from sqlalchemy.orm import Session

from src.core.logging import get_logger
from src.data.models.base import local_now
from src.data.models.conversation import Conversation
from src.data.models.message import Message
from src.data.repositories import (
    AgentRunRepository,
    AgentToolCallRepository,
    ConversationRepository,
    MessageRepository,
)
from src.data.schemas.conversation import ConversationCreate
from src.data.services.base_service import BaseService

logger = get_logger(__name__)

_TITLE_MAX_LEN = 30


def _dump_skill_names(names: list[str] | None) -> str:
    """把 skill 名列表转为入库用的 JSON 字符串。

    Args:
        names: skill 名列表，可为 None

    Returns:
        JSON 数组字符串，已去除空项与首尾空白
    """
    import json

    cleaned = [str(name).strip() for name in (names or []) if str(name).strip()]
    return json.dumps(cleaned, ensure_ascii=False)


class ConversationService(BaseService[Conversation, ConversationRepository]):
    """会话业务逻辑：创建会话、追加消息并维护会话元数据。"""

    def __init__(self, session: Session) -> None:
        """绑定会话与会话、消息、执行记录三个仓储。

        Args:
            session: 调用方持有的会话
        """
        self._session = session
        self.conv_repo = ConversationRepository(session)
        self.msg_repo = MessageRepository(session)
        self.run_repo = AgentRunRepository(session)
        self.tool_call_repo = AgentToolCallRepository(session)
        super().__init__(session, self.conv_repo)

    def list_conversations(self, space_id: int | None, status: int | None, page: int, page_size: int):
        """按空间与状态分页查询会话。

        排序为最近消息时间倒序，无消息时间的会话排在其后，再按创建时间倒序。

        Args:
            space_id: 空间主键；None 表示全部空间
            status: 状态过滤；None 表示不过滤
            page: 页码，从 1 开始
            page_size: 每页条数

        Returns:
            当前页会话列表与总数
        """
        filters = []
        if space_id is not None:
            filters.append(Conversation.space_id == space_id)
        if status is not None:
            filters.append(Conversation.status == status)
        return self.conv_repo.paginate(
            page,
            page_size,
            *filters,
            order_by=[Conversation.last_message_at.desc().nullslast(), Conversation.created_at.desc()],
        )

    def get_with_messages(self, conversation_id: int) -> Conversation | None:
        """取会话及其全部消息。

        Args:
            conversation_id: 会话主键

        Returns:
            会话实体；不存在时返回 None
        """
        return self.conv_repo.get_with_messages(conversation_id)

    def list_messages(self, conversation_id: int) -> list[Message]:
        """按会话取消息列表，按创建时间升序。

        Args:
            conversation_id: 会话主键

        Returns:
            消息列表；无消息时返回空列表
        """
        return self.msg_repo.list_by_conversation(conversation_id)

    def update_conversation(self, conversation_id: int, fields: dict) -> Conversation:
        """更新会话字段，``skill_names`` 与 ``mode`` 在落库前归一化。

        副作用：写库（未提交），需调用方提交事务。

        Args:
            conversation_id: 会话主键
            fields: 待更新字段；``mode`` 归一化为 ``agent`` / ``ask`` / ``plan``

        Returns:
            更新后的会话

        Raises:
            NotFoundError: 会话不存在
        """
        if "skill_names" in fields:
            fields["skill_names"] = _dump_skill_names(fields["skill_names"])
        if "mode" in fields and fields["mode"] is not None:
            from src.agent.modes import normalize_mode

            fields["mode"] = normalize_mode(fields["mode"]).value
        return self.update(conversation_id, **fields)

    def delete_conversation(self, conversation_id: int) -> None:
        """删除会话及其消息、执行记录与工具调用留痕。

        ``agent_run.conversation_id`` 刻意不建外键（会话创建失败时执行记录仍需写入），
        所以数据库不会替我们级联；不显式清理就会留下指向已删会话的孤儿记录。
        删除顺序固定为「先留痕、后执行记录」：留痕按 ``run_id`` 归属，执行记录一旦先删，
        就再也查不到这批 ``run_id`` 了。

        ``llm_log`` 不清理：其 ``space_id`` / ``conversation_id`` / ``run_id`` 同样
        不建外键，成本历史需要在对象删除后继续保留。

        副作用：写库（未提交），需调用方提交事务。执行中的（``running``）记录也会
        一并删除，该轮后续的留痕写入会因外键失败而被记录器吞掉（只记日志、不打断对话）。

        Args:
            conversation_id: 会话主键

        Raises:
            NotFoundError: 会话不存在
        """
        self.get_or_raise(conversation_id, "会话不存在")

        run_ids = self.run_repo.list_ids_by_conversation(conversation_id)
        deleted_tool_calls = self.tool_call_repo.delete_by_run_ids(run_ids)
        deleted_runs = self.run_repo.delete_by_ids(run_ids)

        self.delete(conversation_id)

        if deleted_runs or deleted_tool_calls:
            logger.info(
                "会话及其执行记录已删除",
                conversation_id=conversation_id,
                deleted_runs=deleted_runs,
                deleted_tool_calls=deleted_tool_calls,
            )

    def create_conversation(self, data: ConversationCreate) -> Conversation:
        """创建会话，``mode`` 先归一化再落库。

        库上存在 ``CHECK (mode IN ('agent','ask','plan'))``，未归一化的取值会直接
        触发约束错误，因此在服务层统一处理。

        副作用：写库（未提交），需调用方提交事务。

        Args:
            data: 会话创建参数

        Returns:
            新建的会话实体

        Raises:
            IntegrityError: 归一化后仍不满足数据库约束
        """
        from src.agent.modes import normalize_mode

        conversation = Conversation(
            space_id=data.space_id,
            title=data.title or "",
            mode=normalize_mode(data.mode).value,
            skill_names=_dump_skill_names(data.skill_names),
            environment_id=data.environment_id,
        )
        return self.conv_repo.add(conversation)

    def append_message(
        self,
        conversation_id: int,
        role: str,
        content: str,
        meta: str = "{}",
    ) -> Message:
        """向会话追加一条消息，并同步会话元数据。

        副作用：写库（未提交），需调用方提交事务；同时更新会话的
        ``last_message_at`` 与 ``updated_at``；会话标题为空且本条为 ``user``
        消息时，按内容截断生成标题。

        Args:
            conversation_id: 会话主键
            role: 消息角色，``user`` 时可能触发标题生成
            content: 消息正文
            meta: 附加元数据，JSON 字符串

        Returns:
            新建的消息实体
        """
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            meta=meta,
        )
        self.msg_repo.add(message)

        now = local_now()
        conversation = self.conv_repo.get_by_id(conversation_id)
        if conversation is not None:
            conversation.last_message_at = now
            conversation.updated_at = now
            if role == "user" and not conversation.title:
                conversation.title = self._make_title(content)
            self.conv_repo.update_entity(conversation)

        return message

    @staticmethod
    def _make_title(content: str) -> str:
        """由消息内容生成会话标题，合并空白并截断。

        Args:
            content: 消息正文

        Returns:
            标题，超长时截断并追加省略号；内容为空时返回 ``新对话``
        """
        normalized = " ".join(content.split()).strip()
        if len(normalized) > _TITLE_MAX_LEN:
            return normalized[:_TITLE_MAX_LEN] + "…"
        return normalized or "新对话"
