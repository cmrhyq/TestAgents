"""工作流与数据枚举。

覆盖数据状态、HTTP 方法、用例优先级、测试状态、场景类型与断言运算符六类取值。
"""

from enum import Enum


class DataStatus(int, Enum):
    """数据状态：1-启用，2-禁用，3-已删除，4-已废弃。"""

    ENABLE = 1
    DISABLE = 2
    DELETED = 3
    ABANDONED = 4


class HttpMethod(str, Enum):
    """HTTP 请求方法。"""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


class Priority(str, Enum):
    """用例优先级。"""

    P0 = "P0"  # 冒烟用例
    P1 = "P1"  # 核心用例
    P2 = "P2"  # 全量用例


class TestStatus(str, Enum):
    """测试状态，同时用于执行记录的终态取值。"""

    PENDING = "pending"  # 待执行
    RUNNING = "running"  # 执行中
    PASSED = "passed"  # 通过
    FAILED = "failed"  # 失败
    SKIPPED = "skipped"  # 跳过
    ERROR = "error"  # 错误
    COMPLETED = "completed"  # 完成，执行记录终态
    CANCELLED = "cancelled"  # 已取消，执行记录终态，含客户端断流


class ScenarioType(str, Enum):
    """用例场景类型。"""

    NORMAL = "normal"  # 正常场景
    PARAM_MISSING = "param_missing"  # 参数缺失
    PARAM_TYPE_ERROR = "param_type_error"  # 参数类型错误
    BOUNDARY_VALUE = "boundary_value"  # 边界值
    PERMISSION_ERROR = "permission_error"  # 权限异常
    CUSTOM = "custom"  # 自定义


class AssertOperator(str, Enum):
    """断言运算符。"""

    EQ = "=="  # 等于
    NE = "!="  # 不等于
    GT = ">"  # 大于
    LT = "<"  # 小于
    GE = ">="  # 大于等于
    LE = "<="  # 小于等于
    CONTAINS = "contains"  # 包含
    NOT_CONTAINS = "not_contains"  # 不包含
    MATCHES = "matches"  # 正则匹配
    EXISTS = "exists"  # 存在
    NOT_EXISTS = "not_exists"  # 不存在
