"""业务异常定义。

Service 层抛出业务异常，由 FastAPI 全局 exception_handler 映射为 HTTP 状态码：
``NotFoundError`` / ``ConflictError`` / ``ValidationError`` 依次对应 404 / 409 / 422。
路由层不直接抛 ``HTTPException``，框架级输入校验除外。
"""


class AppError(Exception):
    """业务异常基类。"""


class NotFoundError(AppError):
    """资源不存在。"""


class ConflictError(AppError):
    """资源冲突（如重名、查重失败）。"""


class ValidationError(AppError):
    """业务输入校验失败。"""
