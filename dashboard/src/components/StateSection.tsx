import { useState } from "react";
import { JsonTree } from "./JsonTree";

interface Props {
  title: string;
  description?: string;
  data: unknown;
  defaultOpen?: boolean;
}

function hasContent(data: unknown): boolean {
  if (data === null || data === undefined) return false;
  if (Array.isArray(data)) return data.length > 0;
  if (typeof data === "object") return Object.keys(data).length > 0;
  return true;
}

export function StateSection({ title, description, data, defaultOpen }: Props) {
  const [open, setOpen] = useState(defaultOpen ?? hasContent(data));
  const populated = hasContent(data);

  return (
    <div className="rounded-lg border border-surface-border overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-4 py-2 text-sm text-left hover:bg-surface-border/50"
      >
        <span className="font-medium text-slate-200">
          {title}
          {!populated && (
            <span className="ml-2 text-xs text-slate-600 font-normal">not set yet</span>
          )}
        </span>
        <span className="text-slate-500 text-xs">{open ? "▾" : "▸"}</span>
      </button>
      {description && open && (
        <p className="px-4 pb-2 text-xs text-slate-500">{description}</p>
      )}
      {open && (
        <div className="border-t border-surface-border px-4 py-3 max-h-96 overflow-auto">
          {populated ? (
            <JsonTree value={data} defaultOpen={false} />
          ) : (
            <p className="text-xs text-slate-600">No data</p>
          )}
        </div>
      )}
    </div>
  );
}
