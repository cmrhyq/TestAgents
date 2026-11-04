"""Skills 管理路由：列表、详情、导入与启停。

skill 内容以文件为真源，本层只读写启用状态与安装目录；
空间级同名 skill 覆盖内置 skill。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.core.errors import NotFoundError, ValidationError
from src.skill.registry import SkillRegistry
from src.skill.service import SkillImportError, get_skill_service

router = APIRouter(prefix="/skills", tags=["技能管理"])

# 单个 skill 包上限 20MB
MAX_ZIP_BYTES = 20 * 1024 * 1024


class SkillItem(BaseModel):
    """skill 列表项。"""

    name: str
    description: str
    when_to_use: str = ""
    version: str = ""
    scope: str
    directory: str
    allowed_tools: list[str] = Field(default_factory=list)
    enabled: bool = True


class SkillListResponse(BaseModel):
    items: list[SkillItem]
    total: int
    space_id: str | None = None


class SkillDetail(SkillItem):
    """skill 详情（含正文）。"""

    body: str


class SkillToggleBody(BaseModel):
    """启停请求体。"""

    enabled: bool


@router.get("", response_model=SkillListResponse)
def list_skills(
    space_id: int | None = Query(default=None, description="空间 ID；不传则只返回内置 skill"),
    db: Session = Depends(get_db),
):
    """列出可见 skill，并同步其目录与描述等元信息。

    副作用：把发现的 skill 元信息同步进 ``skill`` 表（只更新已有行）。

    Args:
        space_id: 空间 ID；不传则只返回内置 skill
        db: 请求级数据库会话

    Returns:
        skill 列表与总数，每项带启用状态
    """
    service = get_skill_service()
    skills = service.list_skills(space_id)
    registry = SkillRegistry(db)
    registry.sync(skills, space_id)
    enabled_map = registry.enabled_map(space_id)

    items = [
        SkillItem(
            name=skill.name,
            description=skill.manifest.description,
            when_to_use=skill.manifest.when_to_use,
            version=skill.manifest.version,
            scope=skill.scope,
            directory=skill.display_path,
            allowed_tools=skill.manifest.allowed_tools,
            enabled=enabled_map.get(skill.name, True),
        )
        for skill in skills
    ]
    return SkillListResponse(items=items, total=len(items), space_id=str(space_id) if space_id else None)


@router.get("/{name}", response_model=SkillDetail)
def get_skill(
    name: str,
    space_id: int | None = Query(default=None, description="空间 ID"),
    db: Session = Depends(get_db),
):
    """查询单个 skill 详情，含 SKILL.md 正文。

    Args:
        name: skill 名，需符合小写字母/数字/连字符规则
        space_id: 空间 ID，用于空间级覆盖
        db: 请求级数据库会话

    Returns:
        skill 详情与启用状态

    Raises:
        NotFoundError: skill 不存在，返回 HTTP 404
    """
    skill = get_skill_service().find(name, space_id)
    if skill is None:
        raise NotFoundError(f"skill 不存在: {name}")

    return SkillDetail(
        name=skill.name,
        description=skill.manifest.description,
        when_to_use=skill.manifest.when_to_use,
        version=skill.manifest.version,
        scope=skill.scope,
        directory=skill.display_path,
        allowed_tools=skill.manifest.allowed_tools,
        enabled=SkillRegistry(db).is_enabled(name, space_id),
        body=skill.manifest.body,
    )


@router.post("/import", response_model=SkillListResponse)
async def import_skill(
    file: UploadFile = File(..., description="skill 包（zip，内含 SKILL.md）"),
    space_id: int | None = Query(default=None, description="安装到哪个空间；不传则装进内置库"),
    db: Session = Depends(get_db),
):
    """导入 zip 包中的 skill，一个包可含多个 skill。

    副作用：解压落盘到目标目录（同名目录先删后写），并写入启用状态；
    条目路径越界时整包拒绝。

    Args:
        file: skill 包，zip 格式，每个 skill 一个目录并含 SKILL.md
        space_id: 安装到指定空间；不传则装进内置库
        db: 请求级数据库会话

    Returns:
        导入后该可见范围内的 skill 列表

    Raises:
        ValidationError: 包过大、非法 zip、无 SKILL.md 或含越界路径，返回 HTTP 422
    """
    data = await file.read()
    if len(data) > MAX_ZIP_BYTES:
        raise ValidationError(f"skill 包过大，上限 {MAX_ZIP_BYTES // 1024 // 1024}MB")

    try:
        installed = get_skill_service().import_zip(data, space_id=space_id)
    except SkillImportError as exc:
        raise ValidationError(str(exc)) from exc

    registry = SkillRegistry(db)
    for name in installed:
        registry.set_enabled(name, space_id, True, scope="space")

    return list_skills(space_id=space_id, db=db)


@router.patch("/{name}", response_model=SkillItem)
def toggle_skill(
    name: str,
    body: SkillToggleBody,
    space_id: int | None = Query(default=None, description="空间 ID"),
    db: Session = Depends(get_db),
):
    """启用或禁用某个 skill。

    副作用：写 ``skill`` 表。

    Args:
        name: skill 名
        body: 目标启用状态
        space_id: 空间 ID；不传则改全局默认
        db: 请求级数据库会话

    Returns:
        更新后的 skill 列表项

    Raises:
        NotFoundError: skill 不存在，返回 HTTP 404
    """
    skill = get_skill_service().find(name, space_id)
    if skill is None:
        raise NotFoundError(f"skill 不存在: {name}")

    registry = SkillRegistry(db)
    registry.set_enabled(
        name,
        space_id,
        body.enabled,
        scope=skill.scope,
        directory=skill.display_path,
    )

    return SkillItem(
        name=skill.name,
        description=skill.manifest.description,
        when_to_use=skill.manifest.when_to_use,
        version=skill.manifest.version,
        scope=skill.scope,
        directory=skill.display_path,
        allowed_tools=skill.manifest.allowed_tools,
        enabled=body.enabled,
    )
