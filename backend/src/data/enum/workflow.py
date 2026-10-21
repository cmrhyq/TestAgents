"""
工作流枚举定义

定义 API 测试相关的状态、类型等枚举值，包括：
- DataStatus: 数据状态
- HttpMethod: HTTP 请求方法
- Priority: 用例优先级
- TestStatus: 测试状态
- ScenarioType: 场景类型
- AssertOperator: 断言运算符
"""

from enum import Enum


class DataStatus(int, Enum):
    """
    1=启用，2=禁用，3=已删除, 4=已废弃
    """

    ENABLE = 1
    DISABLE = 2
    DELETED = 3
    ABANDONED = 4


class HttpMethod(str, Enum):
    """HTTP请求方法"""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


class Priority(str, Enum):
    """用例优先级"""

    P0 = "P0"  # 冒烟用例
    P1 = "P1"  # 核心用例
    P2 = "P2"  # 全量用例


class TestStatus(str, Enum):
    """测试状态"""

    PENDING = "pending"  # 待执行
    RUNNING = "running"  # 执行中
    PASSED = "passed"  # 通过
    FAILED = "failed"  # 失败
    SKIPPED = "skipped"  # 跳过
    ERROR = "error"  # 错误
    COMPLETED = "completed"  # 完成（TestRun 终态）
    CANCELLED = "cancelled"  # 已取消（TestRun 终态）


class ScenarioType(str, Enum):
    """场景类型"""

    NORMAL = "normal"  # 正常场景
    PARAM_MISSING = "param_missing"  # 参数缺失
    PARAM_TYPE_ERROR = "param_type_error"  # 参数类型错误
    BOUNDARY_VALUE = "boundary_value"  # 边界值
    PERMISSION_ERROR = "permission_error"  # 权限异常
    CUSTOM = "custom"  # 自定义


class AssertOperator(str, Enum):
    """断言运算符"""

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
