from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.data.models.base import Base, local_now
from src.utils.id import next_id

if TYPE_CHECKING:
    pass


class Skill(Base):
    """Skill 注册表 - 已发现的 skill 与启用开关。

    内容真源是文件系统中的 ``SKILL.md``，正文每次从文件读取；
    本表只存发现结果与用户的 ``enabled`` 选择，重启后需保留。
    """

    __tablename__ = "skill"

    # 主键，由 next_id() 生成，不走数据库自增
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False, default=next_id)
    # skill 名，与目录名一致；同名时 space 作用域覆盖 builtin
    name: Mapped[str] = mapped_column(Text, nullable=False)
    # 作用域：builtin-随代码分发的内置库，space-空间私有
    scope: Mapped[str] = mapped_column(Text, nullable=False, default="builtin")
    # 所属空间，space.id；builtin 作用域为 NULL，该列不建外键
    space_id: Mapped[int | None] = mapped_column(Integer, default=None)
    # skill 目录，相对 backend 根
    directory: Mapped[str] = mapped_column(Text, nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    when_to_use: Mapped[str] = mapped_column(Text, nullable=False, default="")
    version: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # 允许的工具名，JSON 数组字符串；空数组表示不额外限制
    allowed_tools: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    # 1-启用，0-禁用
    enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # 最近一次扫描发现该 skill 的时间
    discovered_at: Mapped[str] = mapped_column(Text, nullable=False, default=local_now)

    __table_args__ = (
        CheckConstraint("scope IN ('builtin','space')", name="ck_skill_scope"),
        CheckConstraint("enabled IN (0,1)", name="ck_skill_enabled"),
        Index("idx_skill_scope", "scope", "space_id"),
        Index("idx_skill_name", "name"),
    )
