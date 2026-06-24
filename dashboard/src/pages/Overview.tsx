import { useEffect, useState } from "react";
import { ProgressRail } from "../components/ProgressRail";
import { TokenChart } from "../components/TokenChart";
import {
  useCommunications,
  useCommunicationsSummary,
  useStatus,
  useTraceSummary,
} from "../hooks/useCasePolling";
import { formatDuration } from "../shared/format";

interface Props {
  caseId: string;
}

function useElapsedMs(
  startedAt: string | undefined,
  endedAt: string | null | undefined,
  isRunning: boolean,
): number | null {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (!isRunning || !startedAt) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [isRunning, startedAt]);

  if (!startedAt) return null;
  const start = new Date(startedAt).getTime();
  const end = endedAt ? new Date(endedAt).getTime() : now;
  return Math.max(0, end - start);
}

export function Overview({ caseId }: Props) {
  const { data: status } = useStatus(caseId);
  const { data: trace } = useTraceSummary(caseId);
  const { data: summary } = useCommunicationsSummary(caseId);
  const { data: communications } = useCommunications(caseId);

  const lastComm = communications?.[communications.length - 1];
  const isRunning = trace != null && trace.ended_at == null && !status?.halted;
  const elapsedMs = useElapsedMs(trace?.started_at, trace?.ended_at, isRunning);

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <section className="rounded-xl border border-surface-border bg-surface-raised p-5 space-y-4">
        <h2 className="text-lg font-medium">Progress</h2>
        {elapsedMs != null && (
          <p className="text-sm">
            <span className="text-slate-400">Elapsed:</span>{" "}
            <span className="font-mono text-slate-100">
              {formatDuration(elapsedMs)}
            </span>
            {trace?.started_at && (
              <span className="text-slate-500 ml-2">
                (since {new Date(trace.started_at).toLocaleString()})
              </span>
            )}
          </p>
        )}
        <ProgressRail status={status} />
        {status && (
          <div className="space-y-2 text-sm">
            <p>
              <span className="text-slate-400">Phase:</span>{" "}
              {status.phase} — {status.phase_name}
            </p>
            <p>
              <span className="text-slate-400">Substep:</span>{" "}
              {status.substep} — {status.substep_name}
            </p>
            <p className="text-slate-300">{status.activity}</p>
            {status.halted && (
              <p className="text-red-400">Halted: {status.halt_reason}</p>
            )}
          </div>
        )}
      </section>

      <section className="rounded-xl border border-surface-border bg-surface-raised p-5">
        <h2 className="text-lg font-medium mb-4">Token spend</h2>
        <TokenChart
          summary={summary}
          communications={communications}
          tokenSpend={status?.token_spend}
        />
      </section>

      <section className="rounded-xl border border-surface-border bg-surface-raised p-5 lg:col-span-2">
        <h2 className="text-lg font-medium mb-2">Activity</h2>
        <p className="text-sm text-slate-400">
          {status?.activity ?? "Waiting for status…"}
        </p>
        {lastComm && (
          <p className="text-sm text-slate-500 mt-2">
            Last LLM turn:{" "}
            <span className="font-mono text-accent-muted">{lastComm.id}</span>{" "}
            ({lastComm.agent_name}, {lastComm.tokens?.total ?? "?"} tokens)
          </p>
        )}
        {summary && summary.parse_failures > 0 && (
          <p className="text-sm text-red-400 mt-2">
            {summary.parse_failures} parse failure(s) detected
          </p>
        )}
      </section>
    </div>
  );
}
