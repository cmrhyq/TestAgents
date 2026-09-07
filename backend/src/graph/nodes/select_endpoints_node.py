"""接口挑选节点实现。

使用 LangGraph ToolNode 模式进行 LLM Tool Calling。
select_endpoints_agent_node 作为 LLM 调用节点，配合 ToolNode 在图中形成循环。
"""

import json
import re
from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from src.core.llm.llm_gateway import get_llm_gateway
from src.core.logging import get_logger
from src.graph.state import AgentState
from src.graph.tools.db_tools import get_space_endpoints, search_space
from src.prompts.builders.select_endpoints_builder import SelectEndpointsBuilder

logger = get_logger(__name__)

AVAILABLE_TOOLS = [search_space, get_space_endpoints]


def select_endpoints_agent_node(state: AgentState) -> dict:
    """接口挑选 Agent 节点。

    将用户请求和系统提示词组装为 messages，调用绑定了工具的 LLM。
    LLM 可能返回 tool_calls（由 ToolNode 处理）或最终文本答案。

    注意：必须经 gateway.invoke_with_tools 调用（内部桥接 ainvoke），
    直接 model.bind_tools().invoke() 走同步 Router.completion，
    smart-router（auto_router/complexity_router）会炸 Unmapped provider。

    Args:
        state: 当前 AgentState（含 messages）

    Returns:
        部分状态更新，包含新的 messages
    """
    logger.info("进入接口挑选Agent节点", node="select_endpoints_agent")

    gateway = get_llm_gateway()

    if not state.get("messages"):
        builder = SelectEndpointsBuilder()
        messages_dicts = builder.build_messages(state["raw_input"])
        messages: list[BaseMessage] = [
            SystemMessage(content=messages_dicts[0]["content"]),
            HumanMessage(content=messages_dicts[1]["content"]),
        ]
        logger.debug(f"初始化消息列表，共{len(messages)}条", node="select_endpoints_agent", message_count=len(messages))
        response = gateway.invoke_with_tools(messages, AVAILABLE_TOOLS)
        return {"messages": messages + [response]}
    else:
        existing_messages: list[BaseMessage] = list(state["messages"])
        logger.debug(
            f"继续对话循环，消息数: {len(existing_messages)}",
            node="select_endpoints_agent",
            message_count=len(existing_messages),
        )
        response = gateway.invoke_with_tools(existing_messages, AVAILABLE_TOOLS)
        return {"messages": [response]}


def parse_endpoints_result_node(state: AgentState) -> dict:
    """从 Agent 最终响应中提取选中的接口信息。

    Args:
        state: 当前 AgentState

    Returns:
        部分状态更新，包含 selected_endpoints
    """
    logger.info("解析接口挑选结果", node="parse_result")

    messages = state.get("messages", [])
    if not messages:
        logger.warning("无消息可解析", node="parse_result")
        return {"selected_endpoints": []}

    last_message = messages[-1]
    final_content = last_message.content if hasattr(last_message, "content") else ""

    if not final_content:
        logger.warning("最终消息内容为空", node="parse_result")
        return {"selected_endpoints": []}

    if isinstance(final_content, list):
        final_content = "".join(part if isinstance(part, str) else str(part) for part in final_content)

    logger.debug(f"LLM最终输出: {final_content[:200]}", node="parse_result", content_length=len(final_content))
    selected = _parse_selected_endpoints(final_content)
    logger.info(f"接口挑选完成，选中{len(selected)}个接口", node="parse_result", count=len(selected))
    return {"selected_endpoints": selected}


def _parse_selected_endpoints(response: str) -> list[dict[str, Any]]:
    """从 LLM 最终响应中解析选中的接口信息。

    采用分层策略：优先从 markdown code block 提取，回退用花括号配对。

    Args:
        response: LLM 最终输出文本

    Returns:
        选中的接口列表
    """
    code_block_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", response)
    if code_block_match:
        try:
            data = json.loads(code_block_match.group(1))
            return _build_endpoint_list(data)
        except json.JSONDecodeError:
            pass

    start = response.find('"selected_endpoint_ids"')
    if start == -1:
        logger.warning("LLM响应中未找到selected_endpoint_ids字段", node="parse_result")
        return []

    brace_start = response.rfind("{", 0, start)
    if brace_start == -1:
        logger.warning("LLM响应中未找到JSON起始位置", node="parse_result")
        return []

    depth = 0
    for i in range(brace_start, len(response)):
        if response[i] == "{":
            depth += 1
        elif response[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    data = json.loads(response[brace_start : i + 1])
                    return _build_endpoint_list(data)
                except json.JSONDecodeError:
                    break

    logger.warning("LLM响应JSON解析失败", node="parse_result")
    return []


def _build_endpoint_list(data: dict[str, Any]) -> list[dict[str, Any]]:
    """从解析后的 JSON 数据构建接口列表。

    Args:
        data: 包含 selected_endpoint_ids 等字段的字典

    Returns:
        选中的接口列表
    """
    endpoint_ids = data.get("selected_endpoint_ids", [])
    if not endpoint_ids:
        return []

    space_id = data.get("space_id")
    space_name = data.get("space_name", "")
    reason = data.get("reason", "")

    return [
        {
            "endpoint_id": eid,
            "space_id": space_id,
            "space_name": space_name,
            "reason": reason,
        }
        for eid in endpoint_ids
    ]
