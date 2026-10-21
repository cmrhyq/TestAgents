from sqlalchemy.orm import Session

from src.data.models.base import local_now
from src.data.models.conversation import Conversation
from src.data.models.message import Message
from src.data.repositories import ConversationRepository, MessageRepository
from src.data.schemas.conversation import ConversationCreate
from src.data.services.base_service import BaseService

_TITLE_MAX_LEN = 30


def _dump_skill_names(names: list[str] | None) -> str:
    """skill 名列表 → DB 里的 JSON 字符串。"""
    import json

    cleaned = [str(name).strip() for name in (names or []) if str(name).strip()]
    return json.dumps(cleaned, ensure_ascii=False)


class ConversationService(BaseService[Conversation, ConversationRepository]):
    """会话业务逻辑：创建会话、追加消息并维护会话元数据。"""

    def __init__(self, session: Session) -> None:
        self._session = session
        self.conv_repo = ConversationRepository(session)
        self.msg_repo = MessageRepository(session)
        super().__init__(session, self.conv_repo)

    def list_conversations(self, space_id: int | None, status: int | None, page: int, page_size: int):
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
        return self.conv_repo.get_with_messages(conversation_id)

    def list_messages(self, conversation_id: int) -> list[Message]:
        return self.msg_repo.list_by_conversation(conversation_id)

    def update_conversation(self, conversation_id: int, fields: dict) -> Conversation:
        """更新会话字段；``skill_names`` 与 ``mode`` 做落库前归一化。"""
        if "skill_names" in fields:
            fields["skill_names"] = _dump_skill_names(fields["skill_names"])
        if "mode" in fields and fields["mode"] is not None:
            from src.agent.modes import normalize_mode

            fields["mode"] = normalize_mode(fields["mode"]).value
        return self.update(conversation_id, **fields)

    def delete_conversation(self, conversation_id: int) -> None:
        self.delete(conversation_id)

    def create_conversation(self, data: ConversationCreate) -> Conversation:
        """创建新会话。

        ``mode`` 必须归一化：DB 上有 ``CHECK (mode IN ('agent','ask','plan'))``，
        前端或旧客户端传 ``Ask`` 会直接撞约束——在服务层挡住比在数据库层爆炸好。
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
        """向会话追加一条消息，并更新会话的 last_message_at/updated_at；

        若会话标题为空且为首条 user 消息，则用内容截断生成标题。
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
        """从消息内容生成会话标题（去除换行并截断）。"""
        normalized = " ".join(content.split()).strip()
        if len(normalized) > _TITLE_MAX_LEN:
            return normalized[:_TITLE_MAX_LEN] + "…"
        return normalized or "新对话"
