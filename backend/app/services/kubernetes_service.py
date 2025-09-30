from kubernetes import client, config
from typing import List, Optional, Dict, Any
import yaml
import os
from app.models.kubernetes import (
    PodMetrics, NodeMetrics, NamespaceMetrics, ClusterSummary,
    ContextInfo, ContextsResponse, PodInfo, NodeInfo
)


class KubernetesService:
    """Service for Kubernetes operations"""
    
    def __init__(self):
        self.current_context = None
        self._load_config()
    
    def _load_config(self):
        """Load Kubernetes configuration"""
        try:
            config.load_kube_config()
            self.current_context = self._get_current_context()
        except Exception as e:
            raise Exception(f"Failed to load kubeconfig: {str(e)}")
    
    def _get_current_context(self) -> Optional[str]:
        """Get current active context"""
        try:
            kubeconfig_path = os.path.expanduser("~/.kube/config")
            with open(kubeconfig_path, 'r') as file:
                kubeconfig = yaml.safe_load(file)
            return kubeconfig.get('current-context', '')
        except:
            return None
    
    def switch_context(self, context_name: str) -> bool:
        """Switch to a specific Kubernetes context"""
        try:
            config.load_kube_config(context=context_name)
            self.current_context = context_name
            return True
        except Exception:
            return False
    
    def get_contexts(self) -> ContextsResponse:
        """Get all available Kubernetes contexts"""
        kubeconfig_path = os.path.expanduser("~/.kube/config")
        
        if not os.path.exists(kubeconfig_path):
            raise Exception("kubeconfig file not found at ~/.kube/config")
        
        try:
            with open(kubeconfig_path, 'r') as file:
                kubeconfig = yaml.safe_load(file)
            
            contexts = []
            if 'contexts' in kubeconfig:
                for context in kubeconfig['contexts']:
                    contexts.append(ContextInfo(
                        name=context['name'],
                        cluster=context['context'].get('cluster', ''),
                        user=context['context'].get('user', ''),
                        namespace=context['context'].get('namespace', 'default')
                    ))
            
            current_context = kubeconfig.get('current-context', '')
            
            return ContextsResponse(
                current_context=current_context,
                contexts=contexts
            )
        except Exception as e:
            raise Exception(f"Failed to read kubeconfig: {str(e)}")
    
    def get_pods(self) -> List[PodInfo]:
        """Get basic pod information"""
        try:
            v1 = client.CoreV1Api()
            pods = v1.list_pod_for_all_namespaces(watch=False)
            return [
                PodInfo(
                    name=pod.metadata.name,
                    namespace=pod.metadata.namespace,
                    status=pod.status.phase,
                    node=pod.spec.node_name
                )
                for pod in pods.items
            ]
        except Exception as e:
            raise Exception(f"Failed to get pods: {str(e)}")
    
    def get_nodes(self) -> List[NodeInfo]:
        """Get basic node information"""
        try:
            v1 = client.CoreV1Api()
            nodes = v1.list_node()
            return [
                NodeInfo(
                    name=node.metadata.name,
                    cpu=node.status.capacity.get("cpu"),
                    memory=node.status.capacity.get("memory")
                )
                for node in nodes.items
            ]
        except Exception as e:
            raise Exception(f"Failed to get nodes: {str(e)}")
    
    def get_pod_metrics(self, context: Optional[str] = None) -> List[PodMetrics]:
        """Get pod resource usage metrics"""
        if context and not self.switch_context(context):
            raise Exception(f"Failed to switch to context: {context}")
        
        try:
            v1 = client.CoreV1Api()
            metrics_v1 = client.CustomObjectsApi()
            
            # Get pod metrics
            pod_metrics = metrics_v1.list_cluster_custom_object(
                group="metrics.k8s.io",
                version="v1beta1",
                plural="pods"
            )
            
            result = []
            for pod_metric in pod_metrics.get('items', []):
                pod_name = pod_metric['metadata']['name']
                namespace = pod_metric['metadata']['namespace']
                
                containers = []
                for container in pod_metric.get('containers', []):
                    container_name = container['name']
                    usage = container.get('usage', {})
                    
                    # Convert CPU from nanocores to millicores
                    cpu_usage = usage.get('cpu', '0')
                    if cpu_usage.endswith('n'):
                        cpu_millicores = int(cpu_usage[:-1]) / 1000000
                    elif cpu_usage.endswith('m'):
                        cpu_millicores = int(cpu_usage[:-1])
                    else:
                        cpu_millicores = 0
                    
                    # Convert memory to MiB
                    memory_usage = usage.get('memory', '0')
                    if memory_usage.endswith('Ki'):
                        memory_mib = int(memory_usage[:-2]) / 1024
                    elif memory_usage.endswith('Mi'):
                        memory_mib = int(memory_usage[:-2])
                    elif memory_usage.endswith('Gi'):
                        memory_mib = int(memory_usage[:-2]) * 1024
                    else:
                        memory_mib = 0
                    
                    containers.append(ContainerMetrics(
                        name=container_name,
                        cpu_usage_millicores=cpu_millicores,
                        memory_usage_mib=memory_mib,
                        cpu_usage_raw=cpu_usage,
                        memory_usage_raw=memory_usage
                    ))
                
                result.append(PodMetrics(
                    name=pod_name,
                    namespace=namespace,
                    containers=containers
                ))
            
            return result
            
        except Exception as e:
            raise Exception(f"Failed to get pod metrics: {str(e)}")
    
    def get_node_metrics(self, context: Optional[str] = None) -> List[NodeMetrics]:
        """Get node resource usage and capacity metrics"""
        if context and not self.switch_context(context):
            raise Exception(f"Failed to switch to context: {context}")
        
        try:
            v1 = client.CoreV1Api()
            metrics_v1 = client.CustomObjectsApi()
            
            # Get node metrics
            node_metrics = metrics_v1.list_cluster_custom_object(
                group="metrics.k8s.io",
                version="v1beta1",
                plural="nodes"
            )
            
            # Get node information
            nodes = v1.list_node()
            node_info = {node.metadata.name: node for node in nodes.items}
            
            result = []
            for node_metric in node_metrics.get('items', []):
                node_name = node_metric['metadata']['name']
                usage = node_metric.get('usage', {})
                
                # Get node details
                node = node_info.get(node_name)
                if not node:
                    continue
                
                # Parse CPU usage
                cpu_usage = usage.get('cpu', '0')
                if cpu_usage.endswith('n'):
                    cpu_millicores = int(cpu_usage[:-1]) / 1000000
                elif cpu_usage.endswith('m'):
                    cpu_millicores = int(cpu_usage[:-1])
                else:
                    cpu_millicores = 0
                
                # Parse memory usage
                memory_usage = usage.get('memory', '0')
                if memory_usage.endswith('Ki'):
                    memory_mib = int(memory_usage[:-2]) / 1024
                elif memory_usage.endswith('Mi'):
                    memory_mib = int(memory_usage[:-2])
                elif memory_usage.endswith('Gi'):
                    memory_mib = int(memory_usage[:-2]) * 1024
                else:
                    memory_mib = 0
                
                # Get capacity information
                capacity = node.status.capacity
                cpu_capacity = capacity.get('cpu', '0')
                memory_capacity = capacity.get('memory', '0')
                
                # Convert capacity to numeric values
                cpu_capacity_cores = int(cpu_capacity) if cpu_capacity.isdigit() else 0
                memory_capacity_mib = 0
                if memory_capacity.endswith('Ki'):
                    memory_capacity_mib = int(memory_capacity[:-2]) / 1024
                elif memory_capacity.endswith('Mi'):
                    memory_capacity_mib = int(memory_capacity[:-2])
                elif memory_capacity.endswith('Gi'):
                    memory_capacity_mib = int(memory_capacity[:-2]) * 1024
                
                result.append(NodeMetrics(
                    name=node_name,
                    cpu_usage_millicores=cpu_millicores,
                    cpu_capacity_cores=cpu_capacity_cores,
                    cpu_usage_percentage=(cpu_millicores / (cpu_capacity_cores * 1000)) * 100 if cpu_capacity_cores > 0 else 0,
                    memory_usage_mib=memory_mib,
                    memory_capacity_mib=memory_capacity_mib,
                    memory_usage_percentage=(memory_mib / memory_capacity_mib) * 100 if memory_capacity_mib > 0 else 0,
                    cpu_usage_raw=cpu_usage,
                    memory_usage_raw=memory_usage,
                    cpu_capacity_raw=cpu_capacity,
                    memory_capacity_raw=memory_capacity,
                    status=node.status.conditions[-1].type if node.status.conditions else "Unknown"
                ))
            
            return result
            
        except Exception as e:
            raise Exception(f"Failed to get node metrics: {str(e)}")
    
    def get_namespace_metrics(self, context: Optional[str] = None) -> List[NamespaceMetrics]:
        """Get namespace-level resource usage aggregation"""
        if context and not self.switch_context(context):
            raise Exception(f"Failed to switch to context: {context}")
        
        try:
            v1 = client.CoreV1Api()
            metrics_v1 = client.CustomObjectsApi()
            
            # Get pod metrics
            pod_metrics = metrics_v1.list_cluster_custom_object(
                group="metrics.k8s.io",
                version="v1beta1",
                plural="pods"
            )
            
            # Aggregate by namespace
            namespace_usage = {}
            
            for pod_metric in pod_metrics.get('items', []):
                namespace = pod_metric['metadata']['namespace']
                
                if namespace not in namespace_usage:
                    namespace_usage[namespace] = {
                        "namespace": namespace,
                        "total_cpu_millicores": 0,
                        "total_memory_mib": 0,
                        "pod_count": 0
                    }
                
                namespace_usage[namespace]["pod_count"] += 1
                
                for container in pod_metric.get('containers', []):
                    usage = container.get('usage', {})
                    
                    # Parse CPU
                    cpu_usage = usage.get('cpu', '0')
                    if cpu_usage.endswith('n'):
                        cpu_millicores = int(cpu_usage[:-1]) / 1000000
                    elif cpu_usage.endswith('m'):
                        cpu_millicores = int(cpu_usage[:-1])
                    else:
                        cpu_millicores = 0
                    
                    # Parse memory
                    memory_usage = usage.get('memory', '0')
                    if memory_usage.endswith('Ki'):
                        memory_mib = int(memory_usage[:-2]) / 1024
                    elif memory_usage.endswith('Mi'):
                        memory_mib = int(memory_usage[:-2])
                    elif memory_usage.endswith('Gi'):
                        memory_mib = int(memory_usage[:-2]) * 1024
                    else:
                        memory_mib = 0
                    
                    namespace_usage[namespace]["total_cpu_millicores"] += cpu_millicores
                    namespace_usage[namespace]["total_memory_mib"] += memory_mib
            
            return [
                NamespaceMetrics(**ns_data) 
                for ns_data in namespace_usage.values()
            ]
            
        except Exception as e:
            raise Exception(f"Failed to get namespace metrics: {str(e)}")
    
    def get_cluster_summary(self, context: Optional[str] = None) -> ClusterSummary:
        """Get overall cluster resource usage summary"""
        if context and not self.switch_context(context):
            raise Exception(f"Failed to switch to context: {context}")
        
        try:
            v1 = client.CoreV1Api()
            metrics_v1 = client.CustomObjectsApi()
            
            # Get node metrics
            node_metrics = metrics_v1.list_cluster_custom_object(
                group="metrics.k8s.io",
                version="v1beta1",
                plural="nodes"
            )
            
            # Get pod metrics
            pod_metrics = metrics_v1.list_cluster_custom_object(
                group="metrics.k8s.io",
                version="v1beta1",
                plural="pods"
            )
            
            # Calculate totals
            total_cpu_usage = 0
            total_memory_usage = 0
            total_cpu_capacity = 0
            total_memory_capacity = 0
            node_count = 0
            pod_count = len(pod_metrics.get('items', []))
            
            for node_metric in node_metrics.get('items', []):
                usage = node_metric.get('usage', {})
                node_count += 1
                
                # Parse CPU usage
                cpu_usage = usage.get('cpu', '0')
                if cpu_usage.endswith('n'):
                    cpu_millicores = int(cpu_usage[:-1]) / 1000000
                elif cpu_usage.endswith('m'):
                    cpu_millicores = int(cpu_usage[:-1])
                else:
                    cpu_millicores = 0
                
                # Parse memory usage
                memory_usage = usage.get('memory', '0')
                if memory_usage.endswith('Ki'):
                    memory_mib = int(memory_usage[:-2]) / 1024
                elif memory_usage.endswith('Mi'):
                    memory_mib = int(memory_usage[:-2])
                elif memory_usage.endswith('Gi'):
                    memory_mib = int(memory_usage[:-2]) * 1024
                else:
                    memory_mib = 0
                
                total_cpu_usage += cpu_millicores
                total_memory_usage += memory_mib
            
            # Get capacity from nodes
            nodes = v1.list_node()
            for node in nodes.items:
                capacity = node.status.capacity
                cpu_capacity = capacity.get('cpu', '0')
                memory_capacity = capacity.get('memory', '0')
                
                if cpu_capacity.isdigit():
                    total_cpu_capacity += int(cpu_capacity) * 1000  # Convert to millicores
                
                if memory_capacity.endswith('Ki'):
                    total_memory_capacity += int(memory_capacity[:-2]) / 1024
                elif memory_capacity.endswith('Mi'):
                    total_memory_capacity += int(memory_capacity[:-2])
                elif memory_capacity.endswith('Gi'):
                    total_memory_capacity += int(memory_capacity[:-2]) * 1024
            
            return ClusterSummary(
                node_count=node_count,
                pod_count=pod_count,
                cpu_usage_millicores=total_cpu_usage,
                cpu_capacity_millicores=total_cpu_capacity,
                cpu_usage_percentage=(total_cpu_usage / total_cpu_capacity) * 100 if total_cpu_capacity > 0 else 0,
                memory_usage_mib=total_memory_usage,
                memory_capacity_mib=total_memory_capacity,
                memory_usage_percentage=(total_memory_usage / total_memory_capacity) * 100 if total_memory_capacity > 0 else 0
            )
            
        except Exception as e:
            raise Exception(f"Failed to get cluster summary: {str(e)}")
