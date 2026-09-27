import React from 'react';
import { Check, Loader2, AlertCircle } from 'lucide-react';
import { SectionHeading } from './SectionHeading';

export interface PipelineStage {
  id: string;
  name: string;
  status: 'pending' | 'running' | 'completed' | 'error';
  latencyMs?: number;
  detail?: string;
}

interface ProcessingPipelineProps {
  stages: PipelineStage[];
  title?: string;
}

/**
 * Left-to-right step flow -- this literally is the document-screening
 * pipeline (upload -> OCR -> MRZ -> tamper -> face -> risk -> case file),
 * so it's shown as one, not as a stack of identical rows.
 */
export const ProcessingPipeline: React.FC<ProcessingPipelineProps> = ({
  stages,
  title = 'Screening pipeline'
}) => {
  return (
    <div>
      <SectionHeading level="h3" title={title} />

      <div className="mt-4 flex flex-col sm:flex-row sm:items-start gap-0">
        {stages.map((st, index) => {
          const isLast = index === stages.length - 1;
          const nodeColor =
            st.status === 'completed'
              ? 'bg-signal-low border-signal-low text-paper'
              : st.status === 'running'
              ? 'bg-accent border-accent text-paper'
              : st.status === 'error'
              ? 'bg-signal-critical border-signal-critical text-paper'
              : 'bg-paper border-hairline text-muted';

          return (
            <div key={st.id} className="flex sm:flex-1 sm:flex-col items-start sm:items-center gap-3 sm:gap-2">
              {/* Node + connecting line */}
              <div className="flex sm:flex-col items-center gap-0 shrink-0 sm:w-full">
                <div className="flex sm:flex-row items-center w-full">
                  <div
                    className={`w-7 h-7 rounded-full border flex items-center justify-center shrink-0 transition-colors ${nodeColor}`}
                  >
                    {st.status === 'completed' ? (
                      <Check className="w-3.5 h-3.5" strokeWidth={1.75} />
                    ) : st.status === 'running' ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" strokeWidth={1.75} />
                    ) : st.status === 'error' ? (
                      <AlertCircle className="w-3.5 h-3.5" strokeWidth={1.75} />
                    ) : (
                      <span className="figure text-[11px]">{index + 1}</span>
                    )}
                  </div>
                  {!isLast && (
                    <div
                      className={`hidden sm:block h-px flex-1 ${
                        st.status === 'completed' ? 'bg-signal-low' : 'bg-hairline'
                      }`}
                    />
                  )}
                </div>
              </div>

              {/* Label + detail */}
              <div className="flex-1 sm:text-center min-w-0 pb-4 sm:pb-0">
                <div className="flex items-center sm:justify-center gap-1.5">
                  <span
                    className={`text-[11px] font-bold ${
                      st.status === 'pending' ? 'text-muted' : 'text-ink'
                    }`}
                  >
                    {st.name}
                  </span>
                  {st.latencyMs !== undefined && (
                    <span className="text-[11px] text-muted figure">{Math.round(st.latencyMs)}ms</span>
                  )}
                </div>
                {st.detail && (
                  <p className="text-[11px] text-muted mt-0.5 sm:max-w-[10rem] sm:mx-auto" title={st.detail}>
                    {st.detail}
                  </p>
                )}
              </div>

              {/* Vertical connector for the mobile/stacked layout */}
              {!isLast && (
                <div className="sm:hidden w-px self-stretch bg-hairline ml-3.5" />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
