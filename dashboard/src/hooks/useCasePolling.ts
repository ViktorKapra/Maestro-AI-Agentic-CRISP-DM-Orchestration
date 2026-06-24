import { useQuery } from "@tanstack/react-query";
import {
  fetchCases,
  fetchCommunications,
  fetchCommunicationsSummary,
  fetchGraph,
  fetchProcess,
  fetchRag,
  fetchState,
  fetchStatus,
  fetchTraceSummary,
} from "../shared/api";

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

export function useStatus(caseId: string | null) {
  return useQuery({
    queryKey: ["status", caseId],
    queryFn: () => fetchStatus(caseId!),
    enabled: !!caseId,
    ...pollOptions,
  });
}

export function useTraceSummary(caseId: string | null) {
  return useQuery({
    queryKey: ["traceSummary", caseId],
    queryFn: () => fetchTraceSummary(caseId!),
    enabled: !!caseId,
    ...pollOptions,
  });
}

export function useCommunications(caseId: string | null) {
  return useQuery({
    queryKey: ["communications", caseId],
    queryFn: () => fetchCommunications(caseId!),
    enabled: !!caseId,
    ...pollOptions,
  });
}

export function useCommunicationsSummary(caseId: string | null) {
  return useQuery({
    queryKey: ["communicationsSummary", caseId],
    queryFn: () => fetchCommunicationsSummary(caseId!),
    enabled: !!caseId,
    ...pollOptions,
  });
}

export function useGraph(caseId: string | null) {
  return useQuery({
    queryKey: ["graph", caseId],
    queryFn: () => fetchGraph(caseId!),
    enabled: !!caseId,
    ...pollOptions,
  });
}

export function useProcess(caseId: string | null) {
  return useQuery({
    queryKey: ["process", caseId],
    queryFn: () => fetchProcess(caseId!),
    enabled: !!caseId,
    ...pollOptions,
  });
}

export function useCrispDMState(caseId: string | null) {
  return useQuery({
    queryKey: ["crispdmState", caseId],
    queryFn: () => fetchState(caseId!),
    enabled: !!caseId,
    ...pollOptions,
  });
}

export function useRag(caseId: string | null) {
  return useQuery({
    queryKey: ["rag", caseId],
    queryFn: () => fetchRag(caseId!),
    enabled: !!caseId,
    ...pollOptions,
  });
}
