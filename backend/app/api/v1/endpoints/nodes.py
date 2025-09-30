from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from app.services.kubernetes_service import KubernetesService
from app.models.kubernetes import NodeInfo, NodeMetrics, ErrorResponse

router = APIRouter()
kubernetes_service = KubernetesService()


@router.get("/nodes", response_model=List[NodeInfo])
async def list_nodes():
    """Get basic node information"""
    try:
        return kubernetes_service.get_nodes()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/monitoring/nodes", response_model=List[NodeMetrics])
async def get_node_metrics(context: Optional[str] = Query(None, description="Kubernetes context to use")):
    """Get node resource usage and capacity metrics"""
    try:
        return kubernetes_service.get_node_metrics(context)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
