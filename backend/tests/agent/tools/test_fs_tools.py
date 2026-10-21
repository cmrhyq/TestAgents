"""空间沙箱文件工具测试。

核心关注：**任何路径都不能逃出空间目录**。
工具被 LLM 调用，参数来自模型输出——模型完全可能被诱导去读 ``../../.env``，
所以沙箱必须在工具层强制，而不是靠 prompt 里写「请不要读工作区外的文件」。
"""

from __future__ import annotations

import pytest

from src.agent.tools.fs_tools import make_fs_tools
from src.workspace.manager import WorkspaceManager

SPACE_ID = 6001


@pytest.fixture()
def space(tmp_path) -> WorkspaceManager:
    manager = WorkspaceManager(root=tmp_path / "workspaces")
    manager.create(SPACE_ID, "沙箱空间")
    return manager


@pytest.fixture()
def tools(space) -> dict:
    return {tool.name: tool for tool in make_fs_tools(space_id=SPACE_ID, workspace=space)}


class TestReadFile:
    def test_reads_relative_path(self, tools, space):
        space.resolve(SPACE_ID, "notes.md").write_text("内容", encoding="utf-8")

        assert tools["read_file"].invoke({"path": "notes.md"}) == "内容"

    def test_returns_error_for_missing_file(self, tools):
        result = tools["read_file"].invoke({"path": "nope.md"})
        assert "不存在" in result

    def test_rejects_parent_escape(self, tools):
        result = tools["read_file"].invoke({"path": "../../secret.txt"})
        assert "越出" in result or "绝对路径" in result

    def test_rejects_absolute_path(self, tools):
        result = tools["read_file"].invoke({"path": "/etc/passwd"})
        assert "绝对路径" in result or "越出" in result

    def test_truncates_large_file(self, tools, space):
        big = "x" * (300 * 1024)
        space.resolve(SPACE_ID, "big.txt").write_text(big, encoding="utf-8")

        result = tools["read_file"].invoke({"path": "big.txt"})

        assert "截断" in result
        assert len(result) < len(big)


class TestWriteFile:
    def test_writes_file(self, tools, space):
        tools["write_file"].invoke({"path": "artifacts/out.md", "content": "结果"})

        assert space.resolve(SPACE_ID, "artifacts/out.md").read_text(encoding="utf-8") == "结果"

    def test_creates_parent_dirs(self, tools, space):
        tools["write_file"].invoke({"path": "testcases/deep/a.md", "content": "x"})

        assert space.resolve(SPACE_ID, "testcases/deep/a.md").is_file()

    def test_rejects_escape(self, tools, tmp_path):
        result = tools["write_file"].invoke({"path": "../evil.md", "content": "x"})

        assert "越出" in result or "绝对路径" in result
        assert not (tmp_path / "workspaces" / "evil.md").exists()

    def test_rejects_oversized_content(self, tools):
        result = tools["write_file"].invoke({"path": "big.md", "content": "x" * (2 * 1024 * 1024)})
        assert "过大" in result


class TestListDirectory:
    def test_lists_entries(self, tools):
        result = tools["list_directory"].invoke({"path": "."})

        assert "AGENTS.md" in result
        assert "docs" in result

    def test_skips_noisy_dirs(self, tools, space):
        (space.resolve(SPACE_ID, "__pycache__")).mkdir()

        assert "__pycache__" not in tools["list_directory"].invoke({"path": "."})

    def test_missing_dir_returns_error(self, tools):
        assert "不存在" in tools["list_directory"].invoke({"path": "nope"})


class TestDeleteFile:
    def test_deletes_file(self, tools, space):
        target = space.resolve(SPACE_ID, "tmp.md")
        target.write_text("x", encoding="utf-8")

        tools["delete_file"].invoke({"path": "tmp.md"})

        assert not target.exists()

    def test_refuses_to_delete_protected(self, tools, space):
        """核心约定文件不允许被 Agent 删掉。"""
        result = tools["delete_file"].invoke({"path": "AGENTS.md"})

        assert "不允许" in result
        assert space.resolve(SPACE_ID, "AGENTS.md").is_file()

    def test_refuses_to_delete_directory(self, tools, space):
        assert "目录" in tools["delete_file"].invoke({"path": "docs"})

    def test_rejects_escape(self, tools):
        assert "越出" in tools["delete_file"].invoke({"path": "../../x"})
