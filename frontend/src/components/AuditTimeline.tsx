import React from 'react';
import { AuditLog } from '../types';
import { History, Clock, Lock, FileKey } from 'lucide-react';
import { SectionHeading } from './SectionHeading';
import { ScrollReveal } from './ScrollReveal';

interface AuditTimelineProps {
  logs: AuditLog[];
}

const EmptyState: React.FC = () => (
  <div className="border border-hairline p-6 text-center">
    <History className="w-7 h-7 text-muted mx-auto mb-2" strokeWidth={1.5} />
    <p className="text-[11px] text-muted">No audit log events recorded for this case.</p>
  </div>
);

export const AuditTimeline: React.FC<AuditTimelineProps> = ({ logs }) => {
  if (!logs || logs.length === 0) {
    return <EmptyState />;
  }

  return (
    <ScrollReveal className="border border-hairline p-5 space-y-5">
      <SectionHeading
        level="h3"
        title={`Chain of custody & cryptographic ledger (${logs.length} blocks)`}
        icon={<History className="w-4 h-4 text-muted" strokeWidth={1.75} />}
        action={
          <span className="badge-signal badge-low">
            <Lock className="w-3 h-3" strokeWidth={1.75} />
            SHA-256 chained
          </span>
        }
      />

      <div>
        {logs.map((item, idx) => {
          const isPurge = item.action.includes('PURGE');
          const isOfficer = item.actor.includes('OFFICER');
          const actorBadgeCls = isPurge ? 'badge-medium' : isOfficer ? 'badge-accent' : 'badge-neutral';
          const dateFormatted = new Date(item.timestamp).toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
          });

          return (
            <div key={item.id || idx} className="py-3.5 border-t border-hairline text-[12px] space-y-2 animate-fade-in" style={{ animationDelay: `${idx * 30}ms` }}>
              <div className="flex items-center justify-between flex-wrap gap-2">
                <div className="flex items-center gap-3">
                  <span className={`font-bold ${isPurge ? 'text-signal-medium' : 'text-ink'}`}>
                    {item.action.replace(/_/g, ' ')}
                  </span>
                  <span className={`badge-signal ${actorBadgeCls}`}>
                    {item.actor}
                  </span>
                </div>

                <div className="flex items-center gap-3">
                  {item.entry_hash && (
                    <span
                      className="text-[10px] figure text-muted flex items-center gap-1"
                      title={`Block Hash: ${item.entry_hash}\nPrevious: ${item.previous_hash || 'GENESIS'}`}
                    >
                      <FileKey className="w-2.5 h-2.5" strokeWidth={1.75} />
                      #{item.entry_hash.substring(0, 6)}…{item.entry_hash.substring(58)}
                    </span>
                  )}
                  <div className="flex items-center gap-1 text-[10px] text-muted figure">
                    <Clock className="w-3 h-3" strokeWidth={1.75} />
                    <span>{dateFormatted}</span>
                  </div>
                </div>
              </div>

              {item.metadata_json && Object.keys(item.metadata_json).length > 0 && (
                <div className="flex flex-wrap gap-x-4 gap-y-1">
                  {Object.entries(item.metadata_json).map(([k, v], mIdx) => (
                    <span
                      key={mIdx}
                      className="text-[10px] text-muted"
                    >
                      <strong className="text-ink-soft">{k}:</strong> {String(v)}
                    </span>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </ScrollReveal>
  );
};
