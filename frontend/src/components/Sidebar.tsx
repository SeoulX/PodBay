import React from 'react';
import { 
  LayoutDashboard, 
  Container, 
  Server, 
  BarChart3, 
  Settings,
  Activity
} from 'lucide-react';

interface SidebarProps {}

export const Sidebar: React.FC<SidebarProps> = () => {
  const menuItems = [
    { icon: LayoutDashboard, label: 'Dashboard', href: '/', active: true },
    { icon: Container, label: 'Pods', href: '/pods' },
    { icon: Server, label: 'Nodes', href: '/nodes' },
    { icon: BarChart3, label: 'Monitoring', href: '/monitoring' },
    { icon: Activity, label: 'Contexts', href: '/contexts' },
    { icon: Settings, label: 'Settings', href: '/settings' },
  ];

  return (
    <aside className="w-64 bg-white border-r border-gray-200 min-h-screen">
      <div className="p-6">
        <div className="flex items-center space-x-2 mb-8">
          <div className="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center">
            <Activity className="w-5 h-5 text-white" />
          </div>
          <span className="text-lg font-semibold text-gray-900">PodBay</span>
        </div>
        
        <nav className="space-y-2">
          {menuItems.map((item) => {
            const Icon = item.icon;
            return (
              <a
                key={item.label}
                href={item.href}
                className={`flex items-center space-x-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  item.active
                    ? 'bg-primary-50 text-primary-700 border-r-2 border-primary-600'
                    : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                }`}
              >
                <Icon className="w-5 h-5" />
                <span>{item.label}</span>
              </a>
            );
          })}
        </nav>
      </div>
    </aside>
  );
};
