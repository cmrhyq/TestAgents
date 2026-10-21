"""Pytest 配置验证 — 确保基本配置和 fixture 正常工作。"""

import pytest


class TestPytestSetup:
    """验证 pytest 环境配置正确。"""

    def test_space_root_exists(self, project_root):
        assert project_root.exists()
        assert (project_root / "pyproject.toml").exists()

    def test_source_layout_exists(self, project_root):
        """重构后的核心包目录应存在。"""
        for pkg in ("src/agent", "src/data", "src/core", "src/api"):
            assert (project_root / pkg).is_dir(), f"缺少包目录: {pkg}"

    def test_env_is_test(self, monkeypatch):
        import os

        assert os.environ.get("LLMTESTAGENT_ENV") == "test"


@pytest.mark.unit
class TestImports:
    """验证核心模块可正常导入。"""

    def test_import_config(self):
        from src.core.config import AppConfig

        assert AppConfig is not None

    def test_import_agent_runtime(self):
        from src.agent.modes import policy_for
        from src.agent.runner import RunRequest, run

        assert RunRequest is not None
        assert run is not None
        assert policy_for("agent").allow_side_effects is True

    def test_import_openapi_parser(self):
        from src.utils.parser import OpenAPIParser

        assert OpenAPIParser is not None

    def test_import_subsystems(self):
        """四大子系统都要能独立导入（避免循环依赖）。"""
        from src.memory import get_knowledge_base, get_long_term_memory
        from src.skill.service import get_skill_service
        from src.workspace.manager import get_workspace_manager

        assert get_long_term_memory is not None
        assert get_knowledge_base is not None
        assert get_skill_service is not None
        assert get_workspace_manager is not None
