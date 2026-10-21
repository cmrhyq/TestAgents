"""报告域 LangChain Tool：测试结果渲染。

面向 LLM 的轻量 Markdown 渲染；node 层完整 HTML 报告仍由
report.renderer.render_report（ORM 版）负责。
"""

from langchain_core.tools import tool

from src.core.logging import get_logger
from src.utils.json_utils import safe_json_loads

logger = get_logger(__name__)


@tool
def render_report(results: str) -> str:
    """将测试结果汇总渲染为 Markdown 报告（统计摘要 + 逐条结果表格）。

    Args:
        results: 测试结果列表 JSON 字符串，每条可含 case_name/status/response_time_ms/error 字段

    Returns:
        Markdown 格式的报告文本
    """
    try:
        items = safe_json_loads(results, []) or []
        total = len(items)
        passed = sum(1 for r in items if r.get("status") == "passed")
        failed = sum(1 for r in items if r.get("status") in ("failed", "error"))
        skipped = total - passed - failed

        lines = [
            "# 测试报告",
            "",
            f"- 总数: {total} | 通过: {passed} | 失败: {failed} | 跳过: {skipped}",
            "",
            "| 用例 | 状态 | 耗时(ms) | 错误 |",
            "|---|---|---|---|",
        ]
        for r in items:
            name = r.get("case_name") or r.get("name") or "-"
            status = r.get("status", "-")
            cost = r.get("response_time_ms", "-")
            error = (r.get("error") or "")[:80]
            lines.append(f"| {name} | {status} | {cost} | {error} |")
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"报告渲染失败: {e}", error=str(e))
        return f"渲染报告失败: {e}"
