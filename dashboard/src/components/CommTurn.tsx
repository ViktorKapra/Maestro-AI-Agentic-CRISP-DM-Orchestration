import { useState } from "react";
import type { CommunicationRecord } from "../shared/types";
import { useTheme } from "../shared/theme";

interface Props {
  record: CommunicationRecord;
  highlighted?: boolean;
  onSelect?: (id: string) => void;
}

function extractText(value: unknown): string {
  if (typeof value === "string") return value;
  if (value && typeof value === "object") {
    const obj = value as Record<string, unknown>;
    if (typeof obj.text === "string") return obj.text;
    if (typeof obj.content === "string") return obj.content;
    return JSON.stringify(value, null, 2);
  }
  return String(value ?? "");
}

export function CommTurn({ record, highlighted, onSelect }: Props) {
  const { clean } = useTheme();
  const [expanded, setExpanded] = useState(false);
  const parseOk = record.outcome?.parse_ok;
  const jsonValid = record.outcome?.json_valid;
  const schemaOk = record.outcome?.schema_ok;
  const schemaErrors = record.outcome?.schema_errors;
  const failed = parseOk === false;
  const schemaOnlyFailure =
    jsonValid === true && schemaOk === false;

  const messages = record.provider?.messages;
  const response =
    record.outcome?.raw_response ??
    record.provider?.raw_response ??
    "";

  const taskDesc = record.maads?.task_description;

  return (
    <article
      id={`comm-${record.id}`}
      className={`rounded-2xl border p-4 transition-colors ${
        highlighted
          ? "border-accent bg-accent/10 glow-card"
          : "border-surface-border bg-surface-raised"
      }`}
    >
      <header className="flex flex-wrap items-center gap-2 mb-2">
        <span className="font-mono text-xs text-accent-muted font-semibold">{record.id}</span>
        <span className="rounded-full bg-surface-border px-2 py-0.5 text-xs font-semibold">
          {clean("🤖")} {record.agent_name || record.role || "agent"}
        </span>
        {record.model && (
          <span className="text-xs text-slate-500">{record.model}</span>
        )}
        {record.substep && (
          <span className="text-xs text-slate-500">§{record.substep}</span>
        )}
        {failed && (
          <span className="rounded-full bg-rose-100 text-rose-700 border border-rose-300 px-2 py-0.5 text-xs font-semibold">
            {clean("😵")} {schemaOnlyFailure ? "schema failed" : "parse failed"}
          </span>
        )}
        {!record.closed && (
          <span className="rounded-full bg-fuchsia-100 text-fuchsia-700 border border-fuchsia-300 px-2 py-0.5 text-xs font-semibold">
            {clean("✨")} in flight
          </span>
        )}
      </header>

      <div className="flex flex-wrap gap-4 text-sm text-slate-400 mb-2">
        <span>
          tokens: {record.tokens?.prompt ?? "?"} in /{" "}
          {record.tokens?.completion ?? "?"} out (
          {record.tokens?.total ?? "?"})
        </span>
        {record.duration_ms != null && (
          <span>{(record.duration_ms / 1000).toFixed(1)}s</span>
        )}
      </div>

      <button
        type="button"
        onClick={() => {
          setExpanded(!expanded);
          onSelect?.(record.id);
        }}
        className="text-sm font-semibold text-accent-muted hover:text-accent"
      >
        {expanded ? clean("🙈 Hide transcript") : clean("👀 Show transcript")}
      </button>

      {expanded && (
        <div className="mt-3 space-y-3 text-sm">
          {taskDesc != null && (
            <section>
              <h4 className="text-xs uppercase text-slate-500 mb-1">
                Task description
              </h4>
              <pre className="whitespace-pre-wrap rounded bg-surface p-3 text-slate-300 overflow-x-auto max-h-48">
                {extractText(taskDesc)}
              </pre>
            </section>
          )}
          {messages != null && (
            <section>
              <h4 className="text-xs uppercase text-slate-500 mb-1">
                Provider messages
              </h4>
              <pre className="whitespace-pre-wrap rounded bg-surface p-3 text-slate-300 overflow-x-auto max-h-64">
                {typeof messages === "string"
                  ? messages
                  : JSON.stringify(messages, null, 2)}
              </pre>
            </section>
          )}
          {response !== "" && (
            <section>
              <h4 className="text-xs uppercase text-slate-500 mb-1">
                Response
              </h4>
              <pre className="whitespace-pre-wrap rounded bg-surface p-3 text-slate-300 overflow-x-auto max-h-64">
                {extractText(response)}
              </pre>
            </section>
          )}
          {record.outcome?.error && (
            <p className="text-red-400 text-xs">{record.outcome.error}</p>
          )}
          {schemaOnlyFailure && schemaErrors && schemaErrors.length > 0 && (
            <p className="text-amber-400 text-xs">
              Schema: {schemaErrors.slice(0, 3).join("; ")}
            </p>
          )}
        </div>
      )}
    </article>
  );
}
