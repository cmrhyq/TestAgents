from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from src.data.models.conversation import Conversation
from src.data.repositories.base import BaseRepository


class ConversationRepository(BaseRepository[Conversation]):
    """会话表数据访问"""

    def __init__(self, session: Session) -> None:
        super().__init__(Conversation, session)

    def get_with_messages(self, conversation_id: int) -> Conversation | None:
        """获取会话及其全部消息（按消息创建时间升序加载）。"""
        stmt = (
            select(Conversation).where(Conversation.id == conversation_id).options(selectinload(Conversation.messages))
        )
        return self._session.scalar(stmt)
