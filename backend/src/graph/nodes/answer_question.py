"""回答问题节点。

承载原 ``ChatStreamService.generate_stream`` 的完整编排逻辑：
1. 安全审计（``security_audit_node``）+ 分流判断（拦截 / 非测试内容 / 放行）
2. 加载会话历史，组装 LLM messages
3. 调用 LLM 生成完整回答，写入 ``answer_content``
4. 把 assistant 消息落库

与 ``security_audit_node`` 相同，本节点由 ``api/v1/chat.py`` 直接调用
（对话不走测试主流程的 ``build_graph()``），保持 text/plain 流式协议。
"""

from collections.abc import Callable
from typing import cast

from data.constant.constants import NodeName
from src.core.database.database_manager import get_db_manager
from src.core.llm.llm_gateway import get_llm_gateway
from src.core.logging import get_logger
from src.data.services.conversation_service import ConversationService
from src.graph import AgentState
from src.graph.nodes.security_audit_node import security_audit_node
from src.prompts.loader import get_loader
from src.utils.json_utils import parse_llm_json_object

logger = get_logger(__name__)

# 审计/生成异常时返回给用户的兜底提示（测试引用此常量）
AUDIT_ERROR_MESSAGE = "抱歉，处理您的请求时发生错误，请稍后重试。"
# 命中安全风险 / 非 API 测试内容的提示（测试引用）
SECURITY_RISK_MESSAGE = "⚠️ 检测到您的输入存在安全风险，无法处理该请求。请调整后重试。"
NON_TESTING_MESSAGE = "抱歉，我只处理 API 测试相关的内容，无法回答 API 测试以外的问题。"


# --------------------------------------------------------------------------
# 纯判断函数
# --------------------------------------------------------------------------

def is_blocked_by_security(audit: dict) -> bool:
    """根据审计结果判断是否命中安全风险。

    同时兼容 security_analysis.is_safe 布尔字段与 overall_verdict.action，
    任一命中风险即视为拦截。
    """
    security = audit.get("security_analysis") or {}
    verdict = audit.get("overall_verdict") or {}
    if security.get("is_safe") is False:
        return True
    return verdict.get("action") == "block"


def is_non_testing(audit: dict) -> bool:
    """根据审计结果判断是否为非 API 测试内容。"""
    api_testing = audit.get("api_testing_analysis") or {}
    return api_testing.get("is_api_testing") is False


# --------------------------------------------------------------------------
# 会话持久化
# --------------------------------------------------------------------------

def load_history(conversation_id: int) -> list[dict[str, str]]:
    """加载会话的历史消息，转为 LLM messages 格式（仅 user/assistant）。"""
    try:
        with get_db_manager().get_session() as session:
            messages = ConversationService(session).list_messages(conversation_id)
            return [{"role": m.role, "content": m.content} for m in messages if m.role in ("user", "assistant")]
    except RuntimeError as exc:
        logger.warning("会话历史暂不可用，使用空历史", error=str(exc))
        return []


def save_assistant_message(conversation_id: int, content: str) -> None:
    """把 assistant 回复落库。"""
    try:
        with get_db_manager().get_session() as session:
            ConversationService(session).append_message(conversation_id, role="assistant", content=content)
    except RuntimeError as exc:
        logger.warning("assistant 消息持久化暂不可用", error=str(exc))


def answer_question_node(
    state: AgentState,
    audit_func: Callable[[AgentState], dict] | None = None,
    llm_client_factory: Callable | None = None,
) -> dict:
    """回答问题节点：安全审计分流 + 会话历史 + LLM 生成 + assistant 消息落库。

    Args:
        state: 当前工作流状态，需包含 ``raw_input`` 与 ``conversation_id``
        audit_func: 安全审计可调用对象（默认 ``security_audit_node``），测试可注入
        llm_client_factory: 返回 LLM 客户端的工厂（默认 ``get_llm_gateway``），测试可注入

    Returns:
        部分状态更新，包含 ``answer_content`` 与 ``next_node``；
        审计/生成异常时 ``next_node`` 为 ``ERROR`` 并携带 ``error_message``。
    """
    logger.info(
        f"进入回答问题节点，用户指令: {state['raw_input'][:80]}",
        node=NodeName.ANSWER_QUESTION.value,
        raw_input=state["raw_input"],
    )

    raw_input = state["raw_input"]
    conversation_id = state.get("conversation_id")
    audit = audit_func or security_audit_node
    llm_client_factory = llm_client_factory or (lambda: get_llm_gateway())

    # 1) 安全审计分流
    try:
        audit_state = audit(cast(AgentState, cast(object, {"raw_input": raw_input})))

        if audit_state.get("next_node") == NodeName.ERROR.value:
            logger.warning("安全审计节点返回异常，拦截请求", error=audit_state.get("error_message", ""))
            return {
                "answer_content": AUDIT_ERROR_MESSAGE,
                "next_node": NodeName.END.value,
            }

        parsed_audit = parse_llm_json_object(audit_state.get("audit_result", ""))
        if not parsed_audit:
            logger.warning("安全审计结果解析为空，出于安全考虑拦截请求")
            return {
                "answer_content": AUDIT_ERROR_MESSAGE,
                "next_node": NodeName.END.value,
            }

        if is_blocked_by_security(parsed_audit):
            logger.info(
                "Prompt 命中安全风险，拦截",
                summary=(parsed_audit.get("security_analysis") or {}).get("summary", ""),
            )
            return {
                "answer_content": SECURITY_RISK_MESSAGE,
                "next_node": NodeName.END.value,
            }

        if is_non_testing(parsed_audit):
            logger.info("Prompt 非 API 测试内容，拒绝处理")
            return {
                "answer_content": NON_TESTING_MESSAGE,
                "next_node": NodeName.END.value,
            }
    except Exception as e:
        logger.error("回答问题节点安全审计失败", node=NodeName.ANSWER_QUESTION.value, error=str(e))
        return {
            "answer_content": AUDIT_ERROR_MESSAGE,
            "next_node": NodeName.END.value,
            "error_message": f"Answer Question Node 安全审计异常: {str(e)}",
        }

    # 2) 通过审计，加载历史并生成回答
    try:
        logger.info("Prompt 通过安全审计且为测试内容，进入大模型回答")
        messages: list[dict[str, str]] = [{"role": "system", "content": get_loader().load_simple_prompt_sync("chat_assistant_system.yaml")}]
        if conversation_id:
            messages.extend(load_history(conversation_id))

        llm_client = llm_client_factory()
        answer = llm_client.chat(messages)

        if conversation_id:
            save_assistant_message(conversation_id, answer)

        return {"answer_content": answer, "next_node": NodeName.END.value}
    except Exception as e:
        logger.error(
            f"Answer Question Node 异常: {e}",
            node=NodeName.ANSWER_QUESTION.value,
            error=str(e),
            default_intent="ask",
            default_mode="single",
        )
        return {
            "next_node": NodeName.ERROR.value,
            "error_message": f"Answer Question Node 异常: {str(e)}",
        }
