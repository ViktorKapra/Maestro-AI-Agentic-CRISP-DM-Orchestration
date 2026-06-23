import type { StatusPayload } from "../shared/types";

interface Props {
  status: StatusPayload | undefined;
}

export function ProgressRail({ status }: Props) {
  if (!status) {
    return (
      <div className="h-2 rounded-full bg-surface-border animate-pulse" />
    );
  }

  const pct =
    status.total_substeps > 0
      ? Math.round((status.completed_substeps / status.total_substeps) * 100)
      : 0;

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-slate-400">
        <span>
          {status.completed_substeps}/{status.total_substeps} substeps
        </span>
        <span>{pct}%</span>
      </div>
      <div className="h-2 rounded-full bg-surface-border overflow-hidden">
        <div
          className="h-full rounded-full bg-accent transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
