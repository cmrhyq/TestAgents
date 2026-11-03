"""`WorkspaceManager` 的目录创建、路径沙箱、归档与目录树。

全部使用 `tmp_path`，不读写真实工作区目录。
"""

from pathlib import Path

import pytest

from src.workspace.manager import PathEscapeError, WorkspaceManager

SPACE_ID = 1234567890


@pytest.fixture()
def manager(tmp_path) -> WorkspaceManager:
    """指向临时根目录的管理器。"""
    return WorkspaceManager(root=tmp_path / "workspaces")


class TestCreate:
    """目录创建与初始文件，重复调用不覆盖已有文件。"""

    def test_creates_full_structure(self, manager):
        space_dir = manager.create(SPACE_ID, "用户中心")

        assert space_dir.is_dir()
        assert space_dir.name == str(SPACE_ID)
        assert (space_dir / "AGENTS.md").is_file()
        assert (space_dir / "memory" / "MEMORY.md").is_file()
        assert (space_dir / "docs" / "README.md").is_file()
        assert (space_dir / "testcases").is_dir()
        assert (space_dir / "artifacts").is_dir()

    def test_agents_md_contains_space_name(self, manager):
        space_dir = manager.create(SPACE_ID, "用户中心")
        content = (space_dir / "AGENTS.md").read_text(encoding="utf-8")

        assert "用户中心" in content

    def test_ensure_is_idempotent(self, manager):
        first = manager.create(SPACE_ID, "用户中心")
        agents = first / "AGENTS.md"
        agents.write_text("用户自定义内容", encoding="utf-8")

        second = manager.create(SPACE_ID, "用户中心")

        assert second == first
        # 已存在的文件不能被覆盖
        assert agents.read_text(encoding="utf-8") == "用户自定义内容"

    def test_ensure_creates_when_missing(self, manager):
        space_dir = manager.ensure(SPACE_ID)
        assert (space_dir / "AGENTS.md").is_file()


class TestResolve:
    """路径沙箱：绝对路径与 `..` 逃逸均被拒绝。"""

    def test_resolves_relative_path_inside_root(self, manager):
        manager.create(SPACE_ID, "s")

        resolved = manager.resolve(SPACE_ID, "docs/README.md")

        assert resolved == (manager.space_dir(SPACE_ID) / "docs" / "README.md").resolve()

    def test_rejects_absolute_path(self, manager):
        with pytest.raises(PathEscapeError):
            manager.resolve(SPACE_ID, "/etc/passwd")

    def test_rejects_windows_absolute_path(self, manager):
        with pytest.raises(PathEscapeError):
            manager.resolve(SPACE_ID, "C:\\Windows\\win.ini")

    def test_rejects_parent_escape(self, manager):
        with pytest.raises(PathEscapeError):
            manager.resolve(SPACE_ID, "../../secret.txt")

    def test_rejects_nested_escape(self, manager):
        with pytest.raises(PathEscapeError):
            manager.resolve(SPACE_ID, "docs/../../../outside.txt")

    def test_allows_current_dir_reference(self, manager):
        manager.create(SPACE_ID, "s")
        resolved = manager.resolve(SPACE_ID, "./docs")
        assert resolved == (manager.space_dir(SPACE_ID) / "docs").resolve()


class TestArchive:
    """空间删除时的目录归档。"""

    def test_archive_renames_directory(self, manager):
        space_dir = manager.create(SPACE_ID, "s")

        archived = manager.archive(SPACE_ID)

        assert archived is not None
        assert archived.exists()
        assert not space_dir.exists()
        assert archived.name.startswith(".deleted-")

    def test_archive_missing_returns_none(self, manager):
        assert manager.archive(SPACE_ID) is None


class TestTree:
    """目录树：条目元数据、噪声目录过滤与深度限制。"""

    def test_tree_lists_entries_with_metadata(self, manager):
        manager.create(SPACE_ID, "s")

        tree = manager.tree(SPACE_ID)

        names = {node["name"] for node in tree}
        assert {"AGENTS.md", "memory", "docs", "testcases", "artifacts"} <= names

        agents = next(node for node in tree if node["name"] == "AGENTS.md")
        assert agents["type"] == "file"
        assert agents["size"] > 0

        docs = next(node for node in tree if node["name"] == "docs")
        assert docs["type"] == "dir"
        assert {c["name"] for c in docs["children"]} == {"README.md"}

    def test_tree_skips_noisy_dirs(self, manager):
        space_dir = manager.create(SPACE_ID, "s")
        (space_dir / "__pycache__").mkdir()
        (space_dir / ".git").mkdir()

        names = {node["name"] for node in manager.tree(SPACE_ID)}

        assert "__pycache__" not in names
        assert ".git" not in names

    def test_tree_respects_max_depth(self, manager):
        space_dir = manager.create(SPACE_ID, "s")
        deep = space_dir / "artifacts" / "a" / "b"
        deep.mkdir(parents=True)
        (deep / "x.txt").write_text("x", encoding="utf-8")

        tree = manager.tree(SPACE_ID, max_depth=1)

        artifacts = next(node for node in tree if node["name"] == "artifacts")
        assert artifacts["children"] == []
