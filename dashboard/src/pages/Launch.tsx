import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { fetchConfigs, postStartRun } from "../shared/api";
import { useModelInfo, useModels } from "../hooks/useCasePolling";
import { useTheme } from "../shared/theme";
import { prettyCase } from "../shared/format";
import type { CaseConfig, ModelInfo } from "../shared/types";

type LaunchState = "idle" | "launching" | "launched" | "error";

function formatBytes(n: unknown): string | null {
  if (typeof n !== "number" || !Number.isFinite(n)) return null;
  const units = ["B", "KB", "MB", "GB", "TB"];
  let v = n;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i += 1;
  }
  return `${v.toFixed(v >= 10 || i === 0 ? 0 : 1)} ${units[i]}`;
}

function formatContextLength(n: unknown): string | null {
  if (typeof n !== "number" || !Number.isFinite(n)) return null;
  if (n >= 1000) return `${Math.round(n / 1000)}k tokens`;
  return `${n} tokens`;
}

function ModelInfoPanel({
  info,
  loading,
  error,
  isDefault,
}: {
  info: ModelInfo | undefined;
  loading: boolean;
  error: Error | null;
  isDefault: boolean;
}) {
  if (loading) {
    return (
      <p className="text-sm text-slate-500 animate-pulse">Loading model details from provider…</p>
    );
  }
  if (error) {
    return (
      <p className="text-sm text-status-halted">Could not load model details: {error.message}</p>
    );
  }
  if (!info) return null;

  const d = info.details;
  const caps = Array.isArray(d.capabilities) ? (d.capabilities as string[]) : [];
  const params =
    d.parameters && typeof d.parameters === "object"
      ? (d.parameters as Record<string, string>)
      : null;

  return (
    <div
      className={`rounded-xl border p-4 space-y-2 text-sm ${
        info.available
          ? "border-surface-border bg-surface"
          : "border-status-halted/30 bg-status-halted/10"
      }`}
    >
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="font-semibold text-slate-200">
          {info.label ?? info.model ?? (isDefault ? "default (.env)" : "—")}
        </span>
        {info.provider && (
          <span className="text-xs uppercase tracking-wide text-slate-500">{info.provider}</span>
        )}
        {!info.available && info.error && (
          <span className="text-xs text-status-halted break-all">{info.error}</span>
        )}
      </div>

      {info.available && (
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-slate-400">
          {typeof d.family === "string" && (
            <span>
              <span className="font-semibold text-slate-300">Family:</span> {d.family}
            </span>
          )}
          {typeof d.parameter_size === "string" && (
            <span>
              <span className="font-semibold text-slate-300">Params:</span> {d.parameter_size}
            </span>
          )}
          {typeof d.quantization === "string" && (
            <span>
              <span className="font-semibold text-slate-300">Quant:</span> {d.quantization}
            </span>
          )}
          {formatContextLength(d.context_length) && (
            <span>
              <span className="font-semibold text-slate-300">Context:</span>{" "}
              {formatContextLength(d.context_length)}
            </span>
          )}
          {formatBytes(d.size_bytes) && (
            <span>
              <span className="font-semibold text-slate-300">Size:</span>{" "}
              {formatBytes(d.size_bytes)}
            </span>
          )}
          {typeof d.owned_by === "string" && (
            <span>
              <span className="font-semibold text-slate-300">Owner:</span> {d.owned_by}
            </span>
          )}
          {typeof d.modified_at === "string" && (
            <span>
              <span className="font-semibold text-slate-300">Updated:</span>{" "}
              {d.modified_at.slice(0, 19)}
            </span>
          )}
        </div>
      )}

      {caps.length > 0 && (
        <p className="text-slate-400">
          <span className="font-semibold text-slate-300">Capabilities:</span> {caps.join(", ")}
        </p>
      )}

      {params && Object.keys(params).length > 0 && (
        <p className="text-slate-400">
          <span className="font-semibold text-slate-300">Defaults:</span>{" "}
          {Object.entries(params)
            .slice(0, 6)
            .map(([k, v]) => `${k} ${v}`)
            .join(" · ")}
        </p>
      )}

      {info.json_capabilities && (
        <p className="text-slate-400">
          <span className="font-semibold text-slate-300">JSON mode:</span>{" "}
          {info.json_capabilities.mode.replace(/_/g, " ")}
        </p>
      )}
    </div>
  );
}

export function Launch({ onLaunched }: { onLaunched?: (caseId: string) => void }) {
  const { clean } = useTheme();
  const { data: configs, isLoading, error } = useQuery({
    queryKey: ["configs"],
    queryFn: fetchConfigs,
  });
  const { data: models } = useModels();

  const [selected, setSelected] = useState<string>("");
  const [selectedModel, setSelectedModel] = useState<string>("");
  const [launchState, setLaunchState] = useState<LaunchState>("idle");
  const [launchedCase, setLaunchedCase] = useState<string | null>(null);
  const [launchedModel, setLaunchedModel] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const {
    data: modelInfo,
    isLoading: modelInfoLoading,
    error: modelInfoError,
  } = useModelInfo(selectedModel || null);

  const activeConfig: CaseConfig | undefined = configs?.find((c) => c.case_id === selected);

  const handleStart = async () => {
    if (!selected) return;
    setLaunchState("launching");
    setErrorMsg(null);
    try {
      await postStartRun(selected, selectedModel || undefined);
      setLaunchedCase(selected);
      setLaunchedModel(selectedModel || null);
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
        <h2 className="text-xl font-bold">{clean("🚀 Launch Experiment")}</h2>
        <p className="text-sm text-slate-400">
          Select a case configuration and start a new pipeline run. The experiment
          runs in the background — switch to the Overview tab to track progress.
        </p>

        {isLoading && (
          <p className="text-sm text-slate-500 animate-pulse">Loading configs…</p>
        )}
        {error && (
          <p className="text-sm text-status-halted">{clean("Failed to load configs 😢")}</p>
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
                    {prettyCase(c.case_id)}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-semibold text-slate-300" htmlFor="model-select">
                Model
              </label>
              <select
                id="model-select"
                value={selectedModel}
                onChange={(e) => {
                  setSelectedModel(e.target.value);
                  setLaunchState("idle");
                  setErrorMsg(null);
                }}
                className="w-full rounded-xl border border-surface-border bg-surface px-4 py-2.5 text-sm font-medium shadow-sm focus:outline-none focus:ring-2 focus:ring-accent/40"
              >
                <option value="">— default (from .env) —</option>
                {models?.ollama_cloud?.length ? (
                  <optgroup label="Ollama Cloud">
                    {models.ollama_cloud.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.label}
                      </option>
                    ))}
                  </optgroup>
                ) : null}
                {models?.openai?.length ? (
                  <optgroup label="OpenAI">
                    {models.openai.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.label}
                      </option>
                    ))}
                  </optgroup>
                ) : null}
              </select>
              <ModelInfoPanel
                info={modelInfo}
                loading={modelInfoLoading}
                error={modelInfoError}
                isDefault={!selectedModel}
              />
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
                ? clean("Launching… ✨")
                : launchState === "launched"
                ? clean("Launched! 🎀")
                : clean("Start Run 🚀")}
            </button>

            {launchState === "launched" && launchedCase && (
              <div className="rounded-xl border border-green-500/30 bg-green-500/10 p-4 text-sm text-green-300">
                <p className="font-semibold">Run started for <span className="font-mono">{launchedCase}</span> {clean("🌸")}</p>
                <p className="text-green-400/70 mt-1">
                  Model: <span className="font-mono">{launchedModel ?? "default (.env)"}</span>
                </p>
                <p className="text-green-400/70 mt-1">
                  Switch to the <span className="font-semibold">Overview</span> tab and select{" "}
                  <span className="font-mono">{launchedCase}</span> from the case dropdown to track progress.
                </p>
              </div>
            )}

            {launchState === "error" && errorMsg && (
              <div className="rounded-xl border border-status-halted/30 bg-status-halted/10 p-4 text-sm text-status-halted">
                <p className="font-semibold">{clean("Failed to launch 😵")}</p>
                <p className="font-mono text-xs mt-1 break-all">{errorMsg}</p>
              </div>
            )}
          </div>
        )}
      </section>
    </div>
  );
}