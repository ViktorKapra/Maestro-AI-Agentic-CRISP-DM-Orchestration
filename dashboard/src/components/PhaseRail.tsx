import type { ProcessPhase } from "../shared/types";
import { useTheme } from "../shared/theme";

interface Props {
  phases: ProcessPhase[] | undefined;
}

function phaseClasses(status: string, ready: boolean): string {
  if (status === "active") return "border-accent bg-accent/10 text-accent-muted";
  if (ready || status === "complete") return "border-emerald-600/50 bg-emerald-900/20 text-emerald-400";
  return "border-surface-border bg-surface text-slate-500";
}

export function PhaseRail({ phases }: Props) {
  const { clean } = useTheme();
  if (!phases?.length) {
    return <div className="h-16 rounded-lg bg-surface-border animate-pulse" />;
  }

  return (
    <div className="flex flex-wrap gap-2">
      {phases.map((phase, i) => (
        <div key={phase.id} className="flex items-center gap-2">
          <div
            className={`rounded-lg border px-3 py-2 text-sm min-w-[8rem] ${phaseClasses(phase.status, phase.ready)}`}
          >
            <div className="font-medium">
              {phase.ready && <span className="mr-1">{clean("✓")}</span>}
              {phase.id}. {phase.name}
            </div>
            <div className="text-xs opacity-70 capitalize">{phase.status}</div>
          </div>
          {i < phases.length - 1 && (
            <span className="text-slate-600 hidden sm:inline">→</span>
          )}
        </div>
      ))}
    </div>
  );
}
