import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { 
  Container, 
  Server, 
  Activity, 
  Cpu, 
  MemoryStick,
  BarChart3 
} from 'lucide-react';
import { MetricCard } from './MetricCard';
import { StatusBadge } from './StatusBadge';
import { getClusterSummary, getPods, getNodes, getContexts } from '../services/api';

export const Dashboard: React.FC = () => {
  const { data: contexts } = useQuery({
    queryKey: ['contexts'],
    queryFn: getContexts,
  });

  const { data: clusterSummary } = useQuery({
    queryKey: ['clusterSummary'],
    queryFn: () => getClusterSummary(),
  });

  const { data: pods } = useQuery({
    queryKey: ['pods'],
    queryFn: getPods,
  });

  const { data: nodes } = useQuery({
    queryKey: ['nodes'],
    queryFn: getNodes,
  });

  const runningPods = pods?.filter(pod => pod.status.toLowerCase().includes('running')).length || 0;
  const totalPods = pods?.length || 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Dashboard</h2>
          <p className="text-gray-600">Kubernetes cluster overview</p>
        </div>
        <div className="flex items-center space-x-2">
          <span className="text-sm text-gray-500">Current Context:</span>
          <StatusBadge status={contexts?.current_context || 'Unknown'} />
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <MetricCard
          title="Total Nodes"
          value={clusterSummary?.node_count || 0}
          icon={Server}
          color="blue"
        />
        <MetricCard
          title="Total Pods"
          value={totalPods}
          subtitle={`${runningPods} running`}
          icon={Container}
          color="green"
        />
        <MetricCard
          title="CPU Usage"
          value={`${clusterSummary?.cpu_usage_percentage.toFixed(1) || 0}%`}
          subtitle={`${clusterSummary?.cpu_usage_millicores.toFixed(0) || 0}m / ${clusterSummary?.cpu_capacity_millicores.toFixed(0) || 0}m`}
          icon={Cpu}
          color="yellow"
        />
        <MetricCard
          title="Memory Usage"
          value={`${clusterSummary?.memory_usage_percentage.toFixed(1) || 0}%`}
          subtitle={`${clusterSummary?.memory_usage_mib.toFixed(0) || 0}Mi / ${clusterSummary?.memory_capacity_mib.toFixed(0) || 0}Mi`}
          icon={MemoryStick}
          color="purple"
        />
      </div>

      {/* Recent Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900">Recent Pods</h3>
            <Activity className="w-5 h-5 text-gray-400" />
          </div>
          <div className="space-y-3">
            {pods?.slice(0, 5).map((pod) => (
              <div key={`${pod.namespace}-${pod.name}`} className="flex items-center justify-between py-2">
                <div>
                  <p className="font-medium text-gray-900">{pod.name}</p>
                  <p className="text-sm text-gray-500">{pod.namespace}</p>
                </div>
                <StatusBadge status={pod.status} />
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900">Cluster Nodes</h3>
            <BarChart3 className="w-5 h-5 text-gray-400" />
          </div>
          <div className="space-y-3">
            {nodes?.slice(0, 5).map((node) => (
              <div key={node.name} className="flex items-center justify-between py-2">
                <div>
                  <p className="font-medium text-gray-900">{node.name}</p>
                  <p className="text-sm text-gray-500">
                    CPU: {node.cpu} | Memory: {node.memory}
                  </p>
                </div>
                <StatusBadge status="Ready" />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
