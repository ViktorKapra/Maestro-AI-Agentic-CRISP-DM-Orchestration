import { FlowCanvas } from "../components/FlowCanvas";
import { ProgressRail } from "../components/ProgressRail";
import { useGraph, useStatus } from "../hooks/useCasePolling";
import { useTheme } from "../shared/theme";

interface Props {
  caseId: string;
}

export function Architecture({ caseId }: Props) {
  const { clean } = useTheme();
  const { data: graph } = useGraph(caseId);
  const { data: status } = useStatus(caseId);

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-surface-border bg-surface-raised p-4 glow-card">
        <p className="text-sm text-slate-400 mb-2 font-medium">
          {clean("🦋")} Live agent topology and information flow. Read left to right:{" "}
          <span className="text-slate-300">CrispDM Flow</span> dispatches substeps
          to agents (gray edges); agents call services such as the LLM. Sparkly
          animated edges {clean("✨")} mean an in-flight LLM call.
        </p>
        <ProgressRail status={status} />
      </div>
      <FlowCanvas graph={graph} />
    </div>
  );
}
