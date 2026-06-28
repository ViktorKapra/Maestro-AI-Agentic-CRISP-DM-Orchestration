import { FlowCanvas } from "../components/FlowCanvas";
import { ProgressRail } from "../components/ProgressRail";
import { useGraph, useStatus } from "../hooks/useCasePolling";
import { useTheme } from "../shared/theme";

interface Props {
  caseId: string;
  onOpenPrompt?: (agentId: string) => void;
}

export function Architecture({ caseId, onOpenPrompt }: Props) {
  const { clean } = useTheme();
  const { data: graph } = useGraph(caseId);
  const { data: status } = useStatus(caseId);

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-surface-border bg-surface-raised p-4 glow-card">
        <p className="mb-3 text-sm leading-relaxed text-slate-400">
          <span className="font-semibold text-slate-200">CRISP-DM</span>{" "}
          (Cross-Industry Standard Process for Data Mining) is the standard
          six-phase framework for data-science projects — from business
          understanding to deployment, with feedback loops between phases. MAADS
          runs the full cycle autonomously; the diagram below shows who does what.
        </p>
        <p className="text-sm text-slate-400 mb-2 font-medium">
          {clean("🦋")} Live agent topology and information flow. Read left to right:{" "}
          <span className="text-slate-300">CrispDM Flow</span> dispatches substeps
          to agents (gray edges); agents call services such as the LLM. Sparkly
          animated edges {clean("✨")} mean an in-flight LLM call.
        </p>
        <div className="mb-3 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-slate-400">
          <span className="flex items-center gap-2">
            <span className="inline-block h-2.5 w-2.5 rounded-full bg-status-running node-active" />
            Active
          </span>
          <span className="flex items-center gap-2">
            <span className="inline-block h-2.5 w-2.5 rounded-full bg-status-complete" />
            Done
          </span>
          <span className="flex items-center gap-2">
            <span className="inline-block h-2.5 w-2.5 rounded-full bg-status-halted" />
            Error
          </span>
          <span className="flex items-center gap-2">
            <span className="inline-block h-0.5 w-6 rounded bg-accent" />
            Agent → service
          </span>
          <span className="flex items-center gap-2">
            <span className="inline-block h-0.5 w-6 rounded bg-slate-600" />
            Dispatch
          </span>
        </div>
        <ProgressRail status={status} />
      </div>
      <FlowCanvas graph={graph} onOpenPrompt={onOpenPrompt} />
    </div>
  );
}
