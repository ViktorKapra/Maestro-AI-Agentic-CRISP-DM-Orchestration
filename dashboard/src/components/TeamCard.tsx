import type { TeamMember } from "../shared/types";

interface Props {
  member: TeamMember;
}

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}

export function TeamCard({ member }: Props) {
  const isActive = member.status === "active";

  return (
    <div
      className={`rounded-xl border p-4 space-y-3 ${
        isActive
          ? "border-accent/50 bg-accent/5"
          : "border-surface-border bg-surface-raised"
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <h3 className="font-medium text-slate-100">{member.label}</h3>
        <span
          className={`text-xs px-2 py-0.5 rounded-full ${
            isActive
              ? "bg-status-running/20 text-status-running"
              : "bg-surface-border text-slate-500"
          }`}
        >
          {member.status}
        </span>
      </div>

      {member.current_substep && (
        <p className="text-sm text-accent-muted">
          Working on §{member.current_substep}
        </p>
      )}

      <p className="text-xs text-slate-500">
        {formatTokens(member.tokens)} tokens · owns {member.owned_substeps.length}{" "}
        substeps
      </p>

      {member.recent_work.length > 0 && (
        <ul className="text-xs text-slate-400 space-y-1 border-t border-surface-border pt-2">
          {member.recent_work.map((entry, i) => (
            <li key={i} className="truncate" title={entry.message}>
              {entry.level === "warn" && (
                <span className="text-amber-400 mr-1">!</span>
              )}
              {entry.message}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
