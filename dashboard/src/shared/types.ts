export type RunStatus = "running" | "complete" | "halted";

export interface CaseSummary {
  case_id: string;
  artifact_dir: string;
  status: RunStatus;
  updated_at: string | null;
  phase?: number;
  phase_name?: string;
  completed_substeps?: number;
  total_substeps?: number;
}

export interface StatusPayload {
  updated_at: string;
  case_id: string;
  phase: number;
  phase_name: string;
  substep: string;
  substep_name: string;
  activity: string;
  completed_substeps: number;
  total_substeps: number;
  token_spend: Record<string, number>;
  halted: boolean;
  halt_reason: string | null;
  artifact_dir: string;
  trace_dir: string;
}

export interface TraceEvent {
  id: string;
  parent_id: string | null;
  ts: string;
  ts_mono_ms: number;
  duration_ms: number | null;
  type: string;
  source: string;
  name: string;
  attributes: Record<string, unknown>;
}

export interface TraceSummary {
  run_id: string;
  case_id: string | null;
  started_at: string;
  ended_at: string | null;
  total_events: number;
  filtered_event_count: number;
  events: TraceEvent[];
}

export interface CommunicationRecord {
  id: string;
  call_id: string | null;
  substep: string;
  agent_name: string;
  role: string | null;
  model: string | null;
  started_at: string;
  duration_ms: number | null;
  tokens: { prompt?: number | null; completion?: number | null; total?: number | null };
  maads: Record<string, unknown>;
  provider: Record<string, unknown>;
  outcome: { parse_ok?: boolean; error?: string; raw_response?: string };
  closed: boolean;
}

export interface CommunicationsSummary {
  turn_count: number;
  total_tokens: number;
  parse_failures: number;
  avg_duration_ms: number;
  by_agent: Record<
    string,
    {
      turns: number;
      total_tokens: number;
      parse_failures: number;
      avg_duration_ms: number;
    }
  >;
  by_model: Record<string, number>;
  llm_io_mode: string;
}

export interface FlowNode {
  id: string;
  type: string;
  position: { x: number; y: number };
  data: { label: string; state: string };
}

export interface FlowEdge {
  id: string;
  source: string;
  target: string;
  animated: boolean;
  edgeType?: string;
  communication_id?: string | null;
}

export interface GraphPayload {
  nodes: FlowNode[];
  edges: FlowEdge[];
}

export type TabId = "overview" | "communications" | "architecture" | "timeline";
