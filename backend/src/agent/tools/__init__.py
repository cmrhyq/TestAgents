"""Agent 工具集。

工具按「能力域 + 空间绑定」组织：所有需要知道当前空间的工具都由 ``make_*_tools``
闭包工厂产出，``space_id`` 不出现在工具参数里，避免模型编造 ID。

工具分两类，这个区分是模式策略的物理基础：

- **只读**：``db_tools`` / ``fs_tools.read_file`` / ``knowledge_tools`` /
  ``memory_tools.recall`` / ``skill_tools`` / ``executor_tools``
- **有副作用**：``http_tools.send_request`` / ``fs_tools.write_file`` /
  ``fs_tools.delete_file`` / ``memory_tools.remember`` / ``memory_tools.forget``
"""

from src.agent.tools.assertion_engine import AssertionEngine
from src.agent.tools.jsonpath import extract_jsonpath

__all__ = [
    "AssertionEngine",
    "extract_jsonpath",
]
