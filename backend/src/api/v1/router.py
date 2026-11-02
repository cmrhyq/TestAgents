"""API v1 路由汇总。"""

from fastapi import APIRouter

from src.api.v1.agent_run import router as agent_run_router
from src.api.v1.chat import router as chat_router
from src.api.v1.conversation import router as conversation_router
from src.api.v1.endpoint import router as endpoint_router
from src.api.v1.environment import router as environment_router
from src.api.v1.knowledge import router as knowledge_router
from src.api.v1.memory import router as memory_router
from src.api.v1.report import router as report_router
from src.api.v1.skill import router as skill_router
from src.api.v1.space import router as space_router
from src.api.v1.usage import router as usage_router
from src.api.v1.workflow import router as workflow_router

api_router = APIRouter()

api_router.include_router(space_router)
api_router.include_router(endpoint_router)
api_router.include_router(environment_router)
api_router.include_router(agent_run_router)
api_router.include_router(workflow_router)
api_router.include_router(report_router)
api_router.include_router(chat_router)
api_router.include_router(conversation_router)
api_router.include_router(skill_router)
api_router.include_router(memory_router)
api_router.include_router(knowledge_router)
api_router.include_router(usage_router)
