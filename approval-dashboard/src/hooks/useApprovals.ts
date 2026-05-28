import { useQuery } from '@tanstack/react-query';
import { fetchWaitingRuns, fetchRunDetails, POLL_INTERVAL_MS } from '../api/agentfield';
import { parseApprovalContext } from '../utils/parser';
import { ApprovalContext } from '../api/types';

/**
 * Hook to poll for waiting runs and parse approval contexts.
 */
export function useApprovals() {
  return useQuery<ApprovalContext[], Error>({
    queryKey: ['approvals'],
    queryFn: async () => {
      // Fetch waiting runs
      const runs = await fetchWaitingRuns();

      // Filter to nd-worker runs only
      const workerRuns = runs.filter((run) => run.nodeId === 'nd-worker');

      // Fetch details and parse context for each run
      const contexts = await Promise.all(
        workerRuns.map(async (run) => {
          try {
            const details = await fetchRunDetails(run.runId);
            return parseApprovalContext(details);
          } catch (error) {
            console.error(`Failed to fetch details for run ${run.runId}:`, error);
            return null;
          }
        })
      );

      // Filter out nulls and return
      return contexts.filter((ctx): ctx is ApprovalContext => ctx !== null);
    },
    refetchInterval: POLL_INTERVAL_MS,
    retry: true,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 10000),
  });
}
