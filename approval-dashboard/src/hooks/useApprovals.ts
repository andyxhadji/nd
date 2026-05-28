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
      // Fetch waiting runs (already filtered to paused status)
      const runs = await fetchWaitingRuns();

      // Filter to nd-worker runs only (agent_id should be 'nd-worker')
      const workerRuns = runs.filter((run) => run.agent_id === 'nd-worker');

      // Fetch details and parse context for each run
      const contexts = await Promise.all(
        workerRuns.map(async (run) => {
          try {
            const details = await fetchRunDetails(run.run_id);
            return parseApprovalContext(details);
          } catch (error) {
            console.error(`Failed to fetch details for run ${run.run_id}:`, error);
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
