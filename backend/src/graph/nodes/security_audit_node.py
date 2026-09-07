"""
用户输入安全审计节点（API 前置守卫，非工作流图节点）

审计用户的输入，判断用户的prompt是否涉及安全问题以及是否不是API测试的内容。
由 ``api/v1/chat.py`` 在流式对话前调用，**不要**加入 ``build_graph()``。
"""

from src.core.llm.llm_gateway import get_llm_gateway
from src.core.logging import get_logger
from data.constant.constants import NodeName
from src.graph.state import AgentState
from src.prompts.builders.system_safety import SystemSafetyBuilder

logger = get_logger(__name__)


def security_audit_node(state: AgentState) -> dict:
    """用户输入安全审计节点

    Args:
        state: 当前工作流状态

    Returns:
        正常时返回 ``{"next_node": NodeName.END, "audit_result": ...}``，
        异常时返回 ``{"next_node": NodeName.ERROR, "error_message": ...}``
    """
    logger.info(
        f"进入Prompt安全审计节点，用户指令: {state['raw_input'][:80]}",
        node="security_audit",
        raw_input=state["raw_input"],
    )

    try:
        builder = SystemSafetyBuilder()
        messages = builder.build_messages(state["raw_input"])

        llm_client = get_llm_gateway()
        response = llm_client.chat(messages)

        logger.info(f"Prompt安全审计响应：: {response}", node="security_audit")
        return {"next_node": NodeName.END.value, "audit_result": response}
    except Exception as e:
        error_msg = f"Prompt安全审计异常：{str(e)}"
        logger.error(f"Prompt安全审计失败，拦截此次会话请求：{e}", node="security_audit", error=str(e))
        return {"next_node": NodeName.ERROR.value, "error_message": error_msg}
