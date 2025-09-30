from fastapi import APIRouter
from .endpoints import contexts, pods, nodes, monitoring

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(contexts.router, tags=["contexts"])
api_router.include_router(pods.router, tags=["pods"])
api_router.include_router(nodes.router, tags=["nodes"])
api_router.include_router(monitoring.router, tags=["monitoring"])
