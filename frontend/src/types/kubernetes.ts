export interface ContextInfo {
  name: string;
  cluster: string;
  user: string;
  namespace: string;
}

export interface ContextsResponse {
  current_context: string;
  contexts: ContextInfo[];
}

export interface PodInfo {
  name: string;
  namespace: string;
  status: string;
  node?: string;
}

export interface NodeInfo {
  name: string;
  cpu?: string;
  memory?: string;
}

export interface ContainerMetrics {
  name: string;
  cpu_usage_millicores: number;
  memory_usage_mib: number;
  cpu_usage_raw: string;
  memory_usage_raw: string;
}

export interface PodMetrics {
  name: string;
  namespace: string;
  containers: ContainerMetrics[];
}

export interface NodeMetrics {
  name: string;
  cpu_usage_millicores: number;
  cpu_capacity_cores: number;
  cpu_usage_percentage: number;
  memory_usage_mib: number;
  memory_capacity_mib: number;
  memory_usage_percentage: number;
  cpu_usage_raw: string;
  memory_usage_raw: string;
  cpu_capacity_raw: string;
  memory_capacity_raw: string;
  status: string;
}

export interface NamespaceMetrics {
  namespace: string;
  total_cpu_millicores: number;
  total_memory_mib: number;
  pod_count: number;
}

export interface ClusterSummary {
  node_count: number;
  pod_count: number;
  cpu_usage_millicores: number;
  cpu_capacity_millicores: number;
  cpu_usage_percentage: number;
  memory_usage_mib: number;
  memory_capacity_mib: number;
  memory_usage_percentage: number;
}

export interface ApiResponse<T> {
  data?: T;
  error?: string;
}
