import React, { useState } from 'react';
import { ShieldCheck, Info, X } from 'lucide-react';

export const PrivacyNotice: React.FC = () => {
  const [dismissed, setDismissed] = useState(false);

  if (dismissed) return null;

  return (
    <div className="flex items-center justify-between gap-3 text-[11px] text-muted">
      <div className="flex items-center gap-2 min-w-0">
        <ShieldCheck className="w-3.5 h-3.5 shrink-0" strokeWidth={1.75} />
        <p className="truncate">
          Synthetic demo data — never connects to real law-enforcement databases. Identifiers are SHA-256 hashed.
        </p>
      </div>
      <button
        onClick={() => setDismissed(true)}
        className="text-muted hover:text-ink p-1 transition-colors shrink-0 cursor-pointer"
        title="Dismiss notice"
      >
        <X className="w-3.5 h-3.5" strokeWidth={1.75} />
      </button>
    </div>
  );
};
