"""工作流层常量与枚举。

集中定义工作流专用的节点名、用户意图、测试模式枚举，
替换散落在 route.py / workflow.py / 各节点中的魔法字符串。
数据状态（``DataStatus`` 等）仍位于 ``src.data.enum.workflow``。
"""

from enum import Enum


class UserIntent(str, Enum):
    """用户意图。"""

    RUN = "run"  # 运行 API 测试
    AGENT = "agent"
    ASK = "ask"  # 提问
    PLAN = "plan"


class TestMode(str, Enum):
    """测试模式。"""

    SINGLE = "single"  # 单接口测试
    FLOW = "flow"  # 业务流程测试


class NodeName(str, Enum):
    """工作流图节点名。

    值即 LangGraph ``add_node`` / 条件边使用的字符串，保持与既有图结构一致。
    """

    AGENT = "agent"  # LLM 决策节点：产出文本回答或工具调用请求
    TOOLS = "tools"  # 工具执行节点：LangGraph ToolNode 统一执行工具
