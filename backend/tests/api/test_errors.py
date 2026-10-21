"""全局业务异常 → HTTP 状态码映射测试。"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.core.errors import ConflictError, NotFoundError, ValidationError

pytestmark = pytest.mark.unit


@pytest.fixture()
def client() -> TestClient:
    """构建带业务异常 handler 的最小应用。"""
    app = FastAPI()

    def _handler(status_code: int):
        def handler(request, exc):
            from fastapi.responses import JSONResponse

            return JSONResponse(status_code=status_code, content={"detail": str(exc)})

        return handler

    app.add_exception_handler(NotFoundError, _handler(404))
    app.add_exception_handler(ConflictError, _handler(409))
    app.add_exception_handler(ValidationError, _handler(422))

    @app.get("/not-found")
    def not_found():
        raise NotFoundError("资源不存在")

    @app.get("/conflict")
    def conflict():
        raise ConflictError("名称已存在")

    @app.get("/validation")
    def validation():
        raise ValidationError("参数非法")

    return TestClient(app)


class TestBusinessErrorHandlers:
    """业务异常映射为对应 HTTP 状态码。"""

    def test_not_found_maps_404(self, client):
        resp = client.get("/not-found")
        assert resp.status_code == 404
        assert resp.json() == {"detail": "资源不存在"}

    def test_conflict_maps_409(self, client):
        resp = client.get("/conflict")
        assert resp.status_code == 409
        assert resp.json() == {"detail": "名称已存在"}

    def test_validation_maps_422(self, client):
        resp = client.get("/validation")
        assert resp.status_code == 422
        assert resp.json() == {"detail": "参数非法"}
