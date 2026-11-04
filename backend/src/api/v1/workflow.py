"""工作流触发路由：OpenAPI 文档上传。

解析与业务编排见 ``WorkflowService``。
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
    """上传 OpenAPI 文档并落盘，返回服务器路径供后续解析。

    副作用：文件写入服务器临时上传目录。

    Args:
        file: OpenAPI 文档文件，支持 JSON 与 YAML

    Returns:
        原始文件名、服务器保存路径、状态与提示信息

    Raises:
        ValidationError: 文件名为空或后缀非 JSON/YAML，返回 HTTP 422
    """
    service = WorkflowService()
    content = await file.read()
    path = await run_in_threadpool(service.save_upload, file.filename or "", content)

    return UploadOpenAPIResponse(
        filename=Path(file.filename or "").name,
        path=path,
        status="uploaded",
        message=f"文件 {file.filename} 上传成功",
    )
