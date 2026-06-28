import { ConclusionsPanel } from "../components/ConclusionsPanel";
import { Loading } from "../components/Loading";
import { PhaseRail } from "../components/PhaseRail";
import { SubstepChecklist } from "../components/SubstepChecklist";
import { TeamCard } from "../components/TeamCard";
import { useProcess } from "../hooks/useCasePolling";

interface Props {
  caseId: string;
}

export function Process({ caseId }: Props) {
  const { data: process, isLoading, error } = useProcess(caseId);

  if (error) {
    return (
      <p className="text-red-400 text-sm">
        Could not load process view — run may not have started yet.
      </p>
    );
  }

  if (isLoading && !process) {
    return <Loading label="Loading process view…" />;
  }

  return (
    <div className="space-y-6">
      <section className="rounded-xl border border-surface-border bg-surface-raised p-5 space-y-3">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-lg font-medium">CRISP-DM phases</h2>
          {process?.current_substep && (
            <p className="text-sm text-slate-400">
              §{process.current_substep} — {process.current_substep_name}
            </p>
          )}
        </div>
        {process?.activity && (
          <p className="text-sm text-slate-300">{process.activity}</p>
        )}
        <PhaseRail phases={process?.phases} />
      </section>

      <section className="rounded-xl border border-surface-border bg-surface-raised p-5 space-y-4">
        <h2 className="text-lg font-medium">Team</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {process?.team.map((member) => (
            <TeamCard key={member.id} member={member} />
          ))}
        </div>
      </section>

      <section className="rounded-xl border border-surface-border bg-surface-raised p-5">
        <h2 className="text-lg font-medium mb-4">Conclusions so far</h2>
        <ConclusionsPanel
          conclusions={process?.conclusions}
          deliverables={process?.deliverables}
          config={process?.config}
        />
      </section>

      {(process?.validator_findings?.length ?? 0) > 0 && (
        <section className="rounded-xl border border-amber-600/30 bg-amber-900/10 p-5">
          <h2 className="text-lg font-medium text-amber-400 mb-2">
            Validator findings
          </h2>
          <ul className="text-sm text-amber-200/80 list-disc list-inside">
            {process!.validator_findings.map((f, i) => (
              <li key={i}>{f}</li>
            ))}
          </ul>
        </section>
      )}

      {(process?.loops?.length ?? 0) > 0 && (
        <section className="rounded-xl border border-surface-border bg-surface-raised p-5">
          <h2 className="text-lg font-medium mb-3">Loop history</h2>
          <ul className="space-y-2 text-sm">
            {process!.loops.map((loop, i) => (
              <li key={i} className="text-slate-400">
                <span className="font-mono text-accent-muted">
                  Loop {loop.label}
                </span>
                : phase {loop.from_phase} → {loop.to_phase}
                {loop.reason && ` — ${loop.reason}`}
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="rounded-xl border border-surface-border bg-surface-raised p-5">
        <h2 className="text-lg font-medium mb-4">Substep checklist</h2>
        <SubstepChecklist phases={process?.phases} currentPhase={process?.current_phase} />
      </section>
    </div>
  );
}
