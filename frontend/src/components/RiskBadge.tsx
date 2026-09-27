import React from 'react';
import { RiskLevel, CaseStatus, OfficerDecision } from '../types';

interface RiskBadgeProps {
  level?: RiskLevel | string;
  status?: CaseStatus | OfficerDecision | string;
  size?: 'sm' | 'md' | 'lg';
}

export const RiskBadge: React.FC<RiskBadgeProps> = ({ level, status, size = 'md' }) => {
  const text = level || status || 'UNKNOWN';

  let signalClass = 'badge-neutral';

  if (text === 'LOW' || text === 'CLEARED' || text === 'LOW_RISK' || text === 'MATCH') {
    signalClass = 'badge-low';
  } else if (text === 'MEDIUM' || text === 'MEDIUM_RISK' || text === 'ROUTINE VERIFICATION') {
    signalClass = 'badge-medium';
  } else if (text === 'HIGH' || text === 'HIGH_RISK' || text === 'REQUIRES_REVIEW' || text === 'REQUIRES_INSPECTION' || text === 'REVIEW_REQUIRED') {
    signalClass = 'badge-high';
  } else if (text === 'CRITICAL' || text === 'ESCALATED' || text === 'REJECT') {
    signalClass = 'badge-critical';
  } else if (text === 'PROCESSING') {
    signalClass = 'badge-pending';
  }

  const sizeClasses = {
    sm: 'text-[10px]',
    md: 'text-[11px]',
    lg: 'text-[12px]'
  }[size];

  const formatted = text.replace(/_/g, ' ');

  return (
    <span className={`badge-signal ${signalClass} ${sizeClasses}`}>
      {formatted}
    </span>
  );
};
