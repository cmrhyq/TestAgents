import json

from pydantic import BaseModel, Field, field_validator

from src.data.schemas.common import PaginatedResponse
from src.data.schemas.message import MessageResponse


class ConversationBase(BaseModel):
    """Conversation 基础字段"""

    space_id: int | None = Field(default=None, description="所属空间ID（可空）")
    title: str = Field(default="", description="会话标题")
    mode: str = Field(default="agent", description="工作模式: agent / ask / plan")
    skill_names: list[str] = Field(default_factory=list, description="本会话选中的 skill 名")
    environment_id: int | None = Field(default=None, description="会话绑定的测试环境 ID")

    @field_validator("skill_names", mode="before")
    @classmethod
    def _parse_skill_names(cls, value):
        """DB 里存的是 JSON 字符串，接口对外暴露为数组。

        在 schema 层转换而不是模型层：ORM 保持「原样存什么读什么」，
        序列化格式属于 API 契约的事。
        """
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except (ValueError, TypeError):
                return []
            return [str(item) for item in parsed] if isinstance(parsed, list) else []
        return value or []


class ConversationCreate(ConversationBase):
    """创建 Conversation 请求体"""

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "space_id": None,
                    "title": "",
                    "mode": "ask",
                    "skill_names": ["api-test-design"],
                }
            ]
        }
    }


class ConversationUpdate(BaseModel):
    """更新 Conversation 请求体（所有字段可选）"""

    title: str | None = Field(default=None, description="会话标题")
    mode: str | None = Field(default=None, description="工作模式: agent / ask / plan")
    skill_names: list[str] | None = Field(default=None, description="本会话选中的 skill 名")
    environment_id: int | None = Field(default=None, description="会话绑定的测试环境 ID")
    status: int | None = Field(default=None, description="状态: 1-正常, 0-删除")


class ConversationResponse(ConversationBase):
    """Conversation 响应体"""

    id: int = Field(..., description="会话ID")
    status: int = Field(..., description="状态: 1-正常, 0-删除")
    last_message_at: str | None = Field(default=None, description="最后一条消息时间")
    created_at: str = Field(..., description="创建时间")
    updated_at: str = Field(..., description="更新时间")

    model_config = {"from_attributes": True}


class ConversationDetail(ConversationResponse):
    """Conversation 详情响应（含消息列表）"""

    messages: list[MessageResponse] = Field(default=[], description="消息列表")

    model_config = {"from_attributes": True}


class ConversationListResponse(PaginatedResponse[ConversationResponse]):
    """Conversation 列表响应"""


class ChatStreamRequest(BaseModel):
    """流式对话请求体。

    ``mode`` 只接受 ``agent`` / ``ask`` / ``plan``。历史值（``Run``/``Ask``/``Plan``）
    在服务层由 ``normalize_mode`` 兜底归一化，避免旧前端直接 422。
    """

    instruction: str = Field(..., min_length=1, description="用户输入的 prompt")
    conversation_id: int | None = Field(default=None, description="会话 ID；缺省时自动新建会话")
    space_id: int | None = Field(default=None, description="所属测试空间 ID")
    mode: str = Field(default="agent", description="工作模式: agent / ask / plan")
    skill_names: list[str] = Field(default_factory=list, description="选中的 skill 名")
    environment_id: int | None = Field(default=None, description="指定测试环境 ID")
