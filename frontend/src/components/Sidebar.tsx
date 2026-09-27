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
    <aside className="w-64 bg-paper border-r border-hairline flex flex-col justify-between shrink-0 select-none z-20">
      <div>
        {/* Brand header -- serif wordmark with a trailing accent period,
            per the nav bar spec, rather than a logo mark. */}
        <div className="px-5 py-5 border-b border-hairline flex items-center gap-2.5">
          <Shield className="w-[18px] h-[18px] text-ink shrink-0" strokeWidth={1.75} />
          <div>
            <span className="font-display text-[19px] tracking-tight text-ink">
              BorderMesh<span className="text-accent">.</span>
            </span>
            <p className="text-[10px] text-muted tracking-[0.09em] uppercase -mt-0.5">
              AI identity screening
            </p>
          </div>
        </div>

        {/* Navigation -- a hairline-ruled list, not buttons with a fill;
            active state is a left ink rule, never a filled pill. */}
        <nav className="py-2">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = currentTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onSelectTab(item.id)}
                className={`w-full flex items-center justify-between gap-3 px-5 py-2.5 text-[11px] uppercase tracking-[0.06em] cursor-pointer border-l-2 transition-colors duration-150 ${
                  active
                    ? 'border-l-ink text-ink font-bold'
                    : 'border-l-transparent text-ink-soft hover:text-ink'
                }`}
              >
                <span className="flex items-center gap-3">
                  <Icon className="w-3.5 h-3.5 shrink-0" strokeWidth={1.75} />
                  <span>{item.label}</span>
                </span>
                {item.badge !== undefined && item.badge > 0 && (
                  <span className="text-signal-medium font-bold">{item.badge}</span>
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {/* System status footer -- hairline rows, no boxed panel. */}
      <div className="px-5 py-4 border-t border-hairline text-[10px] space-y-2">
        <div className="flex items-center justify-between text-ink-soft">
          <span>AI Pipeline</span>
          <span className="text-accent font-bold uppercase">Online</span>
        </div>
        <div className="flex items-center justify-between gap-2 text-ink-soft">
          <span className="truncate">Watchlist Adapter</span>
          <span className="shrink-0">Sandbox Demo</span>
        </div>
        <div className="pt-2 border-t border-hairline text-muted">
          SIH Problem: SIH26188
        </div>
        <div className="flex items-center gap-2 text-muted flex-wrap pt-1">
          <a href="/welcome" className="hover:text-accent transition-colors">About</a>
          <span>&middot;</span>
          <a href="/privacy" className="hover:text-accent transition-colors">Privacy Policy</a>
          <span>&middot;</span>
          <a href="/terms" className="hover:text-accent transition-colors">Terms</a>
        </div>
      </div>
    </aside>
  );
};
