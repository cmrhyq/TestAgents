from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.data.models.base import Base, local_now
from src.utils.id import next_id

if TYPE_CHECKING:
    pass


class Skill(Base):
    """Skill 注册表。

    **内容真源是文件系统**（``SKILL.md``），本表只存「发现结果 + 启用开关」：
    - 每次都从文件读正文，避免 DB 与文件不一致
    - ``enabled`` 是用户意志，重启后要保留，所以必须落库
    """

    __tablename__ = "skill"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False, default=next_id)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    # builtin=随代码分发的内置库 space=空间私有（优先级更高，同名覆盖内置）
    scope: Mapped[str] = mapped_column(Text, nullable=False, default="builtin")
    space_id: Mapped[int | None] = mapped_column(Integer, default=None)
    # 相对 backend 根的目录，如 skills/api-test-design
    directory: Mapped[str] = mapped_column(Text, nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    when_to_use: Mapped[str] = mapped_column(Text, nullable=False, default="")
    version: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # JSON 数组；为空表示不限制（仍受模式白名单约束）
    allowed_tools: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    discovered_at: Mapped[str] = mapped_column(Text, nullable=False, default=local_now)

    __table_args__ = (
        CheckConstraint("scope IN ('builtin','space')", name="ck_skill_scope"),
        CheckConstraint("enabled IN (0,1)", name="ck_skill_enabled"),
        Index("idx_skill_scope", "scope", "space_id"),
        Index("idx_skill_name", "name"),
    )
