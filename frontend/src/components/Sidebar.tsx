import React from 'react';
import {
  LayoutDashboard,
  Scan,
  Inbox,
  FileText,
  BarChart3,
  History,
  Settings,
  Shield,
  Radio,
  GitCompare,
  Scale
} from 'lucide-react';

interface SidebarProps {
  currentTab: string;
  onSelectTab: (tab: string) => void;
  pendingCount?: number;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentTab,
  onSelectTab,
  pendingCount = 0
}) => {
  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'screening', label: 'New Screening', icon: Scan },
    { id: 'queue', label: 'Review Queue', icon: Inbox, badge: pendingCount },
    { id: 'cases', label: 'Cases Archive', icon: FileText },
    { id: 'change_detection', label: 'Change Detection', icon: GitCompare },
    { id: 'compliance', label: 'DPDP Compliance', icon: Scale },
    { id: 'analytics', label: 'Analytics', icon: BarChart3 },
    { id: 'audit', label: 'Audit Trail', icon: History },
    { id: 'settings', label: 'System Settings', icon: Settings },
  ];

  return (
    <aside className="w-64 bg-graphite-950 border-r border-graphite-800/80 flex flex-col justify-between shrink-0 select-none">
      <div>
        {/* Brand Header */}
        <div className="p-5 border-b border-graphite-800/60 flex items-center gap-3">
          {/* The one sanctioned gradient in the app -- a brand mark is
              inherently a logo, not UI chrome. */}
          <div className="h-9 w-9 rounded-lg bg-gradient-to-br from-brass-400 to-brass-700 flex items-center justify-center shadow-lg shadow-brass-950/40 border border-brass-400/30">
            <Shield className="w-5 h-5 text-graphite-950" />
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <span className="font-bold text-base tracking-wider text-graphite-100">
                BORDER<span className="text-brass-400">MESH</span>
              </span>
            </div>
            <p className="text-[10px] text-graphite-400 tracking-wide uppercase">
              AI Identity Screening
            </p>
          </div>
        </div>

        {/* Navigation Menu */}
        <nav className="p-3 space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = currentTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onSelectTab(item.id)}
                className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-lg text-xs font-medium transition-all duration-200 cursor-pointer ${
                  active
                    ? 'bg-brass-950/70 text-brass-300 border border-brass-500/30 font-semibold shadow-inner'
                    : 'text-graphite-400 hover:text-graphite-200 hover:bg-graphite-900/60 border border-transparent'
                }`}
              >
                <div className="flex items-center gap-3">
                  <Icon className={`w-4 h-4 ${active ? 'text-brass-400' : 'text-graphite-400'}`} />
                  <span>{item.label}</span>
                </div>
                {item.badge !== undefined && item.badge > 0 && (
                  <span className="px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {/* System Status Footer */}
      <div className="p-4 m-3 rounded-xl bg-graphite-900/80 border border-graphite-800/80 space-y-2 text-xs transition-all duration-300 hover:border-graphite-700/60">
        <div className="flex items-center justify-between text-graphite-300 text-[11px]">
          <span className="flex items-center gap-1.5 text-graphite-400">
            <Radio className="w-3.5 h-3.5 text-emerald-400 animate-pulse" />
            AI Pipeline
          </span>
          <span className="text-emerald-400 font-bold">ONLINE</span>
        </div>
        <div className="flex items-center justify-between gap-2 text-[11px] text-graphite-400">
          <span className="truncate">Watchlist Adapter</span>
          <span className="text-brass-400 shrink-0">Sandbox Demo</span>
        </div>
        <div className="pt-1.5 border-t border-graphite-800/60 text-[10px] text-graphite-400">
          SIH Problem: <span className="text-graphite-400">SIH26188</span>
        </div>
      </div>
    </aside>
  );
};
