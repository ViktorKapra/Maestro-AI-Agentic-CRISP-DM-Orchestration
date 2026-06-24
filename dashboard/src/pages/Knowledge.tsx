import { useRag } from "../hooks/useCasePolling";
import type { RagCorpusFile } from "../shared/types";

interface Props {
  caseId: string;
}

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  return `${(n / 1024).toFixed(1)} KB`;
}

function roleLabel(role: RagCorpusFile["role"]): string {
  if (role === "case") return "Case";
  if (role === "experience") return "Prior run";
  return "Shared";
}

function backendLabel(backend: string, model: string | null): string {
  if (backend === "none") return "No corpus";
  const name = model ? ` (${model})` : "";
  if (backend === "ollama") return `Ollama embeddings${name}`;
  if (backend === "openai") return `OpenAI embeddings${name}`;
  return `Keyword fallback${name}`;
}

export function Knowledge({ caseId }: Props) {
  const { data: rag, isLoading, error } = useRag(caseId);

  if (error) {
    return (
      <p className="text-red-400 text-sm">
        Could not load RAG view — run may not have started yet.
      </p>
    );
  }

  if (isLoading && !rag) {
    return <p className="text-slate-500">Loading knowledge / RAG…</p>;
  }

  if (!rag) {
    return <p className="text-slate-500">No RAG data.</p>;
  }

  return (
    <div className="space-y-6">
      <section className="rounded-xl border border-surface-border bg-surface-raised p-5 space-y-4">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-lg font-medium">Domain RAG</h2>
          <p className="text-xs text-slate-500">
            Updated {new Date(rag.updated_at).toLocaleString()}
          </p>
        </div>
        <p className="text-sm text-slate-400">
          Grounds the <span className="text-slate-200">Domain Expert</span> at
          substeps {rag.domain_substeps_using_rag.join(", ")} via{" "}
          <code className="text-accent-muted text-xs">maads.rag</code> and CrewAI
          Knowledge.
        </p>
        <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 text-sm">
          <div>
            <dt className="text-slate-500">Embedder</dt>
            <dd className="text-slate-200">
              {backendLabel(rag.embedding_backend, rag.embedding_model)}
            </dd>
          </div>
          <div>
            <dt className="text-slate-500">Indexed chunks</dt>
            <dd className="text-slate-200 font-mono">{rag.chunk_count}</dd>
          </div>
          <div>
            <dt className="text-slate-500">CrewAI Knowledge</dt>
            <dd className="text-slate-200">
              {rag.crewai_knowledge_enabled ? "Enabled" : "Off"}
            </dd>
          </div>
          <div>
            <dt className="text-slate-500">Corpus files</dt>
            <dd className="text-slate-200 font-mono">{rag.corpus_files.length}</dd>
          </div>
        </dl>
      </section>

      <section className="rounded-xl border border-surface-border bg-surface-raised p-5">
        <h3 className="text-base font-medium mb-3">Knowledge corpus</h3>
        {!rag.corpus_files.length ? (
          <p className="text-sm text-slate-500">No markdown files in knowledge/.</p>
        ) : (
          <ul className="space-y-2 text-sm">
            {rag.corpus_files.map((file) => (
              <li
                key={file.name}
                className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border border-surface-border bg-surface px-3 py-2"
              >
                <span className="font-mono text-accent-muted">{file.name}</span>
                <span className="rounded bg-surface-border px-2 py-0.5 text-xs text-slate-400">
                  {roleLabel(file.role)}
                </span>
                <span className="text-slate-500">{formatBytes(file.size_bytes)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="rounded-xl border border-surface-border bg-surface-raised p-5 space-y-3">
        <h3 className="text-base font-medium">Retrieval query</h3>
        <p className="text-xs text-slate-500">
          Built from case config and current data-understanding reports in state.
        </p>
        <pre className="text-xs text-slate-300 whitespace-pre-wrap break-words rounded-lg bg-surface border border-surface-border p-3 max-h-40 overflow-y-auto">
          {rag.retrieval_query_preview || "(empty)"}
        </pre>
      </section>

      <section className="rounded-xl border border-surface-border bg-surface-raised p-5 space-y-3">
        <h3 className="text-base font-medium">
          Retrieved passages ({rag.retrieved_passages.length})
        </h3>
        <p className="text-xs text-slate-500">
          Top matches injected into Domain Expert prompts for the current state.
        </p>
        {!rag.retrieved_passages.length ? (
          <p className="text-sm text-slate-500">No passages retrieved.</p>
        ) : (
          <ul className="space-y-3">
            {rag.retrieved_passages.map((p, i) => (
              <li
                key={`${p.source}-${i}`}
                className="rounded-lg border border-surface-border bg-surface p-3 text-sm"
              >
                <p className="font-mono text-xs text-accent-muted mb-1">{p.source}</p>
                <p className="text-slate-300 whitespace-pre-wrap">{p.text}</p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
