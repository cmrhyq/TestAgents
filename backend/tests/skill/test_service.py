"""`SkillService` 的 zip 导入与 prompt 装配。

zip 条目需防 zip-slip（`../` 与绝对路径），且只接受含合法 `SKILL.md` 的包。
"""

import io
import zipfile

import pytest

from src.skill.service import SkillImportError, SkillService
from src.workspace.manager import WorkspaceManager

SPACE_ID = 777


def _make_zip(entries: dict[str, str]) -> bytes:
    """把 `{路径: 内容}` 打成 zip 字节。"""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name, content in entries.items():
            zf.writestr(name, content)
    return buffer.getvalue()


def _skill_md(name: str, description: str = "desc", body: str = "正文") -> str:
    """生成最小可解析的 `SKILL.md` 文本。"""
    return f"---\nname: {name}\ndescription: {description}\n---\n\n{body}\n"


@pytest.fixture()
def service(tmp_path) -> SkillService:
    """用临时目录构造服务，内置根与工作区相互隔离。"""
    builtin = tmp_path / "skills"
    builtin.mkdir()
    return SkillService(
        builtin_root=builtin,
        workspace=WorkspaceManager(root=tmp_path / "workspaces"),
    )


class TestImportZip:
    """zip 导入：单技能与多技能、参考文件复制、各类非法包拒绝。"""

    def test_imports_single_skill(self, service, tmp_path):
        data = _make_zip({"my-skill/SKILL.md": _skill_md("my-skill")})

        installed = service.import_zip(data, space_id=SPACE_ID)

        assert installed == ["my-skill"]
        target = tmp_path / "workspaces" / str(SPACE_ID) / ".skills" / "my-skill" / "SKILL.md"
        assert target.is_file()

    def test_imports_multiple_skills(self, service):
        data = _make_zip(
            {
                "a/SKILL.md": _skill_md("skill-a"),
                "b/SKILL.md": _skill_md("skill-b"),
            }
        )

        assert sorted(service.import_zip(data, space_id=SPACE_ID)) == ["skill-a", "skill-b"]

    def test_copies_reference_files(self, service, tmp_path):
        data = _make_zip(
            {
                "s/SKILL.md": _skill_md("s"),
                "s/references/notes.md": "参考资料",
            }
        )

        service.import_zip(data, space_id=SPACE_ID)

        assert (tmp_path / "workspaces" / str(SPACE_ID) / ".skills" / "s" / "references" / "notes.md").is_file()

    def test_rejects_zip_without_skill_md(self, service):
        data = _make_zip({"readme.txt": "hello"})

        with pytest.raises(SkillImportError):
            service.import_zip(data, space_id=SPACE_ID)

    def test_rejects_zip_slip_parent_escape(self, service, tmp_path):
        data = _make_zip({"../evil/SKILL.md": _skill_md("evil")})

        with pytest.raises(SkillImportError):
            service.import_zip(data, space_id=SPACE_ID)

        assert not (tmp_path / "workspaces" / "evil").exists()

    def test_rejects_absolute_path_entry(self, service):
        data = _make_zip({"/abs/SKILL.md": _skill_md("abs")})

        with pytest.raises(SkillImportError):
            service.import_zip(data, space_id=SPACE_ID)

    def test_rejects_invalid_skill_md(self, service):
        data = _make_zip({"bad/SKILL.md": "没有 frontmatter"})

        with pytest.raises(SkillImportError):
            service.import_zip(data, space_id=SPACE_ID)

    def test_rejects_non_zip_bytes(self, service):
        with pytest.raises(SkillImportError):
            service.import_zip(b"not a zip", space_id=SPACE_ID)

    def test_install_dir_follows_frontmatter_name(self, service, tmp_path):
        """目录名与 frontmatter `name` 不一致时以 `name` 为准，避免同一技能出现两个名字。"""
        data = _make_zip({"weird-dir/SKILL.md": _skill_md("real-name")})

        assert service.import_zip(data, space_id=SPACE_ID) == ["real-name"]
        assert (tmp_path / "workspaces" / str(SPACE_ID) / ".skills" / "real-name").is_dir()


class TestAssemble:
    """prompt 块装配与 `allowed_tools` 合并。"""

    def test_build_prompt_blocks_for_selected(self, service):
        data = _make_zip({"s/SKILL.md": _skill_md("s", body="方法论正文")})
        service.import_zip(data, space_id=SPACE_ID)

        block = service.build_prompt_blocks(["s"], space_id=SPACE_ID)

        assert '<skill name="s"' in block
        assert "方法论正文" in block

    def test_empty_selection_returns_empty_string(self, service):
        assert service.build_prompt_blocks([], space_id=SPACE_ID) == ""

    def test_unknown_skill_is_ignored(self, service):
        assert service.build_prompt_blocks(["ghost"], space_id=SPACE_ID) == ""

    def test_allowed_tools_union(self, service):
        data = _make_zip(
            {
                "x/SKILL.md": "---\nname: x\ndescription: d\nallowed_tools: [read_file, list_directory]\n---\nb\n",
                "y/SKILL.md": "---\nname: y\ndescription: d\nallowed_tools: [send_request]\n---\nb\n",
            }
        )
        service.import_zip(data, space_id=SPACE_ID)

        assert service.resolve_allowed_tools(["x", "y"], space_id=SPACE_ID) == {
            "read_file",
            "list_directory",
            "send_request",
        }

    def test_no_restriction_returns_none(self, service):
        """任一选中技能未声明 `allowed_tools`，整体不额外限制。"""
        data = _make_zip({"z/SKILL.md": _skill_md("z")})
        service.import_zip(data, space_id=SPACE_ID)

        assert service.resolve_allowed_tools(["z"], space_id=SPACE_ID) is None
