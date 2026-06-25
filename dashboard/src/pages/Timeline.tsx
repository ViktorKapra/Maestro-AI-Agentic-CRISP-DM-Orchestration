import { useState } from "react";
import type { TraceEvent } from "../shared/types";
import { useTraceSummary } from "../hooks/useCasePolling";

interface Props {
  caseId: string;
  onOpenComm?: (commId: string) => void;
}

function formatEvent(evt: TraceEvent): string {
  const attrs = evt.attributes;
  let extra = "";
  if (evt.type === "substep.dispatch") {
    extra = ` [${attrs.substep}] → ${attrs.owner ?? "?"}`;
  } else if (evt.type === "llm.end" || evt.type === "crew.end") {
    if (attrs.total_tokens) extra += ` tokens=${attrs.total_tokens}`;
  }
  const comm = attrs.communication_id;
  if (comm && ["llm.start", "llm.end", "crew.start", "crew.end"].includes(evt.type)) {
    extra += ` ${comm}`;
  }
  const dur = evt.duration_ms != null ? ` (${evt.duration_ms}ms)` : "";
  return `${evt.name || evt.type}${extra}${dur}`;
}

export function Timeline({ caseId, onOpenComm }: Props) {
  const { data: trace } = useTraceSummary(caseId);
  const [filter, setFilter] = useState("");

  const events = (trace?.events ?? []).filter((evt) => {
    if (!filter) return true;
    const q = filter.toLowerCase();
    return (
      evt.type.includes(q) ||
      evt.name.toLowerCase().includes(q) ||
      String(evt.attributes.communication_id ?? "").includes(q)
    );
  });

  return (
    <div className="space-y-4">
      <input
        type="search"
        placeholder="🔎 Filter by type, name, or comm_id…"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        className="w-full max-w-md rounded-full border border-surface-border bg-surface-raised px-4 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-accent/40"
      />

      <p className="text-xs text-slate-500 font-medium">
        ⏳ {events.length} events
        {trace?.ended_at ? " · run complete 🎀" : " · run in progress 💫"}
      </p>

      <div className="rounded-2xl border border-surface-border overflow-hidden glow-card">
        <table className="w-full text-sm">
          <thead className="bg-surface-raised text-slate-400 text-left">
            <tr>
              <th className="px-3 py-2 font-medium w-24">T+</th>
              <th className="px-3 py-2 font-medium w-36">Type</th>
              <th className="px-3 py-2 font-medium">Event</th>
            </tr>
          </thead>
          <tbody>
            {events.map((evt) => {
              const commId = evt.attributes.communication_id as
                | string
                | undefined;
              return (
                <tr
                  key={evt.id}
                  className="border-t border-surface-border hover:bg-surface-raised/50"
                >
                  <td className="px-3 py-1.5 font-mono text-xs text-slate-500">
                    {Math.round(evt.ts_mono_ms)}ms
                  </td>
                  <td className="px-3 py-1.5 font-mono text-xs text-accent-muted">
                    {evt.type}
                  </td>
                  <td className="px-3 py-1.5">
                    {formatEvent(evt)}
                    {commId && onOpenComm && (
                      <button
                        type="button"
                        onClick={() => onOpenComm(commId)}
                        className="ml-2 text-xs text-accent hover:underline"
                      >
                        view
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
