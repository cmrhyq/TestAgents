from enum import StrEnum


class Mode(StrEnum):
    """工作模式。"""

    AGENT = "agent"  # 默认：自动选工具执行测试
    ASK = "ask"  # 只回答问题，零副作用
    PLAN = "plan"  # 只出计划，不执行