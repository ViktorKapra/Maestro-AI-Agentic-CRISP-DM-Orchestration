import { ProgressRail } from "../components/ProgressRail";
import { TokenChart } from "../components/TokenChart";
import {
  useCommunications,
  useCommunicationsSummary,
  useStatus,
} from "../hooks/useCasePolling";

interface Props {
  caseId: string;
}

export function Overview({ caseId }: Props) {
  const { data: status } = useStatus(caseId);
  const { data: summary } = useCommunicationsSummary(caseId);
  const { data: communications } = useCommunications(caseId);

  const lastComm = communications?.[communications.length - 1];

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <section className="rounded-2xl border border-surface-border bg-surface-raised p-5 space-y-4 glow-card">
        <h2 className="text-lg font-bold">📊 Progress</h2>
        <ProgressRail status={status} />
        {status && (
          <div className="space-y-2 text-sm">
            <p>
              <span className="text-slate-400 font-semibold">🌷 Phase:</span>{" "}
              {status.phase} — {status.phase_name}
            </p>
            <p>
              <span className="text-slate-400 font-semibold">🧩 Substep:</span>{" "}
              {status.substep} — {status.substep_name}
            </p>
            <p className="text-slate-300">💭 {status.activity}</p>
            {status.halted && (
              <p className="text-status-halted font-semibold">😵 Halted: {status.halt_reason}</p>
            )}
          </div>
        )}
      </section>

      <section className="rounded-2xl border border-surface-border bg-surface-raised p-5 glow-card">
        <h2 className="text-lg font-bold mb-4">🪙 Token spend</h2>
        <TokenChart
          summary={summary}
          communications={communications}
          tokenSpend={status?.token_spend}
        />
      </section>

      <section className="rounded-2xl border border-surface-border bg-surface-raised p-5 lg:col-span-2 glow-card">
        <h2 className="text-lg font-bold mb-2">💬 Activity</h2>
        <p className="text-sm text-slate-400">
          {status?.activity ?? "Waiting for status… 🕰️"}
        </p>
        {lastComm && (
          <p className="text-sm text-slate-500 mt-2">
            🦄 Last LLM turn:{" "}
            <span className="font-mono text-accent-muted">{lastComm.id}</span>{" "}
            ({lastComm.agent_name}, {lastComm.tokens?.total ?? "?"} tokens)
          </p>
        )}
        {summary && summary.parse_failures > 0 && (
          <p className="text-sm text-status-halted font-semibold mt-2">
            😬 {summary.parse_failures} parse failure(s) detected
          </p>
        )}
      </section>
    </div>
  );
}
