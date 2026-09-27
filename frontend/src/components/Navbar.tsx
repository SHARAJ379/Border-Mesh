import React, { useState, useEffect } from 'react';
import { User } from 'lucide-react';
import { QuickDemoBar } from './QuickDemoBar';

interface NavbarProps {
  currentTab: string;
  onScenarioLoaded: (caseId: string) => void;
}

export const Navbar: React.FC<NavbarProps> = ({ currentTab, onScenarioLoaded }) => {
  const [timeStr, setTimeStr] = useState('');

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setTimeStr(
        now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false }) + ' UTC'
      );
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  const titles: Record<string, string> = {
    dashboard: 'Operations Dashboard',
    screening: 'Document Ingestion & Live Screening',
    queue: 'Officer Review & Inspection Queue',
    cases: 'Archived Cases Repository',
    analytics: 'Analytics & Model Telemetry',
    audit: 'Chain of Custody Audit Trail',
    settings: 'System Policy & Subsystem Settings',
    change_detection: 'Same-Identity Change Detection',
    compliance: 'DPDP Act 2023 Compliance Dashboard',
    detail: 'Officer Case Inspection'
  };

  return (
    <header className="glass-panel-strong border-x-0 border-t-0 sticky top-0 z-40">
      {/* 1-Click Judging Demo Scenario Bar */}
      <QuickDemoBar onScenarioLoaded={onScenarioLoaded} />

      {/* Main App Bar — one quiet line, no boxed chips */}
      <div className="px-6 py-3 flex items-center justify-between gap-4">
        <div className="flex items-baseline gap-2.5 min-w-0">
          <h2 className="font-display text-[15px] font-bold tracking-tight text-graphite-100 truncate">
            {titles[currentTab] || 'BorderMesh Screening'}
          </h2>
          <span className="hidden sm:inline text-xs text-graphite-500 shrink-0 pl-2.5 border-l border-graphite-800/60">
            Station #04, Immigration Gateway
          </span>
        </div>

        <div className="flex items-center gap-3 text-xs text-graphite-400 shrink-0">
          <span className="hidden md:inline font-mono tabular-nums">{timeStr}</span>
          <div className="flex items-center gap-1.5 md:pl-3 md:border-l md:border-graphite-800/60">
            <User className="w-3.5 h-3.5 text-graphite-500" />
            <span>Officer-Demo-01</span>
          </div>
        </div>
      </div>
    </header>
  );
};
