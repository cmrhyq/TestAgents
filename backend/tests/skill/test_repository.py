"""`SkillRepository` 的内置与空间两级技能发现。

空间级 `workspaces/{id}/.skills/` 覆盖同名内置技能；`space_id=None` 时只扫描内置目录。
"""

import pytest

from src.skill.repository import SkillRepository
from src.workspace.manager import WorkspaceManager

SPACE_ID = 555


def _write_skill(root, name: str, description: str = "desc", body: str = "正文") -> None:
    """在 `root` 下写入一个最小可解析的技能目录。"""
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\n{body}\n",
        encoding="utf-8",
    )


@pytest.fixture()
def repo(tmp_path) -> SkillRepository:
    """用临时目录构造仓库，内置根与工作区均与真实环境隔离。"""
    builtin = tmp_path / "skills"
    builtin.mkdir()
    return SkillRepository(builtin_root=builtin, workspace=WorkspaceManager(root=tmp_path / "workspaces"))


class TestDiscoverBuiltin:
    """内置技能发现，以及缺文件、坏文件的容错。"""

    def test_finds_skills_in_builtin_root(self, repo, tmp_path):
        _write_skill(tmp_path / "skills", "alpha")
        _write_skill(tmp_path / "skills", "beta")

        skills = repo.discover(space_id=None)

        assert [s.manifest.name for s in skills] == ["alpha", "beta"]
        assert all(s.scope == "builtin" for s in skills)

    def test_skips_directories_without_skill_md(self, repo, tmp_path):
        _write_skill(tmp_path / "skills", "alpha")
        (tmp_path / "skills" / "not-a-skill").mkdir()
        (tmp_path / "skills" / "not-a-skill" / "README.md").write_text("x", encoding="utf-8")

        assert [s.manifest.name for s in repo.discover(space_id=None)] == ["alpha"]

    def test_skips_invalid_skill_md_without_crashing(self, repo, tmp_path):
        _write_skill(tmp_path / "skills", "alpha")
        bad = tmp_path / "skills" / "broken"
        bad.mkdir()
        (bad / "SKILL.md").write_text("没有 frontmatter", encoding="utf-8")

        assert [s.manifest.name for s in repo.discover(space_id=None)] == ["alpha"]

    def test_missing_builtin_root_returns_empty(self, tmp_path):
        repo = SkillRepository(
            builtin_root=tmp_path / "not-exists",
            workspace=WorkspaceManager(root=tmp_path / "workspaces"),
        )
        assert repo.discover(space_id=None) == []


class TestDiscoverSpace:
    """空间级技能发现及与内置技能的同名覆盖关系。"""

    def test_finds_space_skills(self, repo, tmp_path):
        repo.workspace.create(SPACE_ID, "s")
        space_skills = tmp_path / "workspaces" / str(SPACE_ID) / ".skills"
        space_skills.mkdir(parents=True)
        _write_skill(space_skills, "space-only")

        skills = repo.discover(space_id=SPACE_ID)

        assert [s.manifest.name for s in skills] == ["space-only"]
        assert skills[0].scope == "space"

    def test_space_overrides_builtin_with_same_name(self, repo, tmp_path):
        _write_skill(tmp_path / "skills", "shared", description="内置版本")
        repo.workspace.create(SPACE_ID, "s")
        space_skills = tmp_path / "workspaces" / str(SPACE_ID) / ".skills"
        space_skills.mkdir(parents=True)
        _write_skill(space_skills, "shared", description="空间版本")

        skills = repo.discover(space_id=SPACE_ID)

        assert len(skills) == 1
        assert skills[0].manifest.description == "空间版本"
        assert skills[0].scope == "space"

    def test_builtin_visible_alongside_space_skills(self, repo, tmp_path):
        _write_skill(tmp_path / "skills", "builtin-one")
        repo.workspace.create(SPACE_ID, "s")
        space_skills = tmp_path / "workspaces" / str(SPACE_ID) / ".skills"
        space_skills.mkdir(parents=True)
        _write_skill(space_skills, "space-one")

        names = {s.manifest.name for s in repo.discover(space_id=SPACE_ID)}

        assert names == {"builtin-one", "space-one"}

    def test_no_space_id_only_scans_builtin(self, repo, tmp_path):
        _write_skill(tmp_path / "skills", "builtin-one")
        repo.workspace.create(SPACE_ID, "s")
        space_skills = tmp_path / "workspaces" / str(SPACE_ID) / ".skills"
        space_skills.mkdir(parents=True)
        _write_skill(space_skills, "space-one")

        names = {s.manifest.name for s in repo.discover(space_id=None)}

        assert names == {"builtin-one"}


class TestFind:
    """按名查找，空间级优先于内置。"""

    def test_finds_by_name(self, repo, tmp_path):
        _write_skill(tmp_path / "skills", "alpha")

        found = repo.find("alpha", space_id=None)

        assert found is not None
        assert found.manifest.name == "alpha"

    def test_unknown_name_returns_none(self, repo):
        assert repo.find("nope", space_id=None) is None

    def test_find_prefers_space_scope(self, repo, tmp_path):
        _write_skill(tmp_path / "skills", "shared", description="内置版本")
        repo.workspace.create(SPACE_ID, "s")
        space_skills = tmp_path / "workspaces" / str(SPACE_ID) / ".skills"
        space_skills.mkdir(parents=True)
        _write_skill(space_skills, "shared", description="空间版本")

        assert repo.find("shared", space_id=SPACE_ID).manifest.description == "空间版本"
        assert repo.find("shared", space_id=None).manifest.description == "内置版本"


class TestInstallDir:
    """导入技能时的目标目录。"""

    def test_space_install_dir_created(self, repo, tmp_path):
        target = repo.install_dir(SPACE_ID)

        assert target.name == ".skills"
        assert target.is_dir()
        assert target.parent == tmp_path / "workspaces" / str(SPACE_ID)

    def test_builtin_install_dir(self, repo, tmp_path):
        assert repo.install_dir(None) == tmp_path / "skills"
