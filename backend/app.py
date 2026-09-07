"""TestAgents FastAPI 应用入口。

启动方式:
    python app.py
    uvicorn app:app --host 0.0.0.0 --port 8000 --reload
"""

import json
import os
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.v1.router import api_router
from src.core.config import init_config
from src.core.database.database_manager import init_database_from_config
from src.core.errors import ConflictError, NotFoundError, ValidationError
from src.core.llm.llm_gateway import init_llm_gateway
from src.core.logging import get_logger
from src.data.migration.migration import init_database_from_orm

logger = get_logger(__name__)

MAX_SAFE_INTEGER = 9007199254740991


class SafeIntEncoder(json.JSONEncoder):
    """将超过 JavaScript 安全整数范围的 int 序列化为字符串，避免前端精度丢失。"""

    def default(self, o: Any) -> Any:
        return super().default(o)

    def encode(self, o: Any) -> str:
        return super().encode(self._convert(o))

    def _convert(self, obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: self._convert(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [self._convert(i) for i in obj]
        if isinstance(obj, int) and not isinstance(obj, bool) and (obj > MAX_SAFE_INTEGER or obj < -MAX_SAFE_INTEGER):
            return str(obj)
        return obj


class SafeJSONResponse(JSONResponse):
    """使用 SafeIntEncoder 确保大整数 ID 以字符串形式返回。"""

    def render(self, content: Any) -> bytes:
        return json.dumps(
            content,
            cls=SafeIntEncoder,
            ensure_ascii=False,
        ).encode("utf-8")


@asynccontextmanager
async def lifespan(application: FastAPI):
    """应用生命周期管理：启动时初始化配置和数据库。"""
    config = init_config()
    db_manager = init_database_from_config(config)
    init_database_from_orm(db_manager)
    init_llm_gateway()
    logger.info("FastAPI 应用启动完成", version="1.0.0")
    yield
    db_manager.close()
    logger.info("FastAPI 应用已关闭")


app = FastAPI(
    title="TestAgents API",
    description="基于大语言模型的 API 自动化测试智能体 - RESTful 接口服务",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    default_response_class=SafeJSONResponse,
)

_cors_origins_raw = os.getenv("CORS_ORIGINS", "http://localhost:5173")
_cors_origins = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


def _business_error_handler(status_code: int):
    """把业务异常映射为对应 HTTP 状态码的 JSON 响应。"""

    def handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=status_code, content={"detail": str(exc)})

    return handler


app.add_exception_handler(NotFoundError, _business_error_handler(404))
app.add_exception_handler(ConflictError, _business_error_handler(409))
app.add_exception_handler(ValidationError, _business_error_handler(422))


@app.get("/health", tags=["系统"])
def health_check():
    """健康检查接口。"""
    from src.core.database.database_manager import get_db_manager

    db_ok = get_db_manager().check_connection()
    return {
        "status": "healthy" if db_ok else "degraded",
        "database": "connected" if db_ok else "disconnected",
    }


if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
