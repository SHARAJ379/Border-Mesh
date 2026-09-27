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
    <aside className="w-64 glass-panel-strong border-y-0 border-l-0 flex flex-col justify-between shrink-0 select-none z-20">
      <div>
        {/* Brand Header */}
        <div className="p-5 border-b-[1.5px] border-graphite-800 flex items-center gap-3">
          {/* Flat, hard-bordered brand mark -- a solid fill + a real black
              border reads as a logotype block, not a soft glowing gradient. */}
          <div className="h-9 w-9 rounded-lg bg-brass-500 flex items-center justify-center shadow-[2px_2px_0_0_rgba(0,0,0,0.7)] border-[1.5px] border-graphite-950">
            <Shield className="w-5 h-5 text-graphite-950" />
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <span className="font-display font-bold text-base tracking-tight text-graphite-100">
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
                    ? 'bg-brass-950 text-brass-300 border-[1.5px] border-brass-600 border-l-[3px] border-l-brass-500 font-semibold'
                    : 'text-graphite-400 hover:text-graphite-200 hover:bg-graphite-900/60 border-[1.5px] border-transparent'
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
      <div className="glass-panel p-4 m-3 rounded-xl space-y-2 text-xs">
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
        <div className="flex items-center gap-2.5 text-[10px] text-graphite-500 flex-wrap">
          <a href="/welcome" className="hover:text-brass-400 transition-colors">About</a>
          <span className="text-graphite-700">·</span>
          <a href="/privacy" className="hover:text-brass-400 transition-colors">Privacy Policy</a>
          <span className="text-graphite-700">·</span>
          <a href="/terms" className="hover:text-brass-400 transition-colors">Terms</a>
        </div>
      </div>
    </aside>
  );
};
