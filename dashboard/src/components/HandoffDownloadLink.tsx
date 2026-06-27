import { useSelectedRun } from "../shared/selectedRun";

interface Props {
  caseId: string;
  show: boolean;
  className?: string;
}

export function HandoffDownloadLink({ caseId, show, className = "" }: Props) {
  const { runId } = useSelectedRun();
  if (!show) {
    return null;
  }

  const href = `/api/cases/${caseId}/reports/handoff_standard.zip${
    runId ? `?run_id=${encodeURIComponent(runId)}` : ""
  }`;

  return (
    <p className={`text-xs text-slate-500 ${className}`.trim()}>
      <a
        href={href}
        className="text-accent hover:underline"
        download="handoff_standard.zip"
      >
        Download handoff_standard.zip
      </a>
      <span className="text-slate-600">
        {" "}
        — portable bundle for external DS (data, reports, notebook)
      </span>
    </p>
  );
}
