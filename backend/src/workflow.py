"""测试工作流编排模块。

使用 LangGraph StateGraph 定义有状态工作流：
- parse_input: 意图解析
- select_endpoints: 接口挑选（Agent + ToolNode 循环）
- generate_single_cases: 单接口测试用例生成（LLM 驱动）
- generate_flow_cases: 流程测试用例生成（LLM 驱动）
- execute_single_tests: 单接口测试执行（HTTP 请求 + 断言）
- execute_flow_tests: 流程测试执行（顺序执行 + 上下文传递）
- generate_report: 报告生成

节点名与路由统一使用 ``src.graph.constants`` 中的枚举，
条件边由 ``src.graph.route`` 的注册表驱动。

流式能力：
- ``TestWorkflow.stream``：同步生成器，按节点产出结构化事件（CLI/脚本场景）
- ``TestWorkflow.astream``：异步生成器，按节点产出结构化事件（FastAPI SSE 首选）
- ``TestWorkflow.astream_events``：异步生成器，额外产出 LLM token 级增量

事件统一为 ``dict``，包含 ``type`` 字段：
``start`` / ``node`` / ``token`` / ``final`` / ``error``。
"""

import time
from collections.abc import AsyncIterator, Iterator
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from src.core.config import AppConfig, get_config
from src.core.logging import get_logger
from src.data.enum.workflow import TestStatus
from data.constant.constants import NodeName
from src.graph.nodes.answer_question import answer_question_node
from src.graph.nodes.end_node import end_node
from src.graph.nodes.error_node import error_node
from src.graph.nodes.execute_flow_tests_node import execute_flow_tests_node
from src.graph.nodes.execute_single_tests_node import execute_single_tests_node
from src.graph.nodes.generate_flow_cases_node import generate_flow_cases_node
from src.graph.nodes.generate_report_node import generate_report_node
from src.graph.nodes.generate_single_cases_node import generate_single_cases_node
from src.graph.nodes.parse_input_node import parse_input_node
from src.graph.nodes.select_endpoints_node import (
    AVAILABLE_TOOLS,
    parse_endpoints_result_node,
    select_endpoints_agent_node,
)
from src.graph.nodes.start_node import start_node
from src.graph.route import route_by_intent, route_by_next_node, route_by_test_mode
from src.graph.state import AgentState

logger = get_logger(__name__)


def _now() -> float:
    """当前时间戳（Unix 秒），用于事件记录。"""
    return time.time()


def _extract_token_text(chunk: Any) -> str:
    """从 LLM 输出 chunk 中提取纯文本增量。

    LangChain 的 AIMessageChunk.content 可能是 str 或 content block 列表，
    这里做统一兼容。

    Args:
        chunk: LLM 输出的消息块（通常为 AIMessageChunk）

    Returns:
        文本增量，无文本时返回空字符串
    """
    content = getattr(chunk, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
        return "".join(parts)
    return ""


def build_graph() -> CompiledStateGraph:
    """构建并编译测试工作流图。

    图结构:
        START -> parse_input

    Returns:
        编译后的 StateGraph
    """
    workflow = StateGraph(AgentState)

    workflow.add_node(NodeName.START.value, start_node)
    workflow.add_node(NodeName.PARSE_INPUT.value, parse_input_node)

    # 结束和错误节点
    workflow.add_node(NodeName.END.value, end_node)
    workflow.add_node(NodeName.ERROR.value, error_node)

    workflow.add_edge(START, NodeName.START.value)

    # 结束节点连接到 END
    workflow.add_edge(NodeName.END.value, END)
    workflow.add_edge(NodeName.ERROR.value, END)

    return workflow.compile()


class TestWorkflow:
    """测试工作流入口类。

    提供 run() 方法运行完整的测试工作流，以及 stream() / astream() /
    astream_events() 三个流式输出方法。

    Attributes:
        config: 应用配置
        graph: 编译后的 LangGraph 图
    """

    def __init__(self, config: AppConfig | None = None):
        self.config = config or get_config()
        self.graph = build_graph()

    def _build_initial_state(
            self,
            raw_input: str,
            space_id: int | None = None,
    ) -> dict[str, Any]:
        """构造工作流初始状态。

        Args:
            raw_input: 用户自然语言指令
            space_id: 当前空间 ID（run 流程选接口/生成用例用，可选）

        Returns:
            初始状态字典
        """
        return {
            "raw_input": raw_input,
            "space_id": space_id,
            "next_node": "",
            "run_status": TestStatus.PENDING.value,
            "user_intent": "",
            "test_mode": "",
            "selected_endpoints": [],
            "endpoint_count": 0,
            "run_id": 0,
            "test_cases_count": 0,
            "test_results_summary": {},
            "report_path": "",
            "error_message": "",
            "audit_result": "",
            "messages": [],
        }

    def run(
            self,
            raw_input: str,
            space_id: int | None = None,
    ) -> dict[str, Any]:
        """运行工作流。

        Args:
            raw_input: 用户自然语言指令
            space_id: 当前空间 ID（可选）

        Returns:
            最终工作流状态字典
        """
        logger.info(
            f"工作流开始执行，指令: {raw_input[:80]}",
            raw_input=raw_input,
            space_id=space_id,
        )

        initial_state = self._build_initial_state(raw_input, space_id)

        try:
            final_state = self.graph.invoke(initial_state)
            logger.info(
                f"工作流执行完成，意图: {final_state.get('user_intent', '')}, "
                f"状态: {final_state.get('run_status', '')}",
                intent=final_state.get("user_intent", ""),
                run_status=final_state.get("run_status", ""),
            )
            return final_state
        except Exception as e:
            logger.error(f"工作流执行失败: {str(e)}", error=str(e), raw_input=raw_input[:100])
            initial_state["error_message"] = str(e)
            initial_state["run_status"] = TestStatus.FAILED.value
            return initial_state

    # ------------------------------------------------------------------
    # 流式输出
    # ------------------------------------------------------------------

    def stream(
            self,
            raw_input: str,
            space_id: int | None = None,
            *,
            include_updates: bool = True,
    ) -> Iterator[dict[str, Any]]:
        """同步流式运行工作流，按节点产出结构化事件。

        基于 ``graph.stream(stream_mode=["updates", "values"])``，
        每个已执行节点 yield 一个 ``node`` 事件，结束时 yield 携带完整
        最终状态的 ``final`` 事件；异常时 yield ``error`` 事件后结束。

        Args:
            raw_input: 用户自然语言指令
            space_id: 当前空间 ID（可选）
            include_updates: 是否在 node 事件中携带节点对状态的部分更新
                （可能较大，如生成的测试用例列表），默认 True

        Yields:
            dict: 结构化事件，type 为 start / node / final / error

        Example:
            for event in workflow.stream("测试登录接口"):
            ... print(event["type"], event.get("node", ""))
        """
        initial_state = self._build_initial_state(raw_input, space_id)
        logger.info(
            "工作流流式执行开始(同步)",
            raw_input=raw_input[:100],
        )
        yield {"type": "start", "raw_input": raw_input, "timestamp": _now()}

        final_state: dict[str, Any] | None = None
        try:
            for mode, chunk in self.graph.stream(initial_state, stream_mode=["updates", "values"]):
                if mode == "updates":
                    for node_name, update in chunk.items():
                        event: dict[str, Any] = {"type": "node", "node": node_name, "timestamp": _now()}
                        if include_updates:
                            event["update"] = update
                        yield event
                else:  # values：完整状态快照，最后一次即最终状态
                    final_state = chunk
        except Exception as e:
            logger.error(f"工作流流式执行失败: {str(e)}", error=str(e), raw_input=raw_input[:100])
            initial_state["error_message"] = str(e)
            initial_state["run_status"] = TestStatus.FAILED.value
            yield {"type": "error", "message": str(e), "state": initial_state, "timestamp": _now()}
            return

        yield {"type": "final", "state": final_state or initial_state, "timestamp": _now()}

    async def astream(
            self,
            raw_input: str,
            space_id: int | None = None,
            *,
            include_updates: bool = True,
    ) -> AsyncIterator[dict[str, Any]]:
        """异步流式运行工作流，按节点产出结构化事件。

        基于 ``graph.astream(stream_mode=["updates", "values"])``，是
        FastAPI ``StreamingResponse`` / SSE 场景的首选接口。图内同步节点
        由 LangGraph 自动放入线程池执行，不会阻塞事件循环。

        Args:
            raw_input: 用户自然语言指令
            space_id: 当前空间 ID（可选）
            include_updates: 是否在 node 事件中携带节点对状态的部分更新
                （可能较大，如生成的测试用例列表），默认 True

        Yields:
            dict: 结构化事件，type 为 start / node / final / error

        Example:
            async for event in workflow.astream("测试登录接口"):
            ... await websocket.send_json(event)
        """
        initial_state = self._build_initial_state(raw_input, space_id)
        logger.info(
            "工作流流式执行开始(异步)",
            raw_input=raw_input[:100],
        )
        yield {"type": "start", "raw_input": raw_input, "timestamp": _now()}

        final_state: dict[str, Any] | None = None
        try:
            async for mode, chunk in self.graph.astream(initial_state, stream_mode=["updates", "values"]):
                if mode == "updates":
                    for node_name, update in chunk.items():
                        event: dict[str, Any] = {"type": "node", "node": node_name, "timestamp": _now()}
                        if include_updates:
                            event["update"] = update
                        yield event
                else:  # values：完整状态快照，最后一次即最终状态
                    final_state = chunk
        except Exception as e:
            logger.error(f"工作流流式执行失败: {str(e)}", error=str(e), raw_input=raw_input[:100])
            initial_state["error_message"] = str(e)
            initial_state["run_status"] = TestStatus.FAILED.value
            yield {"type": "error", "message": str(e), "state": initial_state, "timestamp": _now()}
            return

        yield {"type": "final", "state": final_state or initial_state, "timestamp": _now()}

    async def astream_events(
            self,
            raw_input: str,
            space_id: int | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """事件级流式运行工作流，额外产出 LLM token 增量。

        基于 ``graph.astream_events(version="v2")``：
        - 图内每次 LLM 调用产出 ``on_chat_model_stream`` 事件 → yield ``token`` 事件
          （携带文本增量与所属节点名，节点取自 metadata.langgraph_node）
        - 顶层图结束（``on_chain_end``，name == "LangGraph"）时产出 ``final`` 事件

        相比 ``astream()``，本方法能实时推送大模型生成内容，适合
        前端逐字展示；token 事件较多，SSE 传输开销更高。

        Args:
            raw_input: 用户自然语言指令
            space_id: 当前空间 ID（可选）

        Yields:
            dict: 结构化事件，type 为 start / token / final / error
        """
        initial_state = self._build_initial_state(raw_input, space_id)
        logger.info(
            "工作流事件级流式执行开始",
            raw_input=raw_input[:100],
        )
        yield {"type": "start", "raw_input": raw_input, "timestamp": _now()}

        final_state: dict[str, Any] | None = None
        try:
            async for event in self.graph.astream_events(initial_state, version="v2"):
                event_name = event.get("event")
                if event_name == "on_chat_model_stream":
                    node = (event.get("metadata") or {}).get("langgraph_node") or ""
                    text = _extract_token_text((event.get("data") or {}).get("chunk"))
                    if text:
                        yield {"type": "token", "node": node, "content": text, "timestamp": _now()}
                elif event_name == "on_chain_end" and event.get("name") == "LangGraph":
                    # 顶层图结束事件携带最终状态
                    output = (event.get("data") or {}).get("output")
                    if isinstance(output, dict):
                        final_state = output
        except Exception as e:
            logger.error(f"工作流事件级流式执行失败: {str(e)}", error=str(e), raw_input=raw_input[:100])
            initial_state["error_message"] = str(e)
            initial_state["run_status"] = TestStatus.FAILED.value
            yield {"type": "error", "message": str(e), "state": initial_state, "timestamp": _now()}
            return

        yield {"type": "final", "state": final_state or initial_state, "timestamp": _now()}
