from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from app.services.kubernetes_service import KubernetesService
from app.models.kubernetes import PodInfo, PodMetrics, ErrorResponse

router = APIRouter()
kubernetes_service = KubernetesService()


@router.get("/pods", response_model=List[PodInfo])
async def list_pods():
    """Get basic pod information"""
    try:
        return kubernetes_service.get_pods()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/monitoring/pods", response_model=List[PodMetrics])
async def get_pod_metrics(context: Optional[str] = Query(None, description="Kubernetes context to use")):
    """Get pod resource usage metrics (CPU and memory)"""
    try:
        return kubernetes_service.get_pod_metrics(context)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
