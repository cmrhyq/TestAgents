"""Pytest 全局配置：项目路径、临时目录与测试环境标记。

`_env_setup` 为 autouse，逐用例设置 `LLMTESTAGENT_ENV=test` 并重定向报告目录，
避免测试读写真实配置。
"""

from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def project_root() -> Path:
    """项目根目录路径。"""
    return Path(__file__).parent


@pytest.fixture(scope="session")
def input_dir(project_root) -> Path:
    """测试输入文件目录。"""
    return project_root / "input"


@pytest.fixture(scope="session")
def sample_openapi_file(input_dir) -> Path:
    """示例 OpenAPI JSON 文件路径。"""
    return input_dir / "test.json"


@pytest.fixture(autouse=True)
def _env_setup(monkeypatch):
    """将环境标记为 test，并把报告输出目录指向临时目录。"""
    monkeypatch.setenv("LLMTESTAGENT_ENV", "test")
