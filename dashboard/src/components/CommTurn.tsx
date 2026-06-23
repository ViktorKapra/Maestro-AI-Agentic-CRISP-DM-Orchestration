import { useState } from "react";
import type { CommunicationRecord } from "../shared/types";

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
  const [expanded, setExpanded] = useState(false);
  const parseOk = record.outcome?.parse_ok;
  const failed = parseOk === false;

  const messages = record.provider?.messages;
  const response =
    record.outcome?.raw_response ??
    record.provider?.raw_response ??
    "";

  const taskDesc = record.maads?.task_description;

  return (
    <article
      id={`comm-${record.id}`}
      className={`rounded-lg border p-4 transition-colors ${
        highlighted
          ? "border-accent bg-accent/10"
          : "border-surface-border bg-surface-raised"
      }`}
    >
      <header className="flex flex-wrap items-center gap-2 mb-2">
        <span className="font-mono text-xs text-accent-muted">{record.id}</span>
        <span className="rounded bg-surface-border px-2 py-0.5 text-xs">
          {record.agent_name || record.role || "agent"}
        </span>
        {record.model && (
          <span className="text-xs text-slate-500">{record.model}</span>
        )}
        {record.substep && (
          <span className="text-xs text-slate-500">§{record.substep}</span>
        )}
        {failed && (
          <span className="rounded bg-red-900/50 text-red-300 px-2 py-0.5 text-xs">
            parse failed
          </span>
        )}
        {!record.closed && (
          <span className="rounded bg-green-900/40 text-green-300 px-2 py-0.5 text-xs">
            in flight
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
        className="text-sm text-accent-muted hover:text-accent"
      >
        {expanded ? "Hide transcript" : "Show transcript"}
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
        </div>
      )}
    </article>
  );
}
