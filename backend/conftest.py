"""
Pytest 全局配置和 fixtures。

提供测试所需的通用 fixture（项目路径、临时目录、mock 配置等）。
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

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


@pytest.fixture()
def mock_llm_client():
    """Mock LLM 客户端，避免测试中真实调用 LLM API。"""
    with patch("src.core.llm.llm_gateway.get_llm_gateway") as mock_get:
        client = MagicMock()
        client.chat.return_value = '{"intent": "run", "test_mode": "single"}'
        mock_get.return_value = client
        yield client


@pytest.fixture()
def mock_chat_model():
    """Mock LangChain ChatModel（select_endpoints_node 现经 gateway 调用）。"""
    with patch("src.graph.nodes.select_endpoints_node.get_llm_gateway") as mock_get:
        gateway = MagicMock()
        mock_get.return_value = gateway
        yield gateway


@pytest.fixture(autouse=True)
def _env_setup(tmp_path, monkeypatch):
    """确保测试环境不读取真实配置，使用临时目录存放输出。"""
    monkeypatch.setenv("LLMTESTAGENT_ENV", "test")
    monkeypatch.setenv("REPORT_OUTPUT_DIR", str(tmp_path / "reports"))
