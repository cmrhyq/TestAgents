"""LangGraph 工作流状态定义。

使用 TypedDict + Annotated reducer 模式，符合 LangGraph 2026 规范。

字段约定：
- ``next_node``：仅用于条件边路由（值取自 ``src.graph.constants.NodeName``）
- ``run_status``：工作流整体运行状态（值取自 ``TestStatus``）
"""

from typing import TypedDict

from langgraph.graph import MessagesState


class SelectedEndpoint(TypedDict):
    """用户选中的单个接口。"""

    endpoint_id: int
    space_id: int | None
    space_name: str
    reason: str


class TestResultsSummary(TypedDict):
    """测试执行结果汇总。"""

    total: int
    passed: int
    failed: int
    skipped: int
    error: int
    pass_rate: float


class AgentState(MessagesState):
    """统一工作流状态。

    继承 MessagesState 自动包含 messages 字段（带 add_messages reducer）。
    包含所有节点需要的业务数据字段。
    """

    # 输入字段
    raw_input: str

    # 路由字段
    next_node: str
    run_status: str

    # 模型解析的流程字段
    user_intent: str  # UserIntent.value
    test_mode: str  # TestMode.value
    space_id: int | None  # 当前空间 ID（run 流程选接口/生成用例用）

    # 对话字段（answer_question_node 消费，API 层注入 conversation_id）
    answer_content: str  # 问答节点生成的完整回答文本
    conversation_id: int | None  # 会话 ID，用于加载历史 / 落库 assistant 消息

    # 业务字段
    selected_endpoints: list[SelectedEndpoint]
    endpoint_count: int
    run_id: int
    test_cases_count: int
    test_results_summary: TestResultsSummary
    report_path: str
    error_message: str

    # 安全审计结果（security_audit_node 写入，由 API 层消费）
    audit_result: str
