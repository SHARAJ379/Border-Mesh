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
    <header className="bg-paper/90 backdrop-blur-md border-b border-hairline sticky top-0 z-40">
      {/* 1-Click Judging Demo Scenario Bar */}
      <QuickDemoBar onScenarioLoaded={onScenarioLoaded} />

      {/* Main app bar -- one quiet line, no boxed chips */}
      <div className="px-6 h-[58px] flex items-center justify-between gap-4">
        <div className="flex items-baseline gap-2.5 min-w-0">
          <h2 className="font-display text-[17px] text-ink truncate">
            {titles[currentTab] || 'BorderMesh Screening'}
          </h2>
          <span className="hidden sm:inline text-[11px] uppercase tracking-[0.06em] text-muted shrink-0 pl-2.5 border-l border-hairline">
            Station #04, Immigration Gateway
          </span>
        </div>

        <div className="flex items-center gap-3 text-[11px] uppercase tracking-[0.06em] text-ink-soft shrink-0">
          <span className="hidden md:inline figure">{timeStr}</span>
          <div className="flex items-center gap-1.5 md:pl-3 md:border-l md:border-hairline">
            <User className="w-3.5 h-3.5 text-muted" strokeWidth={1.75} />
            <span>Officer-Demo-01</span>
          </div>
        </div>
      </div>
    </header>
  );
};
