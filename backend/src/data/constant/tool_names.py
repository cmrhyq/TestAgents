"""工具名常量。

单独成模块是为了打破循环依赖：``agent_run_recorder`` 要写这些名字，
``agent_tool_call_repository`` 要按名字过滤，两边都不该 import 对方。
"""

#: 唯一会落 HTTP 请求/响应列的工具体（见 ``agent_run_recorder._extract_http``）
HTTP_TOOL_NAME = "send_request"
