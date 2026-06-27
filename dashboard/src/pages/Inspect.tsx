import { useState } from "react";
import { Communications } from "./Communications";
import { State } from "./State";

interface Props {
  caseId: string;
}

type View = "state" | "communications";

const VIEWS: { id: View; label: string }[] = [
  { id: "state", label: "State" },
  { id: "communications", label: "Communications" },
];

export function Inspect({ caseId }: Props) {
  const [view, setView] = useState<View>("state");

  return (
    <div className="space-y-5">
      <div className="inline-flex items-center gap-1 rounded-full border border-surface-border bg-surface p-1 text-sm font-semibold">
        {VIEWS.map((v) => (
          <button
            key={v.id}
            type="button"
            onClick={() => setView(v.id)}
            aria-pressed={view === v.id}
            className={`rounded-full px-4 py-1.5 transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 ${
              view === v.id
                ? "bg-gradient-to-r from-fuchsia-500 to-pink-500 text-white shadow"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            {v.label}
          </button>
        ))}
      </div>

      {view === "state" ? (
        <State caseId={caseId} />
      ) : (
        <Communications caseId={caseId} />
      )}
    </div>
  );
}
