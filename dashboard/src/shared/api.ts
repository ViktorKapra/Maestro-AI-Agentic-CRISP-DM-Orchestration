import type {
  CaseSummary,
  CommunicationRecord,
  CommunicationsSummary,
  CrispDMStatePayload,
  GraphPayload,
  LiveSummary,
  ProcessView,
  RagView,
  StatusPayload,
  TraceSummary,
} from "./types";

const API = "/api";

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export function fetchCases(): Promise<CaseSummary[]> {
  return fetchJson(`${API}/cases`);
}

export function fetchLiveSummary(caseId: string): Promise<LiveSummary> {
  return fetchJson(`${API}/cases/${encodeURIComponent(caseId)}/live_summary`);
}

export function fetchStatus(caseId: string): Promise<StatusPayload> {
  return fetchJson(`${API}/cases/${encodeURIComponent(caseId)}/status`);
}

export function fetchTraceSummary(caseId: string): Promise<TraceSummary> {
  return fetchJson(
    `${API}/cases/${encodeURIComponent(caseId)}/trace/summary?limit=50`,
  );
}

export function fetchCommunications(
  caseId: string,
  opts?: { sinceId?: string; limit?: number },
): Promise<CommunicationRecord[]> {
  const params = new URLSearchParams();
  if (opts?.sinceId) params.set("since_id", opts.sinceId);
  if (opts?.limit) params.set("limit", String(opts.limit));
  const qs = params.toString();
  return fetchJson(
    `${API}/cases/${encodeURIComponent(caseId)}/communications${qs ? `?${qs}` : ""}`,
  );
}

export function fetchCommunicationsSummary(
  caseId: string,
): Promise<CommunicationsSummary> {
  return fetchJson(
    `${API}/cases/${encodeURIComponent(caseId)}/communications/summary`,
  );
}

export function fetchGraph(caseId: string): Promise<GraphPayload> {
  return fetchJson(`${API}/cases/${encodeURIComponent(caseId)}/graph`);
}

export function fetchProcess(caseId: string): Promise<ProcessView> {
  return fetchJson(`${API}/cases/${encodeURIComponent(caseId)}/process`);
}

export function fetchState(caseId: string): Promise<CrispDMStatePayload> {
  return fetchJson(`${API}/cases/${encodeURIComponent(caseId)}/state`);
}

export function fetchRag(caseId: string): Promise<RagView> {
  return fetchJson(`${API}/cases/${encodeURIComponent(caseId)}/rag`);
}
