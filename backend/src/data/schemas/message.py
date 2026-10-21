from pydantic import BaseModel, Field


class MessageBase(BaseModel):
    """Message 基础字段"""

    role: str = Field(..., description="角色: user / assistant / system")
    content: str = Field(default="", description="消息内容")
    meta: str = Field(default="{}", description="附加信息(JSON字符串): token/附件路径/run_id 等")


class MessageCreate(MessageBase):
    """创建 Message 请求体"""


class MessageResponse(MessageBase):
    """Message 响应体"""

    id: int = Field(..., description="消息ID")
    conversation_id: int = Field(..., description="所属会话ID")
    created_at: str = Field(..., description="创建时间")

    model_config = {"from_attributes": True}


class MessageListResponse(BaseModel):
    """Message 列表响应"""

    items: list[MessageResponse] = Field(default=[], description="消息列表")
    total: int = Field(default=0, description="总数")
