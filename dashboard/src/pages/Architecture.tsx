import { FlowCanvas } from "../components/FlowCanvas";
import { ProgressRail } from "../components/ProgressRail";
import { useGraph, useStatus } from "../hooks/useCasePolling";

interface Props {
  caseId: string;
}

export function Architecture({ caseId }: Props) {
  const { data: graph } = useGraph(caseId);
  const { data: status } = useStatus(caseId);

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-surface-border bg-surface-raised p-4">
        <p className="text-sm text-slate-400 mb-2">
          Live agent topology and information flow. Animated edges indicate an
          in-flight LLM call.
        </p>
        <ProgressRail status={status} />
      </div>
      <FlowCanvas graph={graph} />
    </div>
  );
}
