"""SKILL.md 清单解析。

格式对齐通用 Agent Skills 规范：``---`` 包裹的 YAML frontmatter 加 Markdown 正文。
解析器只做校验与拆分，不参与 skill 选择或工具裁剪决策。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import yaml

from data.constant.skills import SKILL_NAME_PATTERN, SKILL_FRONTMATTER_DELIMITER


class SkillManifestError(ValueError):
    """SKILL.md 格式非法。"""


@dataclass(slots=True)
class SkillManifest:
    """一个 skill 的元数据与正文。"""

    name: str
    description: str
    body: str
    when_to_use: str = ""
    version: str = ""
    allowed_tools: list[str] = field(default_factory=list)

    def to_prompt_block(self, max_chars: int | None = None) -> str:
        """渲染为注入 system prompt 的文本块。

        Args:
            max_chars: 正文长度上限；超限截断并在文末标注截断位置，
                以便排障时知道正文未完整注入

        Returns:
            ``<skill>`` 标签包裹的文本块
        """
        body = self.body
        if max_chars is not None and len(body) > max_chars:
            body = body[:max_chars] + f"\n\n…（正文过长，已截断至 {max_chars} 字符）"

        header = f'<skill name="{self.name}"'
        if self.when_to_use:
            header += f' when_to_use="{_escape_attr(self.when_to_use)}"'
        header += ">"
        return f"{header}\n{body.strip()}\n</skill>"


def parse_skill_md(text: str) -> SkillManifest:
    """解析 SKILL.md 全文。

    Args:
        text: 文件内容

    Returns:
        SkillManifest

    Raises:
        SkillManifestError: 缺少 frontmatter、字段缺失或格式非法
    """
    frontmatter, body = _split_frontmatter(text)
    meta = _load_yaml(frontmatter)

    name = str(meta.get("name") or "").strip()
    if not name:
        raise SkillManifestError("SKILL.md 缺少必填字段 name")
    if not SKILL_NAME_PATTERN.match(name):
        raise SkillManifestError(
            f"name 格式非法: {name}（要求小写字母/数字/连字符，1-64 位，如 api-test-design）"
        )

    description = str(meta.get("description") or "").strip()
    if not description:
        raise SkillManifestError("SKILL.md 缺少必填字段 description")

    return SkillManifest(
        name=name,
        description=description,
        body=body.strip(),
        when_to_use=str(meta.get("when_to_use") or "").strip(),
        version=str(meta.get("version") or "").strip(),
        allowed_tools=_parse_allowed_tools(meta.get("allowed_tools")),
    )


def _split_frontmatter(text: str) -> tuple[str, str]:
    """拆出 frontmatter 与正文，开头 BOM 会被忽略。"""
    stripped = (text or "").lstrip("\ufeff")
    if not stripped.startswith(SKILL_FRONTMATTER_DELIMITER):
        raise SkillManifestError("SKILL.md 必须以 '---' 包裹的 frontmatter 开头")

    lines = stripped.splitlines()
    closing = None
    for index in range(1, len(lines)):
        if lines[index].strip() == SKILL_FRONTMATTER_DELIMITER:
            closing = index
            break

    if closing is None:
        raise SkillManifestError("frontmatter 未闭合（缺少结束的 '---'）")

    frontmatter = "\n".join(lines[1:closing])
    body = "\n".join(lines[closing + 1 :])
    return frontmatter, body


def _load_yaml(frontmatter: str) -> dict:
    """解析 frontmatter 为字典。

    Raises:
        SkillManifestError: YAML 非法、为空或不是键值映射
    """
    try:
        meta = yaml.safe_load(frontmatter)
    except yaml.YAMLError as exc:
        raise SkillManifestError(f"frontmatter 不是合法 YAML: {exc}") from exc

    if meta is None:
        raise SkillManifestError("frontmatter 为空")
    if not isinstance(meta, dict):
        raise SkillManifestError("frontmatter 必须是键值映射")
    return meta


def _parse_allowed_tools(raw: object) -> list[str]:
    """把 ``allowed_tools`` 归一化为字符串列表，容忍字符串、序列与缺失值。"""
    if not raw:
        return []
    if isinstance(raw, str):
        return [part.strip() for part in raw.split(",") if part.strip()]
    if isinstance(raw, (list, tuple, set)):
        return [str(item).strip() for item in raw if str(item).strip()]
    return []


def _escape_attr(value: str) -> str:
    """属性值里的引号与换行会破坏标签结构，需要转义。"""
    return value.replace('"', "'").replace("\n", " ")
