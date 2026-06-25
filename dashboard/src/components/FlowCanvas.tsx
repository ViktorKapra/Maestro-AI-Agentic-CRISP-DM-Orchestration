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
  idle: "border-slate-600 bg-surface-raised",
  active: "border-status-running bg-green-950/40 node-active",
  done: "border-slate-500 bg-surface-raised opacity-80",
  error: "border-status-halted bg-red-950/40",
};

function FlowNode({ data }: NodeProps) {
  const state = (data.state as string) ?? "idle";
  return (
    <div
      className={`rounded-xl border-2 px-5 py-3 min-w-[140px] text-center shadow-lg border-accent/70 bg-accent/10 ${STATE_STYLES[state] ?? STATE_STYLES.idle}`}
    >
      <Handle type="source" position={Position.Right} className="!bg-accent" />
      <div className="text-sm font-semibold tracking-tight">{data.label as string}</div>
      <div className="text-xs text-slate-400 capitalize">{state}</div>
    </div>
  );
}

function AgentNode({ data }: NodeProps) {
  const state = (data.state as string) ?? "idle";
  return (
    <div
      className={`rounded-lg border-2 px-4 py-2 min-w-[130px] text-center shadow-lg ${STATE_STYLES[state] ?? STATE_STYLES.idle}`}
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
      className={`rounded-full border-2 px-5 py-3 min-w-[88px] text-center ${STATE_STYLES[state] ?? STATE_STYLES.idle}`}
    >
      <Handle type="target" position={Position.Left} className="!bg-accent" />
      <div className="text-sm font-medium">{data.label as string}</div>
    </div>
  );
}

const nodeTypes = {
  flowNode: FlowNode,
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
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
      })),
    [graph],
  );

  const edges: Edge[] = useMemo(
    () =>
      (graph?.edges ?? []).map((e) => {
        const isDispatch = e.edgeType === "dispatch";
        const stroke = isDispatch ? "#64748b" : "#60a5fa";
        return {
          id: e.id,
          source: e.source,
          target: e.target,
          type: isDispatch ? "smoothstep" : "default",
          animated: e.animated,
          style: {
            stroke,
            strokeWidth: e.animated ? 2.5 : isDispatch ? 2 : 1.5,
          },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            color: e.animated ? "#60a5fa" : stroke,
          },
          label: e.communication_id ?? undefined,
          labelStyle: { fill: "#94a3b8", fontSize: 10 },
        };
      }),
    [graph],
  );

  if (!graph || nodes.length === 0) {
    return (
      <div className="flex h-[480px] items-center justify-center rounded-lg border border-surface-border bg-surface-raised text-slate-500">
        No architecture data yet — start a run or wait for trace export.
      </div>
    );
  }

  return (
    <div className="h-[560px] rounded-lg border border-surface-border overflow-hidden">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        colorMode="dark"
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#2d3a4f" gap={20} />
        <Controls />
        <MiniMap
          nodeColor={(n) => {
            if (n.type === "flowNode") return "#6366f1";
            return n.data?.state === "active" ? "#22c55e" : "#334155";
          }}
          maskColor="rgba(15, 20, 25, 0.8)"
        />
      </ReactFlow>
    </div>
  );
}
