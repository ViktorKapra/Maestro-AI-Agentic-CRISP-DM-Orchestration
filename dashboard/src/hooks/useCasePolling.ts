import { useQuery } from "@tanstack/react-query";
import {
  fetchCaseRuns,
  fetchCases,
  fetchCommunications,
  fetchCommunicationsSummary,
  fetchGraph,
  fetchLiveSummary,
  fetchModels,
  fetchProcess,
  fetchRag,
  fetchState,
  fetchStatus,
  fetchTraceSummary,
} from "../shared/api";
import { useSelectedRun } from "../shared/selectedRun";

const POLL_MS = 2000;

const pollOptions = {
  refetchInterval: POLL_MS,
  refetchIntervalInBackground: false,
};

export function useCases() {
  return useQuery({
    queryKey: ["cases"],
    queryFn: fetchCases,
    ...pollOptions,
  });
}

export function useCaseRuns(caseId: string | null) {
  return useQuery({
    queryKey: ["caseRuns", caseId],
    queryFn: () => fetchCaseRuns(caseId!),
    enabled: !!caseId,
    ...pollOptions,
  });
}

export function useLiveSummary(caseId: string | null) {
  const { runId } = useSelectedRun();
  return useQuery({
    queryKey: ["liveSummary", caseId, runId],
    queryFn: () => fetchLiveSummary(caseId!, runId),
    enabled: !!caseId,
    ...pollOptions,
  });
}

export function useStatus(caseId: string | null) {
  const { runId } = useSelectedRun();
  return useQuery({
    queryKey: ["status", caseId, runId],
    queryFn: () => fetchStatus(caseId!, runId),
    enabled: !!caseId,
    ...pollOptions,
  });
}

export function useTraceSummary(caseId: string | null) {
  const { runId } = useSelectedRun();
  return useQuery({
    queryKey: ["traceSummary", caseId, runId],
    queryFn: () => fetchTraceSummary(caseId!, runId),
    enabled: !!caseId,
    ...pollOptions,
  });
}

export function useCommunications(
  caseId: string | null,
  opts?: { sinceId?: string; limit?: number },
) {
  const { runId } = useSelectedRun();
  return useQuery({
    queryKey: ["communications", caseId, runId, opts?.sinceId, opts?.limit],
    queryFn: () => fetchCommunications(caseId!, opts, runId),
    enabled: !!caseId,
    ...pollOptions,
  });
}

export function useCommunicationsSummary(caseId: string | null) {
  const { runId } = useSelectedRun();
  return useQuery({
    queryKey: ["communicationsSummary", caseId, runId],
    queryFn: () => fetchCommunicationsSummary(caseId!, runId),
    enabled: !!caseId,
    ...pollOptions,
  });
}

export function useGraph(caseId: string | null) {
  const { runId } = useSelectedRun();
  return useQuery({
    queryKey: ["graph", caseId, runId],
    queryFn: () => fetchGraph(caseId!, runId),
    enabled: !!caseId,
    ...pollOptions,
  });
}

export function useProcess(caseId: string | null) {
  const { runId } = useSelectedRun();
  return useQuery({
    queryKey: ["process", caseId, runId],
    queryFn: () => fetchProcess(caseId!, runId),
    enabled: !!caseId,
    ...pollOptions,
  });
}

export function useCrispDMState(caseId: string | null) {
  const { runId } = useSelectedRun();
  return useQuery({
    queryKey: ["crispdmState", caseId, runId],
    queryFn: () => fetchState(caseId!, runId),
    enabled: !!caseId,
    ...pollOptions,
  });
}

export function useRag(caseId: string | null) {
  const { runId } = useSelectedRun();
  return useQuery({
    queryKey: ["rag", caseId, runId],
    queryFn: () => fetchRag(caseId!, runId),
    enabled: !!caseId,
    ...pollOptions,
  });
}

export function useModels() {
  return useQuery({
    queryKey: ["models"],
    queryFn: fetchModels,
  });
}
