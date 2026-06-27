import { useTheme } from "../shared/theme";

const GIT_HISTORY = [
  {
    hash: "54177d7",
    msg: "maybe fixed loop",
    what: "PM loop-firing was silently skipped when action was 'loop_back' but loop_to_phase was None. The orchestrator advanced linearly instead of jumping back.",
    fix: "Added _coerce_phase() to agents.py to normalise LLM-supplied phase values ('null', 'None', empty string → None) and guard the phase transition. Loop B now fires correctly when the PM sets loop_to_phase=3.",
    severity: "high",
  },
  {
    hash: "e8cbe66",
    msg: "Declare maads runtime dependencies explicitly in requirements.txt",
    what: "CrewAI transitive installs were providing langchain, pydantic-v1 shims, and litellm, but a clean install failed because maads never declared them directly. CI passed on a cached env; fresh installs broke.",
    fix: "Audited all imports and added explicit entries in requirements.txt / pyproject.toml for crewai, pydantic, litellm, rich, and others.",
    severity: "medium",
  },
  {
    hash: "d817a89",
    msg: "Refactor CRISP-DM orchestration onto CrewAI Flow with phase crews",
    what: "The original monolithic orchestrator (orchestrator.py) held all 24 substep handlers in one class, making it impossible to test individual phases or swap agent configs without touching unrelated code.",
    fix: "Replaced with CrispDMFlow (phase graph, PM checkpoint routers, loop caps) and phase-scoped @CrewBase crews backed by YAML agent/task config. Deterministic sandbox execution and JSON apply logic moved to capabilities/ so crews stay LLM-focused.",
    severity: "architecture",
  },
  {
    hash: "0c75005",
    msg: "Add Storyteller crew and enhance output handling for reporting",
    what: "Phase 6.2 and 6.3 were stubbed — the storyteller was a no-op that returned empty state deltas. Final report generation was completely missing.",
    fix: "Added StorytellerCrew with its own YAML config, backstory, and capabilities module. render_final_report_step() reads the evaluation_bundle and produces a markdown report with figures. apply_storyteller_response() validates the delta before writing.",
    severity: "feature",
  },
  {
    hash: "5af3892",
    msg: "Align project structure with Python and CrewAI best practices",
    what: "Tests lived inside the src/ tree, agent config was duplicated across per-crew YAML files and the top-level config, and the maads entry point was missing from pyproject.toml. Import paths were fragile.",
    fix: "Moved tests to a top-level tests/ tree, consolidated agent config into maads/config/agents.yaml, exposed build_agent publicly, added the maads console script entry point.",
    severity: "medium",
  },
];

const CODE_FAILURES = [
  {
    class: "json_parse",
    emoji: "🚫",
    color: "border-red-500/40",
    badge: "bg-red-500/20 text-red-300",
    description: "Agent returned non-JSON or malformed JSON output.",
    symptoms: ["Output wrapped in markdown fences (```json...```)", "Trailing commas in objects/arrays", "Line comments (// ...) inside JSON", "Reasoning-model <think>...</think> blocks prepended to output"],
    auto_fix: "crew.py _extract_json() strips fences, _repair_json() removes trailing commas and line comments, re.sub strips <think> blocks. If still failing → escalate to debug_json_parse() → Developer LLM one-shot repair.",
    file: "src/maads/crew.py",
  },
  {
    class: "json_schema",
    emoji: "⚠️",
    color: "border-orange-500/40",
    badge: "bg-orange-500/20 text-orange-300",
    description: "JSON parsed successfully but failed output contract validation (missing required fields, wrong types).",
    symptoms: ["Required field absent", "Field is wrong type (list instead of str)", "Numeric field returned as string"],
    auto_fix: "validate_agent_output() returns error list. If artifact_dir is provided → debug_json_parse(failure_kind='json_schema') asks Developer to patch the payload. If still failing → CrewKickoffError raised.",
    file: "src/maads/crew.py + src/maads/debug.py",
  },
  {
    class: "python_exec",
    emoji: "💥",
    color: "border-rose-500/40",
    badge: "bg-rose-500/20 text-rose-300",
    description: "PythonExec sandbox returned non-zero exit or timed out.",
    symptoms: ["SyntaxError / IndentationError", "KeyError / column not found", "Shape mismatch / n_features mismatch", "TypeError / could not convert dtype", "MemoryError", "ImportError / ModuleNotFoundError", "Timeout (default 60 s)"],
    auto_fix: "classify_exec_error() labels the failure class. debug_python_exec() asks Developer to generate a fixed script, re-executes it, and validates the output contract. Up to MAX_DEBUG_RETRIES = 3 attempts. On STUCK: StateDelta(failed=True) written; orchestrator may degrade to baseline.",
    file: "src/maads/debug.py",
  },
  {
    class: "leakage_signal",
    emoji: "🚿",
    color: "border-purple-500/40",
    badge: "bg-purple-500/20 text-purple-300",
    description: "Data Engineer or Data Scientist detected a leakage-related error in the sandbox.",
    symptoms: ["'leakage' or 'contamination' in stderr", "Test set statistics used during fit", "Post-prediction-time feature"],
    auto_fix: "classify_exec_error() labels as 'leakage_signal'. Developer is escalated. If leakage persists, the Data Engineer's OPERATING PRINCIPLES mandate BLOCKED status and a handoff. Loop B may fire on the PM's next turn.",
    file: "src/maads/debug.py + src/maads/prompts/identities/backstories/data_engineer.md",
  },
  {
    class: "token_budget",
    emoji: "💸",
    color: "border-yellow-500/40",
    badge: "bg-yellow-500/20 text-yellow-300",
    description: "Total token spend across the run exceeded MAX_TOKENS_PER_RUN env var.",
    symptoms: ["RuntimeError: 'Run-wide token cap of N reached'"],
    auto_fix: "_check_token_budget() is called after every LLM kickoff. Raises RuntimeError immediately. The orchestrator catches it, writes halted=True with halt_reason, and stops the pipeline cleanly.",
    file: "src/maads/crew.py",
  },
  {
    class: "loop_cap",
    emoji: "🔁",
    color: "border-amber-500/40",
    badge: "bg-amber-500/20 text-amber-300",
    description: "PM attempted to fire a loop that exceeded the guard-layer hard cap.",
    symptoms: ["Loop B fired more than 3 times", "Loop C attempted after Loop A×2"],
    auto_fix: "Deterministic guard layer in the orchestrator refuses the move, records it in the log, and forces the PM to re-decide from the capped state. The PM backstory explains this contract explicitly so the LLM does not fight the guard.",
    file: "src/maads/agents.py + PM backstory",
  },
  {
    class: "empty_llm_output",
    emoji: "🫙",
    color: "border-slate-500/40",
    badge: "bg-slate-500/20 text-slate-300",
    description: "CrewAI kickoff succeeded but the agent returned an empty string.",
    symptoms: ["raw_output.strip() == ''"],
    auto_fix: "_set_meta(payload=None, repair_succeeded=False) is called. CrewKickoffError is raised with 'returned non-JSON output'. Caught upstream; StateDelta(failed=True) or Plan(action='halt') is issued.",
    file: "src/maads/crew.py",
  },
];

export function FailureModes() {
  const { clean } = useTheme();
  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-surface-border bg-surface-raised p-5 glow-card">
        <h2 className="text-lg font-bold text-slate-200 mb-1">{clean("🩹 Failure Modes — Honest Log")}</h2>
        <p className="text-sm text-slate-400">
          Every class of failure this system has hit, plus how it was fixed — sourced from the
          git history and the debug/repair code. No sugarcoating.
        </p>
      </div>

      {/* Git history failures */}
      <div className="rounded-2xl border border-surface-border bg-surface-raised p-5 glow-card">
        <h3 className="text-sm font-bold text-slate-300 mb-4">
          {clean("📜 From git history")}
        </h3>
        <div className="space-y-4">
          {GIT_HISTORY.map((entry) => (
            <div
              key={entry.hash}
              className="rounded-xl border border-surface-border bg-surface p-4"
            >
              <div className="flex flex-wrap items-baseline gap-2 mb-2">
                <code className="text-slate-500 text-[11px] font-mono">{entry.hash}</code>
                <span className="text-slate-300 font-semibold text-xs">"{entry.msg}"</span>
                <SeverityBadge s={entry.severity} />
              </div>
              <div className="space-y-2 text-xs">
                <div>
                  <span className="text-red-400 font-bold">What broke: </span>
                  <span className="text-slate-400">{entry.what}</span>
                </div>
                <div>
                  <span className="text-green-400 font-bold">How it was fixed: </span>
                  <span className="text-slate-400">{entry.fix}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Runtime failure classes */}
      <div className="rounded-2xl border border-surface-border bg-surface-raised p-5 glow-card">
        <h3 className="text-sm font-bold text-slate-300 mb-4">
          {clean("⚙️ Runtime failure classes (from code)")}
        </h3>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {CODE_FAILURES.map((f) => (
            <div key={f.class} className={`rounded-2xl border ${f.color} p-4 glow-card`}>
              <div className="flex items-center gap-2 mb-3">
                <span className="text-xl">{clean(f.emoji)}</span>
                <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${f.badge}`}>
                  {f.class}
                </span>
              </div>
              <div className="space-y-2 text-xs">
                <div className="text-slate-300">{f.description}</div>
                <div>
                  <div className="text-slate-500 uppercase tracking-wide text-[10px] font-bold mb-1">
                    Symptoms
                  </div>
                  <ul className="list-disc list-inside text-slate-400 space-y-0.5">
                    {f.symptoms.map((s) => (
                      <li key={s}>{s}</li>
                    ))}
                  </ul>
                </div>
                <div>
                  <div className="text-slate-500 uppercase tracking-wide text-[10px] font-bold mb-1">
                    Auto-fix path
                  </div>
                  <div className="text-green-300/80">{f.auto_fix}</div>
                </div>
                <div>
                  <span className="text-slate-600 font-mono text-[10px]">{f.file}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* What is not auto-recovered */}
      <div className="rounded-2xl border border-amber-500/30 bg-amber-900/10 p-5 glow-card">
        <h3 className="text-sm font-bold text-amber-300 mb-3">
          {clean("⚠️ What is NOT auto-recovered")}
        </h3>
        <ul className="space-y-2 text-sm text-slate-400">
          {[
            "Python sandbox hits MAX_DEBUG_RETRIES (3) and still fails → StateDelta(failed=True) written; PM may Loop B or halt.",
            "Developer LLM itself fails during a debug call → DebugOutcome(status='STUCK'); escalates to a halt.",
            "Token budget exceeded mid-run → immediate halt; partial artifacts preserved.",
            "Data Quality blockers that require new raw data — no amount of looping can fix a fundamentally missing column.",
            "LLM provider outage / API timeout during kickoff → CrewKickoffError propagates to Plan(action='halt').",
            "Loop caps exhausted (Loop B×3, Loop A×2+C) → orchestrator forces halt with a clear reason in state.halt_reason.",
          ].map((item) => (
            <li key={item} className="flex gap-2">
              <span className="text-amber-400 font-bold shrink-0">▸</span>
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function SeverityBadge({ s }: { s: string }) {
  const map: Record<string, string> = {
    high: "bg-red-500/20 text-red-300",
    medium: "bg-orange-500/20 text-orange-300",
    architecture: "bg-purple-500/20 text-purple-300",
    feature: "bg-teal-500/20 text-teal-300",
  };
  return (
    <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${map[s] ?? "bg-slate-500/20 text-slate-400"}`}>
      {s}
    </span>
  );
}
