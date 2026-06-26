export function LoopLogic() {
  const loops = [
    {
      label: "A",
      emoji: "🔁",
      from: "Phase 2 → Phase 1",
      fromPhase: "2.4 Verify Data Quality",
      toSubstep: "1.3 Determine Data Mining Goals",
      color: "border-amber-500/50 bg-amber-900/10",
      badge: "bg-amber-500/20 text-amber-300",
      trigger:
        "data_quality_report.blockers is non-empty  OR  Domain Expert hypotheses are contradicted by the actual dataset schema.",
      action:
        "Return to 1.3 to refine objectives and re-enter Phase 2 with updated data-mining goals. Only 1.3 re-runs — the rest of Phase 1 is not repeated.",
      cap: "If Loop A has already fired twice and results still fail: force halt (Loop C is not permitted after Loop A×2).",
      stateFields: ["du.data_quality_report.blockers", "validator_findings"],
      example:
        '"PassengerId has zero predictive variance" is a blocking quality issue — goals must narrow scope or the column must be excluded before proceeding.',
    },
    {
      label: "B",
      emoji: "🔂",
      from: "Phase 4 → Phase 3",
      fromPhase: "4.4 Assess Model",
      toSubstep: "3.2 Clean Data (or specific failing substep)",
      color: "border-rose-500/50 bg-rose-900/10",
      badge: "bg-rose-500/20 text-rose-300",
      trigger:
        "Any of: md.models[-1].cv_score below the success threshold;  validator_findings non-empty (e.g. a derived feature is missing or the target contains NaNs);  or a model run degraded to the baseline fallback (degraded_flags non-empty).",
      action:
        "Return to the specific failing substep of Phase 3 — not the whole phase. Capped at 3 iterations total.",
      cap: "Hard cap at 3 iterations enforced by the guard layer. After cap the orchestrator forces advance regardless of PM decision.",
      stateFields: [
        "md.models[-1].cv_score",
        "md.models[-1].assessment",
        "validator_findings",
        "degraded_flags",
      ],
      example:
        'cv_score = 0.61 vs threshold 0.80, and validator_findings = ["\'cabin_deck\' feature missing after 3.3"] → loop back to 3.3 Construct Data.',
    },
    {
      label: "C",
      emoji: "↩️",
      from: "Phase 5 → Phase 1",
      fromPhase: "5.1 Evaluate Results",
      toSubstep: "1.3 Determine Data Mining Goals",
      color: "border-purple-500/50 bg-purple-900/10",
      badge: "bg-purple-500/20 text-purple-300",
      trigger:
        "ev.assessment_of_dm_results.meets is False — the business success criterion was not met after full modeling.",
      action:
        "Fundamental rethink of data-mining goals. Re-runs only 1.3, then the full pipeline resumes from Phase 2.",
      cap: "Only fires if Loop A has fired fewer than twice. Otherwise: halt with an explanation.",
      stateFields: [
        "ev.assessment_of_dm_results.meets",
        "ev.assessment_of_dm_results.cv_score",
        "loop_history (count of label='A')",
      ],
      example:
        'Target AUC 0.85 not met (achieved 0.73) after Loop B×2 → PM fires Loop C to restate goal as AUC ≥ 0.75, justified by data constraints.',
    },
    {
      label: "D",
      emoji: "🔄",
      from: "Phase 6 → Phase 1 (next run)",
      fromPhase: "6.4 Review Project",
      toSubstep: "1.1 Business Objectives (next dataset / case)",
      color: "border-teal-500/50 bg-teal-900/10",
      badge: "bg-teal-500/20 text-teal-300",
      trigger:
        "Optional outer cycle after 6.4. The experience documentation from the current run feeds the next case.",
      action:
        "Cross-dataset learning. PM explicitly opts in after reviewing the experience documentation. Not automatic.",
      cap: "No hard cap — PM discretion only. Must not fire before 6.4 has fully executed.",
      stateFields: ["dep.experience_documentation", "loop_history"],
      example:
        "Titanic run learns that fare×class interaction is crucial → experience_doc records this → next disaster-tweets run starts with that prior.",
    },
  ];

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-surface-border bg-surface-raised p-5 glow-card">
        <h2 className="text-lg font-bold text-slate-200 mb-1">🔄 Loop Logic</h2>
        <p className="text-sm text-slate-400">
          CRISP-DM is iterative, not waterfall. The PM is the sole decision-maker for loop
          firing — agents only <em>recommend</em> loops via state signals. A deterministic guard
          layer enforces hard caps regardless of PM reasoning. A run that never fires a back-edge
          is a script, not a CRISP-DM process.
        </p>
      </div>

      {/* Phase sequence */}
      <div className="rounded-2xl border border-surface-border bg-surface-raised p-5 glow-card overflow-x-auto">
        <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-4">
          Phase sequence with back-edges
        </h3>
        <div className="flex items-center gap-1 min-w-max">
          {[
            { n: 1, name: "Business\nUnderstanding", color: "border-purple-500/50 bg-purple-900/30" },
            { n: 2, name: "Data\nUnderstanding", color: "border-fuchsia-500/50 bg-fuchsia-900/30" },
            { n: 3, name: "Data\nPreparation", color: "border-pink-500/50 bg-pink-900/30" },
            { n: 4, name: "Modeling", color: "border-rose-500/50 bg-rose-900/30" },
            { n: 5, name: "Evaluation", color: "border-orange-500/50 bg-orange-900/30" },
            { n: 6, name: "Deployment", color: "border-teal-500/50 bg-teal-900/30" },
          ].map((phase, i, arr) => (
            <div key={phase.n} className="flex items-center">
              <div
                className={`rounded-xl border ${phase.color} px-3 py-2 text-center min-w-[86px]`}
              >
                <div className="text-[10px] font-bold text-slate-400">Phase {phase.n}</div>
                <div className="text-xs font-semibold text-slate-200 whitespace-pre-line leading-tight mt-0.5">
                  {phase.name}
                </div>
              </div>
              {i < arr.length - 1 && (
                <div className="text-slate-600 text-sm px-1">→</div>
              )}
            </div>
          ))}
        </div>
        <div className="mt-3 grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px]">
          <span className="text-amber-300 font-semibold">← Loop A  2→1 (after 2.4)</span>
          <span className="text-rose-300 font-semibold">← Loop B  4→3 (after 4.4)</span>
          <span className="text-purple-300 font-semibold">← Loop C  5→1 (after 5.1)</span>
          <span className="text-teal-300 font-semibold">← Loop D  6→1 (after 6.4, optional)</span>
        </div>
      </div>

      {/* Loop cards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {loops.map((loop) => (
          <div key={loop.label} className={`rounded-2xl border ${loop.color} p-5 glow-card`}>
            <div className="flex items-center gap-2 mb-4">
              <span
                className={`rounded-full px-3 py-1 text-sm font-extrabold ${loop.badge}`}
              >
                Loop {loop.label}
              </span>
              <span className="text-lg">{loop.emoji}</span>
              <span className="text-slate-300 text-sm font-semibold">{loop.from}</span>
            </div>

            <div className="space-y-2 text-xs">
              <Row label="Fires after" value={loop.fromPhase} />
              <Row label="Jumps to" value={loop.toSubstep} />

              <div>
                <div className="text-slate-500 uppercase tracking-wide text-[10px] font-bold mb-1">
                  Trigger condition
                </div>
                <div className="text-slate-300">{loop.trigger}</div>
              </div>

              <div>
                <div className="text-slate-500 uppercase tracking-wide text-[10px] font-bold mb-1">
                  Action
                </div>
                <div className="text-slate-300">{loop.action}</div>
              </div>

              <div>
                <div className="text-slate-500 uppercase tracking-wide text-[10px] font-bold mb-1">
                  Cap / guard
                </div>
                <div className="text-yellow-300/80">{loop.cap}</div>
              </div>

              <div>
                <div className="text-slate-500 uppercase tracking-wide text-[10px] font-bold mb-1">
                  State fields read
                </div>
                <div className="font-mono text-pink-300 text-[11px]">
                  {loop.stateFields.join("  ·  ")}
                </div>
              </div>

              <div className="border-t border-white/10 pt-2 text-slate-500 italic">
                {loop.example}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* PM directive format */}
      <div className="rounded-2xl border border-surface-border bg-surface-raised p-5 glow-card">
        <h3 className="text-sm font-bold text-slate-300 mb-3">
          📤 PM loop_back directive (JSON)
        </h3>
        <pre className="bg-slate-900/60 rounded-xl p-4 text-xs font-mono text-green-300 overflow-x-auto">{`{
  "action": "loop_back",
  "target_substep": "3.2",
  "loop_label": "B",
  "loop_to_phase": 3,
  "reason": "md.models[-1].cv_score = 0.61 below threshold 0.80; validator_findings = [\\"cabin_deck feature missing\\"]"
}`}</pre>
        <p className="text-xs text-slate-500 mt-2">
          The <code className="text-pink-300">reason</code> must cite a concrete state field.
          The orchestrator records the event into{" "}
          <code className="text-pink-300">state.loop_history[]</code> with label, from_phase,
          to_phase, reason, and UTC timestamp.
        </p>
      </div>

      {/* Substep prereq gate */}
      <div className="rounded-2xl border border-surface-border bg-surface-raised p-5 glow-card">
        <h3 className="text-sm font-bold text-slate-300 mb-3">
          🔒 Anti-phase-jumping gate (<code className="text-pink-300 text-xs">substep_prereqs_satisfied</code>)
        </h3>
        <div className="space-y-1 text-xs font-mono">
          {[
            ["1.3", "bu.business_objectives must be set"],
            ["1.4", "bu.data_mining_goals must be set"],
            ["2.3", "du.data_description_report must be set"],
            ["3.1", "du.data_quality_report must be set"],
            ["4.1", "dp.dataset must be non-empty"],
            ["4.4", "md.models must be non-empty"],
            ["5.1", "md.models must be non-empty"],
            ["6.1", "md.chosen_model must be set"],
            ["6.2", "md.chosen_model and chosen_model.evaluation_bundle must be set"],
            ["6.3", "dep.story_spec_path must be set"],
          ].map(([substep, prereq]) => (
            <div
              key={substep}
              className="flex gap-3 py-1 border-b border-surface-border/30"
            >
              <code className="text-fuchsia-300 w-8 shrink-0">{substep}</code>
              <span className="text-slate-400">{prereq}</span>
            </div>
          ))}
        </div>
        <p className="text-xs text-slate-500 mt-3">
          If a prereq is missing the orchestrator skips the PM and advances to the substep that
          fills it — preventing the PM from accidentally phase-jumping after a loop.
        </p>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-2 items-start">
      <span className="text-slate-500 uppercase tracking-wide text-[10px] font-bold shrink-0 w-20 pt-0.5">
        {label}
      </span>
      <span className="text-slate-300">{value}</span>
    </div>
  );
}
