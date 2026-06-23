import { useQuery } from "@tanstack/react-query";
import {
  fetchCases,
  fetchCommunications,
  fetchCommunicationsSummary,
  fetchGraph,
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
