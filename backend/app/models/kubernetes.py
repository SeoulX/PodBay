from pydantic import BaseModel
from typing import List, Optional, Dict, Any


class ContainerMetrics(BaseModel):
    """Container resource metrics"""
    name: str
    cpu_usage_millicores: float
    memory_usage_mib: float
    cpu_usage_raw: str
    memory_usage_raw: str


class PodMetrics(BaseModel):
    """Pod resource metrics"""
    name: str
    namespace: str
    containers: List[ContainerMetrics]


class NodeMetrics(BaseModel):
    """Node resource metrics"""
    name: str
    cpu_usage_millicores: float
    cpu_capacity_cores: int
    cpu_usage_percentage: float
    memory_usage_mib: float
    memory_capacity_mib: float
    memory_usage_percentage: float
    cpu_usage_raw: str
    memory_usage_raw: str
    cpu_capacity_raw: str
    memory_capacity_raw: str
    status: str


class NamespaceMetrics(BaseModel):
    """Namespace resource aggregation"""
    namespace: str
    total_cpu_millicores: float
    total_memory_mib: float
    pod_count: int


class ClusterSummary(BaseModel):
    """Cluster resource summary"""
    node_count: int
    pod_count: int
    cpu_usage_millicores: float
    cpu_capacity_millicores: float
    cpu_usage_percentage: float
    memory_usage_mib: float
    memory_capacity_mib: float
    memory_usage_percentage: float


class ContextInfo(BaseModel):
    """Kubernetes context information"""
    name: str
    cluster: str
    user: str
    namespace: str


class ContextsResponse(BaseModel):
    """Response for contexts list"""
    current_context: str
    contexts: List[ContextInfo]


class PodInfo(BaseModel):
    """Basic pod information"""
    name: str
    namespace: str
    status: str
    node: Optional[str]


class NodeInfo(BaseModel):
    """Basic node information"""
    name: str
    cpu: Optional[str]
    memory: Optional[str]


class ErrorResponse(BaseModel):
    """Error response model"""
    error: str
    detail: Optional[str] = None
