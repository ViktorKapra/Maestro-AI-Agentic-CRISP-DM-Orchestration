import { useEffect, useMemo, useState } from "react";
import type { RunStatus, TabId } from "./shared/types";
import { BIZ_THEME_NAME, useTheme } from "./shared/theme";
import type { ThemeId } from "./shared/theme";
import { useCaseRuns, useCases } from "./hooks/useCasePolling";
import { useSelectedRun } from "./shared/selectedRun";
import { Overview } from "./pages/Overview";
import { Process } from "./pages/Process";
import { State } from "./pages/State";
import { Communications } from "./pages/Communications";
import { Architecture } from "./pages/Architecture";
import { Timeline } from "./pages/Timeline";
import { Knowledge } from "./pages/Knowledge";
import { Framework } from "./pages/Framework";
import { Prompts } from "./pages/Prompts";
import { StateShape } from "./pages/StateShape";
import { LoopLogic } from "./pages/LoopLogic";
import { FailureModes } from "./pages/FailureModes";
import { Launch } from "./pages/Launch";

const TABS: { id: TabId; label: string }[] = [
  { id: "launch", label: "🚀 Launch" },
  { id: "overview", label: "💖 Overview" },
  { id: "process", label: "🌸 Process" },
  { id: "knowledge", label: "📚 Knowledge" },
  { id: "state", label: "🗂️ State" },
  { id: "communications", label: "💬 Communications" },
  { id: "architecture", label: "🦋 Architecture" },
  { id: "timeline", label: "⏳ Timeline" },
  { id: "framework", label: "🔬 Framework" },
  { id: "prompts", label: "📝 Prompts" },
  { id: "state_shape", label: "🏗️ State Shape" },
  { id: "loop_logic", label: "🔄 Loop Logic" },
  { id: "failure_modes", label: "🩹 Failures" },
];

function ThemeToggle({
  theme,
  onChange,
}: {
  theme: ThemeId;
  onChange: (t: ThemeId) => void;
}) {
  const base = "rounded-full px-3 py-1 transition-all whitespace-nowrap";
  const active =
    "bg-gradient-to-r from-fuchsia-500 to-pink-500 text-white shadow";
  const idle = "text-slate-400 hover:text-slate-200";
  return (
    <div
      role="group"
      aria-label="Theme"
      title="Switch the look of the dashboard"
      className="flex items-center gap-1 rounded-full border border-surface-border bg-surface p-1 text-xs font-semibold shadow-sm"
    >
      <button
        type="button"
        onClick={() => onChange("pink")}
        aria-pressed={theme === "pink"}
        className={`${base} ${theme === "pink" ? active : idle}`}
      >
        {theme === "biz" ? "Pink" : "🌸 Pink"}
      </button>
      <button
        type="button"
        onClick={() => onChange("biz")}
        aria-pressed={theme === "biz"}
        className={`${base} ${theme === "biz" ? active : idle}`}
      >
        {BIZ_THEME_NAME}
      </button>
    </div>
  );
}

function statusDot(status: RunStatus | undefined) {
  if (status === "running") return "bg-status-running";
  if (status === "halted") return "bg-status-halted";
  return "bg-status-complete";
}

function statusLabel(status: RunStatus | undefined) {
  if (status === "running") return "Running ✨";
  if (status === "halted") return "Halted 😵";
  if (status === "complete") return "Complete 🎀";
  return "Unknown 🤔";
}

export default function App() {
  const { data: cases, isLoading, error } = useCases();
  const [caseId, setCaseId] = useState<string | null>(null);
  const [tab, setTab] = useState<TabId>("overview");
  const [highlightComm, setHighlightComm] = useState<string | null>(null);
  const { theme, setTheme, clean } = useTheme();
  const { runId, setRunId } = useSelectedRun();
  const { data: runs } = useCaseRuns(caseId);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const fromUrl = params.get("case");
    if (fromUrl) setCaseId(fromUrl);
  }, []);

  useEffect(() => {
    if (!caseId && cases?.length) {
      setCaseId(cases[0].case_id);
    }
  }, [cases, caseId]);

  // When the case changes, follow its active run until the user picks one.
  useEffect(() => {
    setRunId(null);
  }, [caseId, setRunId]);

  const activeCase = useMemo(
    () => cases?.find((c) => c.case_id === caseId),
    [cases, caseId],
  );

  const selectedRun = useMemo(
    () => runs?.find((r) => r.run_id === runId),
    [runs, runId],
  );
  const shownModel = selectedRun?.model ?? activeCase?.model ?? null;
  const shownStatus = selectedRun?.status ?? activeCase?.status;

  const openComm = (commId: string) => {
    setHighlightComm(commId);
    setTab("communications");
    setTimeout(() => {
      document.getElementById(`comm-${commId}`)?.scrollIntoView({
        behavior: "smooth",
        block: "center",
      });
    }, 100);
  };

  if (error) {
    return (
      <div className="p-8 text-center">
        <p className="text-status-halted font-semibold">
          {clean("😢 Cannot reach API — is the dashboard server running?")}
        </p>
        <p className="text-sm text-slate-500 mt-2">
          Run: <code className="text-accent-muted">python -m maads dashboard --no-open</code>
        </p>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-surface-border bg-surface-raised/80 backdrop-blur px-6 py-4 shadow-sm">
        <div className="flex flex-wrap items-center gap-4 justify-between max-w-7xl mx-auto">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight bg-gradient-to-r from-fuchsia-500 via-pink-500 to-purple-500 bg-clip-text text-transparent">
              {clean("🌸 MAADS Trace ✨")}
            </h1>
            {activeCase && (
              <span className="flex items-center gap-2 text-sm font-semibold rounded-full bg-surface px-3 py-1 border border-surface-border">
                <span
                  className={`h-2.5 w-2.5 rounded-full ${statusDot(shownStatus)} ${
                    shownStatus === "running" ? "node-active" : ""
                  }`}
                />
                {clean(statusLabel(shownStatus))}
              </span>
            )}
          </div>

          <div className="flex items-center gap-3">
            <div className="flex flex-col items-end gap-1">
              <div className="flex items-center gap-2">
                <select
                  value={caseId ?? ""}
                  onChange={(e) => setCaseId(e.target.value)}
                  disabled={isLoading}
                  className="rounded-full border border-surface-border bg-surface px-4 py-1.5 text-sm font-medium shadow-sm focus:outline-none focus:ring-2 focus:ring-accent/40"
                >
                  {!cases?.length && (
                    <option value="">{clean("No cases 😴")}</option>
                  )}
                  {cases?.map((c) => (
                    <option key={c.case_id} value={c.case_id}>
                      {clean(`🎀 ${c.case_id} (${c.status})`)}
                    </option>
                  ))}
                </select>
                <select
                  value={runId ?? ""}
                  onChange={(e) => setRunId(e.target.value || null)}
                  disabled={!runs?.length}
                  title="Pick which run of this case to view"
                  className="rounded-full border border-surface-border bg-surface px-4 py-1.5 text-sm font-medium shadow-sm focus:outline-none focus:ring-2 focus:ring-accent/40 max-w-[16rem]"
                >
                  <option value="">{clean("⚡ active run")}</option>
                  {runs?.map((r, i) => (
                    <option key={r.run_id} value={r.run_id}>
                      {`#${(runs.length - i)} · ${r.model ?? "default"} · ${r.status}`}
                    </option>
                  ))}
                </select>
              </div>
              <span
                className="text-xs font-mono rounded-full bg-surface px-3 py-0.5 border border-surface-border text-slate-400"
                title="LLM this run was launched with"
              >
                {clean("🧠 ")}{shownModel ?? "default (.env)"}
              </span>
            </div>
            <ThemeToggle theme={theme} onChange={setTheme} />
          </div>
        </div>

        {activeCase && (
          <p className="text-sm text-slate-400 mt-2 max-w-7xl mx-auto font-medium">
            {clean("🌷")} Phase {activeCase.phase} — {activeCase.phase_name} ·{" "}
            {activeCase.completed_substeps}/{activeCase.total_substeps} substeps
          </p>
        )}

        <nav className="flex flex-wrap gap-2 mt-4 max-w-7xl mx-auto">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setTab(t.id)}
              className={`rounded-full px-4 py-2 text-sm font-semibold transition-all ${
                tab === t.id
                  ? "bg-gradient-to-r from-fuchsia-500 to-pink-500 text-white shadow-md scale-105"
                  : "text-slate-400 hover:bg-surface-border hover:text-slate-200"
              }`}
            >
              {clean(t.label)}
            </button>
          ))}
        </nav>
      </header>

      <main className="flex-1 p-6 max-w-7xl mx-auto w-full">
        {tab === "launch" ? (
          <Launch onLaunched={(id) => setCaseId(id)} />
        ) : tab === "framework" ? (
          <Framework />
        ) : tab === "prompts" ? (
          <Prompts />
        ) : tab === "state_shape" ? (
          <StateShape />
        ) : tab === "loop_logic" ? (
          <LoopLogic />
        ) : tab === "failure_modes" ? (
          <FailureModes />
        ) : !caseId ? (
          <p className="text-slate-500">
            {clean("💫 Select a case or start one from the Launch tab!")}
          </p>
        ) : (
          <>
            {tab === "overview" && <Overview caseId={caseId} />}
            {tab === "process" && <Process caseId={caseId} />}
            {tab === "knowledge" && <Knowledge caseId={caseId} />}
            {tab === "state" && <State caseId={caseId} />}
            {tab === "communications" && (
              <Communications
                caseId={caseId}
                highlightCommId={highlightComm}
              />
            )}
            {tab === "architecture" && <Architecture caseId={caseId} />}
            {tab === "timeline" && (
              <Timeline caseId={caseId} onOpenComm={openComm} />
            )}
          </>
        )}
      </main>
    </div>
  );
}
