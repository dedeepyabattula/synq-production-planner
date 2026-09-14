import React from 'react';

interface StatusBadgeProps {
  status: string;
  className?: string;
}

const statusColors: Record<string, { bg: string, text: string }> = {
  // Machine Status
  AVAILABLE: { bg: 'bg-green-500/10', text: 'text-green-400' },
  BUSY: { bg: 'bg-blue-500/10', text: 'text-blue-400' },
  MAINTENANCE: { bg: 'bg-yellow-500/10', text: 'text-yellow-400' },
  FAILED: { bg: 'bg-red-500/10', text: 'text-red-400' },
  
  // Order Status
  PENDING: { bg: 'bg-gray-500/10', text: 'text-gray-400' },
  IN_PROGRESS: { bg: 'bg-blue-500/10', text: 'text-blue-400' },
  COMPLETED: { bg: 'bg-green-500/10', text: 'text-green-400' },
  DELAYED: { bg: 'bg-orange-500/10', text: 'text-orange-400' },
  CANCELLED: { bg: 'bg-red-500/10', text: 'text-red-400' },
  
  // Priority
  LOW: { bg: 'bg-gray-500/10', text: 'text-gray-400' },
  NORMAL: { bg: 'bg-blue-500/10', text: 'text-blue-400' },
  HIGH: { bg: 'bg-orange-500/10', text: 'text-orange-400' },
  CRITICAL: { bg: 'bg-red-500/10', text: 'text-red-400' },

  // Approval Status
  APPROVED: { bg: 'bg-green-500/10', text: 'text-green-400' },
  MODIFIED: { bg: 'bg-yellow-500/10', text: 'text-yellow-400' },
  REJECTED: { bg: 'bg-red-500/10', text: 'text-red-400' },
};

const StatusBadge: React.FC<StatusBadgeProps> = ({ status, className = '' }) => {
  const normStatus = status.toUpperCase();
  const colors = statusColors[normStatus] || { bg: 'bg-synq-border', text: 'text-synq-text' };

  return (
    <span className={`inline-flex items-center px-2 py-1 rounded text-xs font-semibold uppercase tracking-wider ${colors.bg} ${colors.text} ${className}`}>
      {status.replace(/_/g, ' ')}
    </span>
  );
};

export default StatusBadge;
