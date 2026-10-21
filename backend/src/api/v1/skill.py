"""Skills 管理路由。

- ``GET  /skills``            列出可见 skill（内置 + 空间），带启用状态
- ``GET  /skills/{name}``     详情（含 SKILL.md 正文，供前端详情抽屉）
- ``POST /skills/import``     导入 zip 包
- ``PATCH /skills/{name}``    启用 / 禁用
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

# 单个 skill 包上限：够放文档与脚本，又不至于让人把整个仓库塞进来
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
    """列出可见 skill。空间级同名 skill 会覆盖内置。"""
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
    """获取单个 skill 详情（含 SKILL.md 正文）。"""
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
    """导入 zip 包形式的 skill。

    一个 zip 可以包含多个 skill（每个 skill 一个目录）。
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
    """启用或禁用某个 skill。"""
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
