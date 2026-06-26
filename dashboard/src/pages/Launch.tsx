import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { fetchConfigs, postStartRun } from "../shared/api";
import type { CaseConfig } from "../shared/types";

type LaunchState = "idle" | "launching" | "launched" | "error";

export function Launch({ onLaunched }: { onLaunched?: (caseId: string) => void }) {
  const { data: configs, isLoading, error } = useQuery({
    queryKey: ["configs"],
    queryFn: fetchConfigs,
  });

  const [selected, setSelected] = useState<string>("");
  const [launchState, setLaunchState] = useState<LaunchState>("idle");
  const [launchedCase, setLaunchedCase] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const activeConfig: CaseConfig | undefined = configs?.find((c) => c.case_id === selected);

  const handleStart = async () => {
    if (!selected) return;
    setLaunchState("launching");
    setErrorMsg(null);
    try {
      await postStartRun(selected);
      setLaunchedCase(selected);
      setLaunchState("launched");
      onLaunched?.(selected);
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : String(e));
      setLaunchState("error");
    }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <section className="rounded-2xl border border-surface-border bg-surface-raised p-6 glow-card space-y-5">
        <h2 className="text-xl font-bold">🚀 Launch Experiment</h2>
        <p className="text-sm text-slate-400">
          Select a case configuration and start a new pipeline run. The experiment
          runs in the background — switch to the Overview tab to track progress.
        </p>

        {isLoading && (
          <p className="text-sm text-slate-500 animate-pulse">Loading configs…</p>
        )}
        {error && (
          <p className="text-sm text-status-halted">Failed to load configs 😢</p>
        )}

        {configs && (
          <div className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-semibold text-slate-300" htmlFor="case-select">
                Case config
              </label>
              <select
                id="case-select"
                value={selected}
                onChange={(e) => {
                  setSelected(e.target.value);
                  setLaunchState("idle");
                  setErrorMsg(null);
                }}
                className="w-full rounded-xl border border-surface-border bg-surface px-4 py-2.5 text-sm font-medium shadow-sm focus:outline-none focus:ring-2 focus:ring-accent/40"
              >
                <option value="">— pick a case —</option>
                {configs.map((c) => (
                  <option key={c.case_id} value={c.case_id}>
                    {c.case_id}
                  </option>
                ))}
              </select>
            </div>

            {activeConfig && (
              <div className="rounded-xl border border-surface-border bg-surface p-4 space-y-2 text-sm">
                {activeConfig.problem_statement && (
                  <p className="text-slate-300 italic">{activeConfig.problem_statement}</p>
                )}
                <div className="flex flex-wrap gap-4 text-slate-400 mt-1">
                  {activeConfig.problem_type && (
                    <span>
                      <span className="font-semibold text-slate-300">Type:</span>{" "}
                      {activeConfig.problem_type}
                    </span>
                  )}
                  {activeConfig.evaluation_metric && (
                    <span>
                      <span className="font-semibold text-slate-300">Metric:</span>{" "}
                      {activeConfig.evaluation_metric}
                    </span>
                  )}
                  {activeConfig.success_threshold != null && (
                    <span>
                      <span className="font-semibold text-slate-300">Target:</span>{" "}
                      {activeConfig.success_threshold}
                    </span>
                  )}
                </div>
              </div>
            )}

            <button
              type="button"
              onClick={handleStart}
              disabled={!selected || launchState === "launching" || launchState === "launched"}
              className="w-full rounded-xl px-6 py-3 font-semibold text-sm transition-all
                bg-gradient-to-r from-fuchsia-500 to-pink-500 text-white shadow-md
                hover:scale-[1.02] active:scale-100
                disabled:opacity-40 disabled:cursor-not-allowed disabled:scale-100"
            >
              {launchState === "launching"
                ? "Launching… ✨"
                : launchState === "launched"
                ? "Launched! 🎀"
                : "Start Run 🚀"}
            </button>

            {launchState === "launched" && launchedCase && (
              <div className="rounded-xl border border-green-500/30 bg-green-500/10 p-4 text-sm text-green-300">
                <p className="font-semibold">Run started for <span className="font-mono">{launchedCase}</span> 🌸</p>
                <p className="text-green-400/70 mt-1">
                  Switch to the <span className="font-semibold">Overview</span> tab and select{" "}
                  <span className="font-mono">{launchedCase}</span> from the case dropdown to track progress.
                </p>
              </div>
            )}

            {launchState === "error" && errorMsg && (
              <div className="rounded-xl border border-status-halted/30 bg-status-halted/10 p-4 text-sm text-status-halted">
                <p className="font-semibold">Failed to launch 😵</p>
                <p className="font-mono text-xs mt-1 break-all">{errorMsg}</p>
              </div>
            )}
          </div>
        )}
      </section>
    </div>
  );
}