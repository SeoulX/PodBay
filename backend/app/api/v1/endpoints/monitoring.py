from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from app.services.kubernetes_service import KubernetesService
from app.models.kubernetes import NamespaceMetrics, ClusterSummary, ErrorResponse

router = APIRouter()
kubernetes_service = KubernetesService()


@router.get("/monitoring/namespaces", response_model=List[NamespaceMetrics])
async def get_namespace_metrics(context: Optional[str] = Query(None, description="Kubernetes context to use")):
    """Get namespace-level resource usage aggregation"""
    try:
        return kubernetes_service.get_namespace_metrics(context)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/monitoring/summary", response_model=ClusterSummary)
async def get_cluster_summary(context: Optional[str] = Query(None, description="Kubernetes context to use")):
    """Get overall cluster resource usage summary"""
    try:
        return kubernetes_service.get_cluster_summary(context)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
