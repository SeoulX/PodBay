from fastapi import APIRouter, HTTPException
from typing import Optional
from app.services.kubernetes_service import KubernetesService
from app.models.kubernetes import ContextsResponse, ErrorResponse

router = APIRouter()
kubernetes_service = KubernetesService()


@router.get("/contexts", response_model=ContextsResponse)
async def list_contexts():
    """Get all available Kubernetes contexts from kubeconfig"""
    try:
        return kubernetes_service.get_contexts()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/contexts/{context_name}/switch")
async def switch_to_context(context_name: str):
    """Switch to a specific Kubernetes context"""
    if kubernetes_service.switch_context(context_name):
        return {"message": f"Switched to context: {context_name}", "current_context": context_name}
    else:
        raise HTTPException(status_code=400, detail=f"Failed to switch to context: {context_name}")
