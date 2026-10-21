from sqlalchemy import select
from sqlalchemy.orm import Session

from src.data.models.message import Message
from src.data.repositories.base import BaseRepository


class MessageRepository(BaseRepository[Message]):
    """消息表数据访问"""

    def __init__(self, session: Session) -> None:
        super().__init__(Message, session)

    def list_by_conversation(self, conversation_id: int) -> list[Message]:
        """按会话查询消息列表，按创建时间升序。"""
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc(), Message.id.asc())
        )
        return list(self._session.scalars(stmt).all())
