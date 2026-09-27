import React, { useState } from 'react';
import { LucideIcon } from 'lucide-react';

export interface TabItem {
  id: string;
  label: string;
  icon?: LucideIcon;
}

interface TabsProps {
  tabs: TabItem[];
  defaultTabId?: string;
  children: (activeTabId: string) => React.ReactNode;
}

export const Tabs: React.FC<TabsProps> = ({ tabs, defaultTabId, children }) => {
  const [activeTabId, setActiveTabId] = useState(defaultTabId || tabs[0]?.id);

  return (
    <div className="space-y-4">
      <div
        role="tablist"
        className="flex items-center gap-6 border-b border-hairline overflow-x-auto"
      >
        {tabs.map((tab) => {
          const isActive = tab.id === activeTabId;
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              role="tab"
              aria-selected={isActive}
              onClick={() => setActiveTabId(tab.id)}
              className="tab-flat flex items-center gap-1.5 whitespace-nowrap"
            >
              {Icon && <Icon className="w-3.5 h-3.5" strokeWidth={1.75} />}
              {tab.label}
            </button>
          );
        })}
      </div>

      <div role="tabpanel" className="animate-fade-in">{children(activeTabId)}</div>
    </div>
  );
};
