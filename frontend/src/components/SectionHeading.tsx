import React from 'react';

interface SectionHeadingProps {
  title: string;
  description?: string;
  level?: 'h1' | 'h3';
  icon?: React.ReactNode;
  action?: React.ReactNode;
}

/**
 * Plain sentence-case heading with an optional one-line description below
 * it — replaces the all-caps, tracked-out "eyebrow label" pattern
 * previously repeated across nearly every page. Matches the treatment
 * AuditTrailPage.tsx already established.
 */
export const SectionHeading: React.FC<SectionHeadingProps> = ({
  title,
  description,
  level = 'h1',
  icon,
  action
}) => {
  const titleClasses =
    level === 'h1'
      ? 'font-display text-lg font-bold tracking-tight text-graphite-100'
      : 'font-display text-sm font-bold tracking-tight text-graphite-200';

  const Tag = level;

  return (
    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
      <div>
        <Tag className={`${titleClasses} flex items-center gap-2`}>
          {icon}
          {title}
        </Tag>
        {description && (
          <p className="text-sm text-graphite-500 mt-0.5">{description}</p>
        )}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
};
