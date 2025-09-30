import axios from 'axios';
import {
  ContextsResponse,
  PodInfo,
  NodeInfo,
  PodMetrics,
  NodeMetrics,
  NamespaceMetrics,
  ClusterSummary,
} from '../types/kubernetes';

const API_BASE_URL = 'http://localhost:8000/api/v1';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
});

// Context endpoints
export const getContexts = async (): Promise<ContextsResponse> => {
  const response = await api.get('/contexts');
  return response.data;
};

export const switchContext = async (contextName: string): Promise<void> => {
  await api.post(`/contexts/${contextName}/switch`);
};

// Pod endpoints
export const getPods = async (): Promise<PodInfo[]> => {
  const response = await api.get('/pods');
  return response.data;
};

export const getPodMetrics = async (context?: string): Promise<PodMetrics[]> => {
  const params = context ? { context } : {};
  const response = await api.get('/monitoring/pods', { params });
  return response.data;
};

// Node endpoints
export const getNodes = async (): Promise<NodeInfo[]> => {
  const response = await api.get('/nodes');
  return response.data;
};

export const getNodeMetrics = async (context?: string): Promise<NodeMetrics[]> => {
  const params = context ? { context } : {};
  const response = await api.get('/monitoring/nodes', { params });
  return response.data;
};

// Monitoring endpoints
export const getNamespaceMetrics = async (context?: string): Promise<NamespaceMetrics[]> => {
  const params = context ? { context } : {};
  const response = await api.get('/monitoring/namespaces', { params });
  return response.data;
};

export const getClusterSummary = async (context?: string): Promise<ClusterSummary> => {
  const params = context ? { context } : {};
  const response = await api.get('/monitoring/summary', { params });
  return response.data;
};

export default api;
