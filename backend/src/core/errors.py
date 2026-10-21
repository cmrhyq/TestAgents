"""业务异常定义。

Service 层抛出业务异常，FastAPI 全局 exception_handler 映射为 HTTP 状态码：
- ``NotFoundError``   → 404
- ``ConflictError``   → 409
- ``ValidationError`` → 422

路由层不再手写 ``HTTPException(404/409)``（输入校验等框架级校验除外）。
"""


class AppError(Exception):
    """业务异常基类。"""


class NotFoundError(AppError):
    """资源不存在。"""


class ConflictError(AppError):
    """资源冲突（如重名、查重失败）。"""


class ValidationError(AppError):
    """业务输入校验失败。"""
