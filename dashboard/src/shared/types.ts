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
  workflow_complete?: boolean;
  ml_success?: boolean;
  ml_deficits?: string[];
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
  outcome: {
    parse_ok?: boolean;
    json_valid?: boolean;
    schema_ok?: boolean;
    schema_errors?: string[];
    repair?: {
      kind?: string;
      requesting_agent?: string;
      succeeded?: boolean;
    };
    error?: string;
    raw_response?: string;
  };
  parent_comm_id?: string | null;
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

export type TabId = "overview" | "process" | "state" | "communications" | "architecture" | "timeline" | "knowledge" | "framework" | "prompts" | "state_shape" | "loop_logic" | "failure_modes" | "launch";

export interface CaseConfig {
  case_id: string;
  problem_type: string | null;
  evaluation_metric: string | null;
  problem_statement: string | null;
  success_threshold: number | null;
}

export type SubstepStatus = "done" | "active" | "pending" | "skipped";
export type PhaseStatus = "complete" | "active" | "pending";
export type AgentStatus = "active" | "idle";

export interface ProcessSubstep {
  id: string;
  name: string;
  owner: string;
  owner_label: string;
  phase: number;
  status: SubstepStatus;
  duration_ms: number | null;
}

export interface ProcessPhase {
  id: number;
  name: string;
  status: PhaseStatus;
  ready: boolean;
  substeps: ProcessSubstep[];
}

export interface TeamMember {
  id: string;
  label: string;
  status: AgentStatus;
  current_substep: string | null;
  owned_substeps: string[];
  recent_work: { agent: string; message: string; level: string }[];
  tokens: number;
}

export interface ConclusionHighlight {
  label: string;
  value: string;
}

export interface LiveSummary {
  updated_at: string;
  case_id: string;
  phase: number;
  phase_name: string;
  substep: string;
  substep_name: string;
  activity: string;
  progress: {
    completed_substeps: number;
    total_substeps: number;
    source: string;
  };
  halted: boolean;
  halt_reason: string | null;
  workflow_complete?: boolean;
  ml_success?: boolean;
  ml_deficits?: string[];
  token_spend: Record<string, number>;
  token_spend_by_provider?: Record<string, number>;
  elapsed_ms: number | null;
  trace: {
    run_id: string | null;
    started_at: string | null;
    ended_at: string | null;
    event_count: number;
  };
  in_flight: {
    communication_id: string;
    agent: string;
    substep: string;
    model?: string | null;
  } | null;
  last_comm: {
    id: string;
    agent: string;
    substep: string;
    parse_ok?: boolean;
    tokens?: number | null;
  } | null;
}

export interface ConclusionItem {
  id: string;
  name: string;
  summary: string;
  highlights?: ConclusionHighlight[];
  artifact_paths?: Record<string, string>;
  evidence_refs?: { type: string; ref: string }[];
}

export interface ConclusionPhase {
  id: number;
  name: string;
  items: ConclusionItem[];
}

export interface ProcessConclusions {
  business_objectives?: string | null;
  data_mining_goals?: string | null;
  data_quality_blockers?: string[];
  data_quality_tolerable?: string[];
  dataset_paths?: Record<string, string>;
  dataset_description?: string | null;
  models?: { technique: string; cv_score: number | null; assessment: string | null }[];
  chosen_model?: { technique: string; cv_score: number | null; assessment: string | null } | null;
  assessment?: { cv_score?: number; meets?: boolean; threshold?: number } | null;
  decision?: string | null;
  submission_path?: string | null;
  final_report_path?: string | null;
  workflow_complete?: boolean;
  ml_success?: boolean;
  ml_deficits?: string[];
  phases?: ConclusionPhase[];
}

export interface ProcessLoop {
  label?: string;
  from_phase?: number;
  to_phase?: number;
  reason?: string;
  ts?: string;
}

export interface ProcessDeliverable {
  label: string;
  path: string;
  exists: boolean;
  url?: string | null;
}

export interface ProcessView {
  updated_at?: string;
  current_phase: number;
  current_substep: string;
  current_substep_name: string;
  activity: string;
  phases: ProcessPhase[];
  substeps: ProcessSubstep[];
  team: TeamMember[];
  conclusions: ProcessConclusions;
  config: {
    problem_statement?: string;
    problem_type?: string;
    target_column?: string;
    evaluation_metric?: string;
  };
  loops: ProcessLoop[];
  deliverables: ProcessDeliverable[];
  validator_findings: string[];
  outputs_status: Record<string, boolean>;
}

export interface CrispDMStatePayload {
  updated_at: string | null;
  source: "live" | "final" | string;
  state: Record<string, unknown>;
}

export interface RagCorpusFile {
  name: string;
  path: string;
  size_bytes: number;
  role: "shared" | "case" | "experience";
}

export interface RagPassage {
  source: string;
  text: string;
}

export interface RagView {
  updated_at: string;
  case_id: string;
  embedding_backend: string;
  embedding_model: string | null;
  chunk_count: number;
  crewai_knowledge_enabled: boolean;
  explicit_rag_enabled: boolean;
  corpus_files: RagCorpusFile[];
  retrieval_query_preview: string;
  retrieved_passages: RagPassage[];
  domain_substeps_using_rag: string[];
  consumer_agent: string;
}
