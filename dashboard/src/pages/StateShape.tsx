import { useTheme } from "../shared/theme";

const PHASES = [
  {
    key: "bu",
    label: "BusinessUnderstanding",
    phase: 1,
    color: "border-purple-500/40 bg-purple-900/10",
    badge: "bg-purple-500/20 text-purple-300",
    fields: [
      { name: "background", type: "str | None", substep: "1.1" },
      { name: "business_objectives", type: "str | None", substep: "1.1" },
      { name: "business_success_criteria", type: "str | None", substep: "1.1" },
      { name: "inventory_of_resources", type: "dict | None", substep: "1.2" },
      { name: "requirements_assumptions_constraints", type: "dict | None", substep: "1.2" },
      { name: "risks_and_contingencies", type: "list[str]", substep: "1.2" },
      { name: "terminology", type: "dict[str, str]", substep: "1.2" },
      { name: "costs_and_benefits", type: "dict | None", substep: "1.2" },
      { name: "data_mining_goals", type: "str | None", substep: "1.3" },
      { name: "data_mining_success_criteria", type: "str | None", substep: "1.3" },
      { name: "project_plan", type: "list[str]", substep: "1.4" },
      { name: "initial_assessment_of_tools_and_techniques", type: "dict | None", substep: "1.4" },
    ],
  },
  {
    key: "du",
    label: "DataUnderstanding",
    phase: 2,
    color: "border-fuchsia-500/40 bg-fuchsia-900/10",
    badge: "bg-fuchsia-500/20 text-fuchsia-300",
    fields: [
      { name: "initial_data_collection_report", type: "dict | None", substep: "2.1" },
      { name: "data_description_report", type: "dict | None", substep: "2.2" },
      { name: "data_exploration_report", type: "dict | None", substep: "2.3" },
      { name: "data_quality_report", type: "dict | None", substep: "2.4" },
    ],
  },
  {
    key: "dp",
    label: "DataPreparation",
    phase: 3,
    color: "border-pink-500/40 bg-pink-900/10",
    badge: "bg-pink-500/20 text-pink-300",
    fields: [
      { name: "rationale_for_inclusion_exclusion", type: "dict | None", substep: "3.1" },
      { name: "data_cleaning_report", type: "dict | None", substep: "3.2" },
      { name: "derived_attributes", type: "dict | None", substep: "3.3" },
      { name: "generated_records", type: "dict | None", substep: "3.3" },
      { name: "merged_data", type: "dict | None", substep: "3.4" },
      { name: "reformatted_data", type: "dict | None", substep: "3.5" },
      { name: "dataset", type: "dict[str, str]", substep: "3.5" },
      { name: "dataset_description", type: "str | None", substep: "3.5" },
    ],
  },
  {
    key: "md",
    label: "Modeling",
    phase: 4,
    color: "border-rose-500/40 bg-rose-900/10",
    badge: "bg-rose-500/20 text-rose-300",
    fields: [
      { name: "modeling_technique", type: "str | None", substep: "4.1" },
      { name: "modeling_assumptions", type: "list[str]", substep: "4.1" },
      { name: "test_design", type: "dict | None", substep: "4.2" },
      { name: "models", type: "list[ModelRun]", substep: "4.3/4.4" },
      { name: "chosen_model", type: "ModelRun | None", substep: "4.4" },
    ],
  },
  {
    key: "ev",
    label: "Evaluation",
    phase: 5,
    color: "border-orange-500/40 bg-orange-900/10",
    badge: "bg-orange-500/20 text-orange-300",
    fields: [
      { name: "assessment_of_dm_results", type: "dict | None", substep: "5.1" },
      { name: "approved_models", type: "list[ModelRun]", substep: "5.1" },
      { name: "review_of_process", type: "str | None", substep: "5.2" },
      { name: "list_of_possible_actions", type: "list[str]", substep: "5.3" },
      { name: "decision", type: "str | None", substep: "5.3" },
    ],
  },
  {
    key: "dep",
    label: "Deployment",
    phase: 6,
    color: "border-teal-500/40 bg-teal-900/10",
    badge: "bg-teal-500/20 text-teal-300",
    fields: [
      { name: "deployment_plan", type: "str | None", substep: "6.1" },
      { name: "story_spec_path", type: "str | None", substep: "6.2" },
      { name: "figures_dir", type: "str | None", substep: "6.2" },
      { name: "final_report_path", type: "str | None", substep: "6.3" },
      { name: "final_presentation_path", type: "str | None", substep: "6.3" },
      { name: "experience_documentation", type: "str | None", substep: "6.4" },
      { name: "submission_path", type: "str | None", substep: "6.1" },
    ],
  },
];

const MODEL_RUN = [
  { name: "technique", type: "str" },
  { name: "parameter_settings", type: "dict" },
  { name: "description", type: "str" },
  { name: "cv_score", type: "float | None" },
  { name: "cv_std", type: "float | None" },
  { name: "holdout_score", type: "float | None" },
  { name: "assessment", type: "str | None" },
  { name: "revised_parameter_settings", type: "dict | None" },
  { name: "evaluation_bundle", type: "EvaluationBundle | None" },
];

export function StateShape() {
  const { clean } = useTheme();
  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-surface-border bg-surface-raised p-5 glow-card">
        <h2 className="text-lg font-bold text-slate-200 mb-1">{clean("🏗️ State Shape")}</h2>
        <p className="text-sm text-slate-400">
          <code className="text-pink-300 text-xs">CrispDMState</code> is a single Pydantic{" "}
          <code className="text-pink-300 text-xs">BaseModel</code> shared across all agents.
          It lives in{" "}
          <code className="text-pink-300 text-xs">src/maads/state.py</code>.
          Two design rules: <em>(1) append-only logs</em> — log, loop_history, and md.models only grow;
          <em> (2) no agent reads another agent's prompts</em> — only state.
        </p>
      </div>

      {/* Top-level fields */}
      <div className="rounded-2xl border border-surface-border bg-surface-raised p-5 glow-card">
        <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3">
          CrispDMState — top-level fields
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs font-mono">
          {[
            ["case_id", "str", ""],
            ["config", "CaseConfig", "problem_statement, target_column, metric, …"],
            ["phase", "Phase (IntEnum 1-6)", "current CRISP-DM phase"],
            ["substep", "str", "e.g. '3.2'"],
            ["loop_history", "list[LoopEvent]", "append-only; label, from_phase, to_phase, reason, ts"],
            ["validator_findings", "list[str]", "Loop B trigger signals"],
            ["degraded_flags", "list[str]", "baseline-fallback signals for Loop B"],
            ["halted", "bool", ""],
            ["halt_reason", "str | None", ""],
            ["bu", "BusinessUnderstanding", "Phase 1 outputs"],
            ["du", "DataUnderstanding", "Phase 2 outputs"],
            ["dp", "DataPreparation", "Phase 3 outputs"],
            ["md", "Modeling", "Phase 4 outputs"],
            ["ev", "Evaluation", "Phase 5 outputs"],
            ["dep", "Deployment", "Phase 6 outputs"],
            ["log", "list[LogEntry]", "append-only; agent, level, message, data, ts"],
            ["token_spend", "dict[str, int]", "per-agent token totals"],
            ["token_spend_by_provider", "dict[str, int]", "per-provider token totals"],
          ].map(([field, type, note]) => (
            <div
              key={field}
              className="flex gap-2 py-1.5 border-b border-surface-border/40 items-start"
            >
              <code className="text-fuchsia-300 shrink-0 w-44">{field}</code>
              <code className="text-pink-200/70 shrink-0 w-36">{type}</code>
              {note && <span className="text-slate-500 text-[11px]">{note}</span>}
            </div>
          ))}
        </div>
      </div>

      {/* Phase sub-models */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {PHASES.map((p) => (
          <div key={p.key} className={`rounded-2xl border ${p.color} p-4 glow-card`}>
            <div className="flex items-center gap-2 mb-3">
              <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${p.badge}`}>
                Phase {p.phase}
              </span>
              <code className="text-slate-300 text-xs font-bold">{p.key}</code>
              <span className="text-slate-500 text-[11px]">{p.label}</span>
            </div>
            <div className="space-y-1">
              {p.fields.map((f) => (
                <div key={f.name} className="flex gap-2 text-[11px]">
                  <code className="text-pink-300 w-52 shrink-0 truncate">{f.name}</code>
                  <code className="text-slate-500 w-28 shrink-0 truncate">{f.type}</code>
                  <span className="text-slate-600">{f.substep}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* ModelRun nested model */}
      <div className="rounded-2xl border border-surface-border bg-surface-raised p-5 glow-card">
        <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3">
          ModelRun — nested inside md.models[] and md.chosen_model
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-1 text-[11px] font-mono">
          {MODEL_RUN.map((f) => (
            <div key={f.name} className="flex gap-2 py-1 border-b border-surface-border/30">
              <code className="text-pink-300 w-36 shrink-0">{f.name}</code>
              <code className="text-slate-500">{f.type}</code>
            </div>
          ))}
        </div>
        <p className="text-xs text-slate-500 mt-3">
          <code className="text-pink-300">EvaluationBundle</code> nested inside ModelRun:
          problem_type, metrics dict, confusion_matrix, class_labels, cv dict, figures list, warnings list.
        </p>
      </div>

      {/* view_for */}
      <div className="rounded-2xl border border-surface-border bg-surface-raised p-5 glow-card">
        <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3">
          state.view_for(agent_name) — what each agent sees
        </h3>
        <div className="space-y-2 text-xs">
          {[
            ["pm", "loop_history, recent_log[-8:], latest_quality_blockers, latest_model_assessment, outputs_status, validator_findings, degraded_flags, suggested_action, business_goal_met"],
            ["domain", "bu (full), du_so_far (exclude_none), feature_hints, config"],
            ["data_engineer", "raw_data_paths, data_mining_goals, du_so_far, dp_so_far"],
            ["data_scientist", "data_mining_goals, dataset, data_description_report, recent_models[-3:], test_design"],
            ["developer", "chosen_model, dataset, sample_submission_csv, data_description_report"],
            ["storyteller", "chosen_model, evaluation_bundle, business_objectives, data_mining_goals, data_description_report, data_exploration_report, test_design, assessment_of_dm_results, loop_history, degraded_flags, class_labels, submission_path"],
          ].map(([agent, fields]) => (
            <div key={agent} className="flex gap-3 py-1.5 border-b border-surface-border/40">
              <code className="text-fuchsia-300 shrink-0 w-28">{agent}</code>
              <span className="text-slate-400">{fields}</span>
            </div>
          ))}
        </div>
        <p className="text-xs text-slate-500 mt-3">
          All views also include the base fields: case_id, phase, substep, substep_name, config (problem_statement, problem_type, target_column, evaluation_metric).
        </p>
      </div>
    </div>
  );
}
