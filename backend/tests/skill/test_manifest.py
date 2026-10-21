"""SKILL.md frontmatter 解析测试。

Skill 包格式对齐市面 Agent Skills 规范：
``---`` 包裹的 YAML frontmatter + Markdown 正文。
"""

import pytest

from src.skill.manifest import SkillManifestError, parse_skill_md

VALID = """---
name: api-test-design
description: 为一组接口设计测试场景矩阵
when_to_use: 当用户要求为某组接口设计测试用例时
version: 1.0.0
allowed_tools: [get_space_endpoints, get_endpoint_detail]
---

# 方法论

第一步：拉取接口清单。
"""

MINIMAL = """---
name: quick-check
description: 快速检查
---

正文
"""


class TestParseValid:
    def test_parses_all_fields(self):
        manifest = parse_skill_md(VALID)

        assert manifest.name == "api-test-design"
        assert manifest.description == "为一组接口设计测试场景矩阵"
        assert manifest.when_to_use == "当用户要求为某组接口设计测试用例时"
        assert manifest.version == "1.0.0"
        assert manifest.allowed_tools == ["get_space_endpoints", "get_endpoint_detail"]
        assert "第一步：拉取接口清单。" in manifest.body

    def test_body_excludes_frontmatter(self):
        manifest = parse_skill_md(VALID)

        assert "name: api-test-design" not in manifest.body
        assert manifest.body.lstrip().startswith("# 方法论")

    def test_optional_fields_default_empty(self):
        manifest = parse_skill_md(MINIMAL)

        assert manifest.when_to_use == ""
        assert manifest.version == ""
        assert manifest.allowed_tools == []

    def test_allowed_tools_accepts_yaml_list(self):
        text = """---
name: a-b
description: d
allowed_tools:
  - tool_a
  - tool_b
---
body
"""
        assert parse_skill_md(text).allowed_tools == ["tool_a", "tool_b"]


class TestParseInvalid:
    def test_missing_frontmatter(self):
        with pytest.raises(SkillManifestError, match="frontmatter"):
            parse_skill_md("# 只有正文\n没有元数据")

    def test_unclosed_frontmatter(self):
        with pytest.raises(SkillManifestError, match="frontmatter"):
            parse_skill_md("---\nname: a-b\ndescription: d\n")

    def test_missing_name(self):
        with pytest.raises(SkillManifestError, match="name"):
            parse_skill_md("---\ndescription: d\n---\nbody")

    def test_missing_description(self):
        with pytest.raises(SkillManifestError, match="description"):
            parse_skill_md("---\nname: a-b\n---\nbody")

    def test_invalid_name_format(self):
        with pytest.raises(SkillManifestError, match="name"):
            parse_skill_md("---\nname: Bad_Name\ndescription: d\n---\nbody")

    def test_invalid_yaml(self):
        with pytest.raises(SkillManifestError):
            parse_skill_md("---\nname: [unclosed\ndescription: d\n---\nbody")

    def test_non_mapping_frontmatter(self):
        with pytest.raises(SkillManifestError):
            parse_skill_md("---\n- just\n- a\n- list\n---\nbody")


class TestInjection:
    """注入 system prompt 的文本形态。"""

    def test_to_prompt_block_wraps_body(self):
        manifest = parse_skill_md(VALID)
        block = manifest.to_prompt_block()

        assert block.startswith('<skill name="api-test-design"')
        assert block.rstrip().endswith("</skill>")

    def test_to_prompt_block_truncates(self):
        manifest = parse_skill_md(VALID)
        block = manifest.to_prompt_block(max_chars=5)

        assert "截断" in block
        assert len(block) < len(manifest.body) + 200

    def test_to_prompt_block_keeps_short_body_intact(self):
        manifest = parse_skill_md(VALID)
        block = manifest.to_prompt_block(max_chars=len(manifest.body))

        assert "截断" not in block
        assert manifest.body.strip() in block
