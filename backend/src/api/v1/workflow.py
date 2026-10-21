"""工作流触发路由。

提供 OpenAPI 文档上传与解析的 HTTP 接口，业务编排见 ``WorkflowService``。
"""

from pathlib import Path

from fastapi import APIRouter, File, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from src.core.logging import get_logger
from src.data.services.workflow_service import WorkflowService

logger = get_logger(__name__)

router = APIRouter(prefix="/workflows", tags=["工作流"])


class UploadOpenAPIResponse(BaseModel):
    """上传 OpenAPI 文档响应体。"""

    filename: str = Field(..., description="原始文件名")
    path: str = Field(..., description="服务器保存后的绝对路径")
    status: str = Field(default="uploaded", description="当前状态")
    message: str = Field(default="", description="提示信息")


@router.post("/upload/openapi", response_model=UploadOpenAPIResponse)
async def upload_openapi(
        file: UploadFile = File(..., description="OpenAPI 文档文件（JSON/YAML）"),
):
    """上传 OpenAPI 文档并持久化保存，返回服务器路径供后续运行测试使用。"""
    service = WorkflowService()
    content = await file.read()
    path = await run_in_threadpool(service.save_upload, file.filename or "", content)

    return UploadOpenAPIResponse(
        filename=Path(file.filename or "").name,
        path=path,
        status="uploaded",
        message=f"文件 {file.filename} 上传成功",
    )
