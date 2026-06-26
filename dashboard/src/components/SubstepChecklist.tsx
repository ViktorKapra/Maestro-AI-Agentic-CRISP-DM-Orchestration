import { useState } from "react";
import type { ProcessPhase } from "../shared/types";
import { formatDuration } from "../shared/format";
import { useTheme } from "../shared/theme";

interface Props {
  phases: ProcessPhase[] | undefined;
  currentPhase?: number;
}

function statusIcon(status: string): string {
  switch (status) {
    case "done":
      return "✓";
    case "active":
      return "●";
    case "skipped":
      return "⊘";
    default:
      return "○";
  }
}

function statusColor(status: string): string {
  switch (status) {
    case "done":
      return "text-emerald-400";
    case "active":
      return "text-accent";
    case "skipped":
      return "text-amber-400";
    default:
      return "text-slate-600";
  }
}

export function SubstepChecklist({ phases, currentPhase = 1 }: Props) {
  const { clean } = useTheme();
  const [openPhases, setOpenPhases] = useState<Set<number>>(
    () => new Set([currentPhase]),
  );

  if (!phases?.length) {
    return <div className="h-32 rounded-lg bg-surface-border animate-pulse" />;
  }

  const toggle = (id: number) => {
    setOpenPhases((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <div className="space-y-2">
      {phases.map((phase) => {
        const isOpen = openPhases.has(phase.id);
        const doneCount = phase.substeps.filter((s) => s.status === "done").length;
        return (
          <div
            key={phase.id}
            className="rounded-lg border border-surface-border overflow-hidden"
          >
            <button
              type="button"
              onClick={() => toggle(phase.id)}
              className="w-full flex items-center justify-between px-4 py-2 text-sm text-left hover:bg-surface-border/50"
            >
              <span className="font-medium">
                Phase {phase.id}: {phase.name}
              </span>
              <span className="text-slate-500 text-xs">
                {doneCount}/{phase.substeps.length} done {isOpen ? clean("▾") : clean("▸")}
              </span>
            </button>
            {isOpen && (
              <ul className="border-t border-surface-border divide-y divide-surface-border">
                {phase.substeps.map((sub) => (
                  <li
                    key={sub.id}
                    className={`flex items-center gap-3 px-4 py-2 text-sm ${
                      sub.status === "active" ? "bg-accent/5" : ""
                    }`}
                  >
                    <span className={`w-4 text-center ${statusColor(sub.status)}`}>
                      {clean(statusIcon(sub.status))}
                    </span>
                    <span className="font-mono text-xs text-slate-500 w-8">
                      {sub.id}
                    </span>
                    <span className="flex-1 text-slate-300">{sub.name}</span>
                    <span className="text-xs text-slate-500">{sub.owner_label}</span>
                    {sub.duration_ms != null && (
                      <span className="text-xs text-slate-600 font-mono">
                        {formatDuration(sub.duration_ms)}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        );
      })}
    </div>
  );
}
