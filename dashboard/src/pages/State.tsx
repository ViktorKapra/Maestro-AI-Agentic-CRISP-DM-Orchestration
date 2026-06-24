import { useState } from "react";
import { JsonTree } from "../components/JsonTree";
import { StateSection } from "../components/StateSection";
import { useCrispDMState } from "../hooks/useCasePolling";

interface Props {
  caseId: string;
}

type ViewMode = "structured" | "raw";

const RUNTIME_KEYS = [
  "phase",
  "substep",
  "halted",
  "halt_reason",
  "validator_findings",
  "token_spend",
] as const;

const PHASE_SECTIONS = [
  { key: "bu", title: "Phase 1 — Business Understanding" },
  { key: "du", title: "Phase 2 — Data Understanding" },
  { key: "dp", title: "Phase 3 — Data Preparation" },
  { key: "md", title: "Phase 4 — Modeling" },
  { key: "ev", title: "Phase 5 — Evaluation" },
  { key: "dep", title: "Phase 6 — Deployment" },
] as const;

export function State({ caseId }: Props) {
  const { data: payload, isLoading, error } = useCrispDMState(caseId);
  const [view, setView] = useState<ViewMode>("structured");
  const [copied, setCopied] = useState(false);

  const state = payload?.state;

  const copyRaw = async () => {
    if (!state) return;
    await navigator.clipboard.writeText(JSON.stringify(state, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (error) {
    return (
      <p className="text-red-400 text-sm">
        Could not load state — run may not have started yet.
      </p>
    );
  }

  if (isLoading && !payload) {
    return <p className="text-slate-500">Loading state…</p>;
  }

  if (!state || Object.keys(state).length === 0) {
    return <p className="text-slate-500">No CrispDMState data available yet.</p>;
  }

  const runtimeData = Object.fromEntries(
    RUNTIME_KEYS.map((k) => [k, (state as Record<string, unknown>)[k]]),
  );

  return (
    <div className="space-y-4">
      <section className="rounded-xl border border-surface-border bg-surface-raised p-4 flex flex-wrap items-center gap-4 justify-between">
        <div className="space-y-1 text-sm">
          <p>
            <span className="text-slate-400">Case:</span>{" "}
            <span className="font-mono">{state.case_id as string}</span>
          </p>
          <p>
            <span className="text-slate-400">Position:</span> phase {String(state.phase)}{" "}
            · substep {String(state.substep)}
          </p>
          {payload?.updated_at && (
            <p className="text-xs text-slate-500">
              Updated {new Date(payload.updated_at).toLocaleString()}
            </p>
          )}
          {Boolean(state.halted) && state.halt_reason != null && (
            <p className="text-red-400">Halted: {String(state.halt_reason)}</p>
          )}
        </div>
        <span
          className={`text-xs px-2 py-1 rounded-full ${
            payload?.source === "live"
              ? "bg-status-running/20 text-status-running"
              : "bg-surface-border text-slate-400"
          }`}
        >
          {payload?.source ?? "unknown"}
        </span>
      </section>

      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => setView("structured")}
          className={`rounded-lg px-3 py-1.5 text-sm ${
            view === "structured"
              ? "bg-accent text-white"
              : "text-slate-400 hover:bg-surface-border"
          }`}
        >
          Structured
        </button>
        <button
          type="button"
          onClick={() => setView("raw")}
          className={`rounded-lg px-3 py-1.5 text-sm ${
            view === "raw"
              ? "bg-accent text-white"
              : "text-slate-400 hover:bg-surface-border"
          }`}
        >
          Raw JSON
        </button>
        {view === "raw" && (
          <button
            type="button"
            onClick={copyRaw}
            className="ml-auto rounded-lg border border-surface-border px-3 py-1.5 text-sm text-slate-400 hover:text-slate-200"
          >
            {copied ? "Copied" : "Copy"}
          </button>
        )}
      </div>

      {view === "structured" ? (
        <div className="space-y-2">
          <StateSection
            title="Runtime"
            description="Current orchestrator position and control flags"
            data={runtimeData}
            defaultOpen
          />
          {PHASE_SECTIONS.map((s) => (
            <StateSection
              key={s.key}
              title={s.title}
              data={(state as Record<string, unknown>)[s.key]}
            />
          ))}
          <StateSection title="Config" data={state.config} />
          <StateSection title="Loop history" data={state.loop_history} />
          <StateSection title="Log" data={state.log} defaultOpen={false} />
        </div>
      ) : (
        <div className="rounded-xl border border-surface-border bg-surface-raised p-4 max-h-[70vh] overflow-auto">
          <JsonTree value={state} defaultOpen />
        </div>
      )}
    </div>
  );
}
