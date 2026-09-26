import React from 'react';
import { AuditLog } from '../types';
import { History, Shield, User, Bot, Clock, Link, Lock, FileKey } from 'lucide-react';
import { SectionHeading } from './SectionHeading';

interface AuditTimelineProps {
  logs: AuditLog[];
}

const EmptyState: React.FC = () => (
  <div className="bg-graphite-900/80 border border-graphite-800/80 rounded-xl p-6 backdrop-blur text-center transition-all duration-300 hover:border-graphite-700/60">
    <History className="w-8 h-8 text-graphite-600 mx-auto mb-2" />
    <p className="text-xs text-graphite-500">No audit log events recorded for this case.</p>
  </div>
);

export const AuditTimeline: React.FC<AuditTimelineProps> = ({ logs }) => {
  if (!logs || logs.length === 0) {
    return <EmptyState />;
  }

  return (
    <div className="bg-graphite-900/80 border border-graphite-800/80 rounded-xl p-5 backdrop-blur space-y-5 transition-all duration-300 hover:border-graphite-700/60">
      <SectionHeading
        level="h3"
        title={`Chain of custody & cryptographic ledger (${logs.length} blocks)`}
        icon={<History className="w-4 h-4 text-graphite-500" />}
        action={
          <span className="text-xs font-semibold px-2.5 py-1 rounded-lg bg-emerald-950/60 text-emerald-400 border border-emerald-500/30 flex items-center gap-1">
            <Lock className="w-3 h-3" />
            SHA-256 chained
          </span>
        }
      />

      <div className="relative pl-6 border-l-2 border-graphite-800/60 space-y-4">
        {logs.map((item, idx) => {
          const isPurge = item.action.includes('PURGE');
          const isOfficer = item.actor.includes('OFFICER');
          const isAI = item.actor.startsWith('AI');
          const dateFormatted = new Date(item.timestamp).toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
          });

          return (
            <div key={item.id || idx} className="relative group animate-fade-in" style={{ animationDelay: `${idx * 30}ms` }}>
              {/* Dot indicator */}
              <div
                className={`absolute -left-[31px] top-1.5 h-3.5 w-3.5 rounded-full border-2 border-graphite-950 flex items-center justify-center ${
                  isPurge ? 'bg-amber-500' : isOfficer ? 'bg-brass-500' : isAI ? 'bg-emerald-500' : 'bg-graphite-500'
                }`}
              >
                <div className="h-1.5 w-1.5 rounded-full bg-graphite-950" />
              </div>

              <div className={`p-3.5 rounded-lg border text-xs space-y-2 transition-all duration-200 ${
                isPurge
                  ? 'bg-amber-950/20 border-amber-500/40 hover:border-amber-500/60'
                  : 'bg-graphite-950/70 border-graphite-800/80 hover:border-graphite-700/60'
              }`}>
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <div className="flex items-center gap-2">
                    <span className={`font-bold text-xs tracking-wide ${isPurge ? 'text-amber-300' : isOfficer ? 'text-brass-300' : 'text-graphite-200'}`}>
                      {item.action.replace(/_/g, ' ')}
                    </span>
                    <span className={`px-2 py-0.5 rounded-lg text-[10px] font-medium ${
                      isPurge
                        ? 'bg-amber-950/80 text-amber-300 border border-amber-500/30'
                        : isOfficer
                        ? 'bg-brass-950/80 text-brass-300 border border-brass-500/30'
                        : isAI
                        ? 'bg-emerald-950/80 text-emerald-300 border border-emerald-500/30'
                        : 'bg-graphite-800/60 text-graphite-300 border border-graphite-700/60'
                    }`}>
                      {item.actor}
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    {item.entry_hash && (
                      <span
                        className="text-[10px] font-mono px-2 py-0.5 rounded-lg bg-graphite-900/60 border border-graphite-800/60 text-graphite-400 flex items-center gap-1"
                        title={`Block Hash: ${item.entry_hash}\nPrevious: ${item.previous_hash || 'GENESIS'}`}
                      >
                        <FileKey className="w-2.5 h-2.5" />
                        #{item.entry_hash.substring(0, 6)}…{item.entry_hash.substring(58)}
                      </span>
                    )}
                    <div className="flex items-center gap-1 text-[10px] text-graphite-400">
                      <Clock className="w-3 h-3" />
                      <span>{dateFormatted}</span>
                    </div>
                  </div>
                </div>

                {item.metadata_json && Object.keys(item.metadata_json).length > 0 && (
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {Object.entries(item.metadata_json).map(([k, v], mIdx) => (
                      <span
                        key={mIdx}
                        className="text-[10px] px-2 py-0.5 rounded bg-graphite-900/60 border border-graphite-800/60 text-graphite-400"
                      >
                        <strong className="text-graphite-300">{k}:</strong> {String(v)}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
