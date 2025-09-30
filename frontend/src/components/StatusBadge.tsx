import React from 'react';

interface StatusBadgeProps {
  status: string;
  className?: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, className = '' }) => {
  const getStatusClass = (status: string) => {
    const normalizedStatus = status.toLowerCase();
    
    if (normalizedStatus.includes('running') || normalizedStatus.includes('ready')) {
      return 'status-badge status-running';
    } else if (normalizedStatus.includes('pending') || normalizedStatus.includes('waiting')) {
      return 'status-badge status-pending';
    } else if (normalizedStatus.includes('failed') || normalizedStatus.includes('error')) {
      return 'status-badge status-failed';
    } else {
      return 'status-badge status-unknown';
    }
  };

  return (
    <span className={`${getStatusClass(status)} ${className}`}>
      {status}
    </span>
  );
};
