import { useMemo } from "react";
import {
  Background,
  Controls,
  Handle,
  MarkerType,
  MiniMap,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { GraphPayload } from "../shared/types";

const STATE_STYLES: Record<string, string> = {
  idle: "border-surface-border bg-surface-raised",
  active: "border-status-running bg-fuchsia-100 node-active",
  done: "border-status-complete bg-surface-raised opacity-80",
  error: "border-status-halted bg-rose-100",
};

function AgentNode({ data }: NodeProps) {
  const state = (data.state as string) ?? "idle";
  return (
    <div
      className={`rounded-lg border-2 px-4 py-2 min-w-[120px] text-center shadow-lg ${STATE_STYLES[state] ?? STATE_STYLES.idle}`}
    >
      <Handle type="target" position={Position.Left} className="!bg-accent" />
      <div className="text-sm font-medium">{data.label as string}</div>
      <div className="text-xs text-slate-400 capitalize">{state}</div>
      <Handle type="source" position={Position.Right} className="!bg-accent" />
    </div>
  );
}

function ServiceNode({ data }: NodeProps) {
  const state = (data.state as string) ?? "idle";
  return (
    <div
      className={`rounded-full border-2 px-5 py-3 min-w-[80px] text-center ${STATE_STYLES[state] ?? STATE_STYLES.idle}`}
    >
      <Handle type="target" position={Position.Left} className="!bg-accent" />
      <div className="text-sm font-medium">{data.label as string}</div>
      <Handle type="source" position={Position.Right} className="!bg-accent" />
    </div>
  );
}

const nodeTypes = {
  agentNode: AgentNode,
  serviceNode: ServiceNode,
};

interface Props {
  graph: GraphPayload | undefined;
}

export function FlowCanvas({ graph }: Props) {
  const nodes: Node[] = useMemo(
    () =>
      (graph?.nodes ?? []).map((n) => ({
        id: n.id,
        type: n.type,
        position: n.position,
        data: n.data,
      })),
    [graph],
  );

  const edges: Edge[] = useMemo(
    () =>
      (graph?.edges ?? []).map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        animated: e.animated,
        style: {
          stroke: e.edgeType === "dispatch" ? "#e9a8d6" : "#d6409f",
          strokeWidth: e.animated ? 2.5 : 1.5,
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: e.animated ? "#d6409f" : "#e9a8d6",
        },
        label: e.communication_id ?? undefined,
        labelStyle: { fill: "#a98fb8", fontSize: 10 },
      })),
    [graph],
  );

  if (!graph || nodes.length === 0) {
    return (
      <div className="flex h-[480px] items-center justify-center rounded-2xl border border-surface-border bg-surface-raised text-slate-500">
        🦋 No architecture data yet — start a run or wait for trace export.
      </div>
    );
  }

  return (
    <div className="h-[520px] rounded-2xl border border-surface-border overflow-hidden glow-card">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        colorMode="light"
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#f0abdc" gap={20} />
        <Controls />
        <MiniMap
          nodeColor={(n) =>
            n.data?.state === "active" ? "#d946ef" : "#e9a8d6"
          }
          maskColor="rgba(253, 244, 255, 0.7)"
        />
      </ReactFlow>
    </div>
  );
}
