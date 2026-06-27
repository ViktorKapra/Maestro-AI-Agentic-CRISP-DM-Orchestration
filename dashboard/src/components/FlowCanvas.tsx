import { useMemo, type MouseEvent } from "react";
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
import { useTheme } from "../shared/theme";
import { AGENTS } from "../pages/Prompts";

// Map a diagram agent node (by its display label) to its prompt metadata.
const AGENT_BY_NAME = new Map(AGENTS.map((a) => [a.name, a]));

// Status-tinted backgrounds are theme tokens, so they follow the active theme.
const STATE_STYLES: Record<string, string> = {
  idle: "border-surface-border bg-surface-raised",
  active: "border-status-running bg-status-running/10 node-active",
  done: "border-status-complete bg-surface-raised opacity-80",
  error: "border-status-halted bg-status-halted/10",
};

// Canvas chrome (edges, labels, minimap, background) per theme.
const CANVAS_THEME = {
  pink: {
    colorMode: "light" as const,
    edge: "#d6409f",
    edgeDispatch: "#e9a8d6",
    label: "#a98fb8",
    background: "#f0abdc",
    miniFlow: "#a855f7",
    miniActive: "#d946ef",
    miniIdle: "#e9a8d6",
    mask: "rgba(253, 244, 255, 0.7)",
  },
  biz: {
    colorMode: "dark" as const,
    edge: "#38bdf8",
    edgeDispatch: "#475569",
    label: "#64748b",
    background: "#1e293b",
    miniFlow: "#818cf8",
    miniActive: "#22d3ee",
    miniIdle: "#334155",
    mask: "rgba(15, 23, 42, 0.7)",
  },
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
      className={`cursor-pointer rounded-lg border-2 px-4 py-2 min-w-[130px] text-center shadow-lg transition-shadow hover:ring-2 hover:ring-accent/50 ${STATE_STYLES[state] ?? STATE_STYLES.idle}`}
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
  onOpenPrompt?: (agentId: string) => void;
}

export function FlowCanvas({ graph, onOpenPrompt }: Props) {
  const { theme, clean } = useTheme();
  const ct = CANVAS_THEME[theme];

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

  const edges: Edge[] = useMemo(() => {
    const backend: Edge[] = (graph?.edges ?? []).map((e) => {
      const isDispatch = e.edgeType === "dispatch";
      const stroke = isDispatch ? ct.edgeDispatch : ct.edge;
      return {
        id: e.id,
        source: e.source,
        target: e.target,
        type: isDispatch ? "smoothstep" : "default",
        // animate every edge so there's always visible movement / flow
        animated: true,
        style: {
          stroke,
          strokeWidth: e.animated ? 2.5 : isDispatch ? 2 : 1.5,
        },
        // Service calls are two-way (request + response) → arrows on both ends.
        // Dispatch from the orchestrator is one-way (it hands out work) →
        // a single arrow pointing to the agent.
        markerStart: isDispatch
          ? undefined
          : { type: MarkerType.ArrowClosed, color: e.animated ? ct.edge : stroke },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: e.animated ? ct.edge : stroke,
        },
      };
    });

    return backend;
  }, [graph, ct]);

  if (!graph || nodes.length === 0) {
    return (
      <div className="flex h-[480px] items-center justify-center rounded-2xl border border-surface-border bg-surface-raised text-slate-500">
        {clean("🦋 No architecture data yet — start a run or wait for trace export.")}
      </div>
    );
  }

  const handleClick = (_e: MouseEvent, node: Node) => {
    const agent = AGENT_BY_NAME.get(String(node.data?.label));
    if (agent) onOpenPrompt?.(agent.id);
  };

  return (
    <div className="relative h-[560px] rounded-2xl border border-surface-border overflow-hidden glow-card">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        colorMode={ct.colorMode}
        proOptions={{ hideAttribution: true }}
        onNodeClick={handleClick}
      >
        <Background color={ct.background} gap={20} />
        <Controls />
        <MiniMap
          nodeColor={(n) => {
            if (n.type === "flowNode") return ct.miniFlow;
            return n.data?.state === "active" ? ct.miniActive : ct.miniIdle;
          }}
          maskColor={ct.mask}
        />
      </ReactFlow>
    </div>
  );
}
