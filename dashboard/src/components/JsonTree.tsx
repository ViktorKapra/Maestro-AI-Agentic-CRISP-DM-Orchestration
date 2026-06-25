import { useState } from "react";

interface Props {
  value: unknown;
  name?: string;
  depth?: number;
  defaultOpen?: boolean;
}

function isExpandable(value: unknown): value is Record<string, unknown> | unknown[] {
  return value !== null && typeof value === "object";
}

function isEmpty(value: unknown): boolean {
  if (value === null || value === undefined) return true;
  if (Array.isArray(value)) return value.length === 0;
  if (typeof value === "object") return Object.keys(value).length === 0;
  return false;
}

function preview(value: unknown): string {
  if (value === null) return "null";
  if (value === undefined) return "undefined";
  if (Array.isArray(value)) return `Array(${value.length})`;
  if (typeof value === "object") return `Object(${Object.keys(value).length})`;
  if (typeof value === "string") {
    const s = value.length > 60 ? `${value.slice(0, 60)}…` : value;
    return JSON.stringify(s);
  }
  return String(value);
}

export function JsonTree({ value, name, depth = 0, defaultOpen }: Props) {
  const expandable = isExpandable(value);
  const [open, setOpen] = useState(
    defaultOpen ?? (depth < 1 && expandable && !isEmpty(value)),
  );

  if (!expandable) {
    return (
      <div className="font-mono text-xs leading-relaxed" style={{ paddingLeft: depth * 12 }}>
        {name != null && <span className="text-accent-muted">{name}: </span>}
        <span className="text-slate-300">{preview(value)}</span>
      </div>
    );
  }

  const entries = Array.isArray(value)
    ? value.map((v, i) => [String(i), v] as const)
    : Object.entries(value);

  return (
    <div style={{ paddingLeft: depth > 0 ? 12 : 0 }}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="font-mono text-xs text-left hover:text-slate-200 text-slate-400"
      >
        <span className="inline-block w-3">{open ? "▾" : "▸"}</span>
        {name != null && <span className="text-accent-muted">{name}: </span>}
        {!open && <span className="text-slate-500">{preview(value)}</span>}
      </button>
      {open && (
        <div className="border-l border-surface-border ml-1 pl-1">
          {entries.length === 0 ? (
            <div className="text-xs text-slate-600 pl-3">empty</div>
          ) : (
            entries.map(([key, child]) => (
              <JsonTree
                key={key}
                name={key}
                value={child}
                depth={depth + 1}
                defaultOpen={depth < 2}
              />
            ))
          )}
        </div>
      )}
    </div>
  );
}
