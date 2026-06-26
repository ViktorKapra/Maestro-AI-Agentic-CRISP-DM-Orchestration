import { useState } from "react";
import { CommTurn } from "../components/CommTurn";
import { useCommunications } from "../hooks/useCasePolling";
import { useTheme } from "../shared/theme";

interface Props {
  caseId: string;
  highlightCommId?: string | null;
}

export function Communications({ caseId, highlightCommId }: Props) {
  const { clean } = useTheme();
  const { data: communications } = useCommunications(caseId, { limit: 200 });
  const [selected, setSelected] = useState<string | null>(
    highlightCommId ?? null,
  );

  const active = highlightCommId ?? selected;

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-rose-300 bg-rose-100/70 px-4 py-2 text-sm text-rose-700 font-semibold">
        {clean("🔒 Contains full system prompts and LLM responses — local use only, keep it secret bestie! 🤫")}
      </div>

      {!communications?.length && (
        <p className="text-slate-500 text-sm">{clean("🫧 No LLM communications yet…")}</p>
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
