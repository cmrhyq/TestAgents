from pydantic import BaseModel, Field


class MessageBase(BaseModel):
    """消息基础字段。"""

    role: str = Field(..., description="角色：user / assistant / system")
    content: str = Field(default="", description="消息正文")
    meta: str = Field(default="{}", description="附加信息，JSON 对象字符串，可含 token 用量、附件路径、run_id")


class MessageCreate(MessageBase):
    """创建消息请求体。"""


class MessageResponse(MessageBase):
    """消息响应体。"""

    id: int = Field(..., description="消息 ID")
    conversation_id: int = Field(..., description="所属会话 ID")
    created_at: str = Field(..., description="创建时间")

    model_config = {"from_attributes": True}


class MessageListResponse(BaseModel):
    """消息列表响应。"""

    items: list[MessageResponse] = Field(default=[], description="消息列表")
    total: int = Field(default=0, description="记录总数")
