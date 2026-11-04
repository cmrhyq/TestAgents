"""Pytest 全局配置：项目路径、临时目录与 LLM mock fixture。

`_env_setup` 为 autouse，逐用例设置 `LLMTESTAGENT_ENV=test` 并重定向报告目录，
避免测试读写真实配置。
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
    """替换 `get_llm_gateway`，返回预设 `chat` 结果的 mock 客户端。"""
    with patch("src.core.llm.llm_gateway.get_llm_gateway") as mock_get:
        client = MagicMock()
        client.chat.return_value = '{"intent": "run", "test_mode": "single"}'
        mock_get.return_value = client
        yield client


@pytest.fixture()
def mock_chat_model():
    """替换 `select_endpoints_node` 依赖的 `get_llm_gateway`。

    `select_endpoints_node` 现经 gateway 调用，不再直接持有 ChatModel。
    """
    with patch("src.graph.nodes.select_endpoints_node.get_llm_gateway") as mock_get:
        gateway = MagicMock()
        mock_get.return_value = gateway
        yield gateway


@pytest.fixture(autouse=True)
def _env_setup(monkeypatch):
    """将环境标记为 test，并把报告输出目录指向临时目录。"""
    monkeypatch.setenv("LLMTESTAGENT_ENV", "test")
