"""校验 pytest 配置、项目目录结构与核心模块导入可用性。"""

import pytest


class TestPytestSetup:
    """验证 pytest 环境配置正确。"""

    def test_space_root_exists(self, project_root):
        assert project_root.exists()
        assert (project_root / "pyproject.toml").exists()

    def test_source_layout_exists(self, project_root):
        """核心包目录应存在。"""
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
        """四大子系统可各自独立导入，用于暴露循环依赖。"""
        from src.memory import get_knowledge_base, get_long_term_memory
        from src.skill.service import get_skill_service
        from src.workspace.manager import get_workspace_manager

        assert get_long_term_memory is not None
        assert get_knowledge_base is not None
        assert get_skill_service is not None
        assert get_workspace_manager is not None


@pytest.mark.unit
class TestImportConventions:
    """第一方模块必须统一用 ``src.`` 前缀导入。

    背景：``pyproject.toml`` 曾经把 ``src`` 也塞进 pytest 的 ``pythonpath``，
    于是 ``from data.constant.agent import ...`` 这种裸导入在测试里能跑，
    但 ``python app.py`` / ``uvicorn app:app`` 没有这层路径注入，启动时
    直接 ``ModuleNotFoundError: No module named 'data'``——线上第一次真跑
    才发现，排查成本极高。

    现在 pythonpath 只保留项目根目录，并由本用例在静态层面兜住：
    任何裸导入 ``data.`` / ``core.`` / ``agent.`` 等都会被判红。
    """

    #: src/ 下的顶层包名，裸导入它们一定是错的
    FIRST_PARTY = frozenset({"agent", "api", "core", "data", "memory", "skill", "utils", "workspace"})

    @classmethod
    def _offenders(cls, root) -> list[str]:
        import ast

        found: list[str] = []
        for path in sorted(root.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    # level > 0 是相对导入（from .data import x），不受影响
                    if node.level == 0 and (node.module or "").split(".")[0] in cls.FIRST_PARTY:
                        found.append(f"{path}:{node.lineno} from {node.module}")
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.split(".")[0] in cls.FIRST_PARTY:
                            found.append(f"{path}:{node.lineno} import {alias.name}")
        return found

    def test_src_has_no_bare_first_party_imports(self, project_root):
        offenders = self._offenders(project_root / "src")

        assert offenders == [], "以下导入缺少 src. 前缀，会导致 python app.py 启动失败:\n" + "\n".join(
            offenders
        )

    def test_tests_have_no_bare_first_party_imports(self, project_root):
        offenders = self._offenders(project_root / "tests")

        assert offenders == [], "测试代码同样要写全 src. 前缀:\n" + "\n".join(offenders)

    def test_app_entry_imports_without_pytest_path_injection(self, project_root):
        """用 ``python -c "import app"`` 真跑一次入口导入。

        这是对上面静态检查的补充：静态检查漏掉的动态导入（``importlib``、
        ``__import__``）只有真导入才暴露得出来。子进程不加载 pytest 配置，
        等价于 ``uvicorn app:app`` 的启动环境。
        """
        import subprocess
        import sys

        result = subprocess.run(
            [sys.executable, "-c", "import app"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=120,
        )

        assert result.returncode == 0, f"入口导入失败:\n{result.stderr}"
