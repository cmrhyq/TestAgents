from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from src.data.models.conversation import Conversation
from src.data.repositories.base import BaseRepository


class ConversationRepository(BaseRepository[Conversation]):
    """会话表数据访问。"""

    def __init__(self, session: Session) -> None:
        """绑定会话模型。

        Args:
            session: 调用方持有的会话
        """
        super().__init__(Conversation, session)

    def get_with_messages(self, conversation_id: int) -> Conversation | None:
        """取会话及其全部消息，消息一次性预加载。

        Args:
            conversation_id: 会话主键

        Returns:
            会话实体，消息按创建时间升序；会话不存在时返回 None
        """
        stmt = (
            select(Conversation).where(Conversation.id == conversation_id).options(selectinload(Conversation.messages))
        )
        return self._session.scalar(stmt)
