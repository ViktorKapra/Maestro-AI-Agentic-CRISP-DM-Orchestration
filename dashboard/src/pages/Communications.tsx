import { useState } from "react";
import { CommTurn } from "../components/CommTurn";
import { useCommunications } from "../hooks/useCasePolling";

interface Props {
  caseId: string;
  highlightCommId?: string | null;
}

export function Communications({ caseId, highlightCommId }: Props) {
  const { data: communications } = useCommunications(caseId);
  const [selected, setSelected] = useState<string | null>(
    highlightCommId ?? null,
  );

  const active = highlightCommId ?? selected;

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-amber-900/50 bg-amber-950/20 px-4 py-2 text-sm text-amber-200/90">
        Contains full system prompts and LLM responses — local use only.
      </div>

      {!communications?.length && (
        <p className="text-slate-500 text-sm">No LLM communications yet.</p>
      )}

      <div className="space-y-3">
        {communications?.map((record) => (
          <CommTurn
            key={record.id}
            record={record}
            highlighted={active === record.id}
            onSelect={setSelected}
          />
        ))}
      </div>
    </div>
  );
}
