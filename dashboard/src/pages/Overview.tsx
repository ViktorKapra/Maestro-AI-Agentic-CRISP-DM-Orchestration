import { useEffect, useState } from "react";
import { HandoffDownloadLink } from "../components/HandoffDownloadLink";
import { ProgressRail } from "../components/ProgressRail";
import { TokenChart } from "../components/TokenChart";
import { useCommunicationsSummary, useLiveSummary } from "../hooks/useCasePolling";
import { formatDuration } from "../shared/format";
import type { LiveSummary, StatusPayload } from "../shared/types";

interface Props {
  caseId: string;
}

function useElapsedMs(live: LiveSummary | undefined): number | null {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (!live || live.halted || live.trace.ended_at) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [live]);

  if (!live?.trace.started_at) return live?.elapsed_ms ?? null;
  const start = new Date(live.trace.started_at).getTime();
  const end = live.trace.ended_at
    ? new Date(live.trace.ended_at).getTime()
    : now;
  return Math.max(0, end - start);
}

function statusFromLive(live: LiveSummary): StatusPayload {
  return {
    updated_at: live.updated_at,
    case_id: live.case_id,
    phase: live.phase,
    phase_name: live.phase_name,
    substep: live.substep,
    substep_name: live.substep_name,
    activity: live.activity,
    completed_substeps: live.progress.completed_substeps,
    total_substeps: live.progress.total_substeps,
    token_spend: live.token_spend,
    halted: live.halted,
    halt_reason: live.halt_reason,
    workflow_complete: live.workflow_complete,
    ml_success: live.ml_success,
    ml_deficits: live.ml_deficits,
    artifact_dir: "",
    trace_dir: "",
  };
}

export function Overview({ caseId }: Props) {
  const { data: live } = useLiveSummary(caseId);
  const { data: summary } = useCommunicationsSummary(caseId);

  const elapsedMs = useElapsedMs(live);
  const isRunning = live != null && !live.halted && live.trace.ended_at == null;
  const status = live ? statusFromLive(live) : undefined;

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <section className="rounded-2xl border border-surface-border bg-surface-raised p-5 space-y-4 glow-card">
        <h2 className="text-lg font-bold">📊 Progress</h2>
        {elapsedMs != null && (
          <p className="text-sm">
            <span className="text-slate-400">Elapsed:</span>{" "}
            <span className="font-mono text-slate-100">
              {formatDuration(elapsedMs)}
            </span>
            {live?.trace.started_at && (
              <span className="text-slate-500 ml-2">
                (since {new Date(live.trace.started_at).toLocaleString()})
              </span>
            )}
          </p>
        )}
        <ProgressRail status={status} />
        {live && (
          <div className="space-y-2 text-sm">
            <p>
              <span className="text-slate-400 font-semibold">🌷 Phase:</span>{" "}
              {live.phase} — {live.phase_name}
            </p>
            <p>
              <span className="text-slate-400 font-semibold">🧩 Substep:</span>{" "}
              {live.substep} — {live.substep_name}
            </p>
            <p className="text-slate-300">💭 {live.activity}</p>
            {live.halted && (
              <p className="text-status-halted font-semibold">😵 Halted: {live.halt_reason}</p>
            )}
            {live.workflow_complete != null && (
              <p>
                <span className="text-slate-400 font-semibold">🎀 Workflow:</span>{" "}
                {live.workflow_complete ? "complete" : "incomplete"}
              </p>
            )}
            {live.ml_success != null && (
              <p className={live.ml_success ? "text-green-400" : "text-amber-400"}>
                ML outcome: {live.ml_success ? "success ✨" : "failed 😵"}
                {live.ml_deficits && live.ml_deficits.length > 0 && (
                  <span className="text-slate-400">
                    {" "}
                    ({live.ml_deficits.join("; ")})
                  </span>
                )}
              </p>
            )}
            <HandoffDownloadLink
              caseId={caseId}
              show={Boolean(live.halted || live.workflow_complete)}
              className="pt-2 border-t border-surface-border/60"
            />
          </div>
        )}
      </section>

      <section className="rounded-2xl border border-surface-border bg-surface-raised p-5 glow-card">
        <h2 className="text-lg font-bold mb-4">🪙 Token spend</h2>
        <TokenChart
          summary={summary}
          tokenSpend={live?.token_spend}
        />
      </section>

      <section className="rounded-2xl border border-surface-border bg-surface-raised p-5 lg:col-span-2 glow-card">
        <h2 className="text-lg font-bold mb-2">💬 Activity</h2>
        <p className="text-sm text-slate-400">
          {live?.activity ?? "Waiting for status… 🕰️"}
        </p>
        {live?.in_flight && (
          <p className="text-sm text-yellow-400/90 mt-2">
            In-flight LLM:{" "}
            <span className="font-mono">{live.in_flight.communication_id}</span>{" "}
            ({live.in_flight.agent}, substep {live.in_flight.substep})
          </p>
        )}
        {live?.last_comm && (
          <p className="text-sm text-slate-500 mt-2">
            🦄 Last LLM turn:{" "}
            <span className="font-mono text-accent-muted">{live.last_comm.id}</span>{" "}
            ({live.last_comm.agent}, {live.last_comm.tokens ?? "?"} tokens)
          </p>
        )}
        {summary && summary.parse_failures > 0 && (
          <p className="text-sm text-status-halted font-semibold mt-2">
            😬 {summary.parse_failures} parse failure(s) detected
          </p>
        )}
        {isRunning && (
          <p className="text-xs text-slate-600 mt-3">
            Polling live summary only (~{live ? "<10" : "?"} KB/tick). Open
            Communications for full LLM turns.
          </p>
        )}
      </section>
    </div>
  );
}
