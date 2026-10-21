"""SKILL.md 清单解析。

Skill 包格式刻意对齐市面 Agent Skills 规范（``---`` YAML frontmatter + Markdown 正文），
这样别人写的 skill 直接拷进目录就能用，不需要转换。

解析器只做「校验 + 拆分」，**不做任何业务判断**——skill 该不该参与本轮对话、
工具要不要取交集，都由 ``SkillService`` 与 ``agent.modes`` 决定。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import yaml

# 市面规范：小写字母/数字/连字符，不允许下划线与大写（长度 1-64）
_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")

_FRONTMATTER_DELIMITER = "---"


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
            max_chars: 正文上限；超限截断并显式标注，避免悄悄丢掉后半部分
                （用户排障时必须知道「Agent 只看到了一半」）。
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
    if not _NAME_PATTERN.match(name):
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
    """拆出 frontmatter 与正文。"""
    stripped = (text or "").lstrip("\ufeff")
    if not stripped.startswith(_FRONTMATTER_DELIMITER):
        raise SkillManifestError("SKILL.md 必须以 '---' 包裹的 frontmatter 开头")

    lines = stripped.splitlines()
    closing = None
    for index in range(1, len(lines)):
        if lines[index].strip() == _FRONTMATTER_DELIMITER:
            closing = index
            break

    if closing is None:
        raise SkillManifestError("frontmatter 未闭合（缺少结束的 '---'）")

    frontmatter = "\n".join(lines[1:closing])
    body = "\n".join(lines[closing + 1 :])
    return frontmatter, body


def _load_yaml(frontmatter: str) -> dict:
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
    """把 allowed_tools 归一化为字符串列表（容忍字符串/列表/缺失）。"""
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
