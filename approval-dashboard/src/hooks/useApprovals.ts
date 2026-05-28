import { useQuery } from '@tanstack/react-query';
import {
  fetchWaitingRuns,
  fetchRunDetails,
  findWaitingExecutions,
  fetchExecutionDetails,
  POLL_INTERVAL_MS,
} from '../api/agentfield';
import { parseApprovalContext } from '../utils/parser';
import { ApprovalContext } from '../api/types';

/**
 * Hook to poll for waiting runs and parse approval contexts.
 */
export function useApprovals() {
  return useQuery<ApprovalContext[], Error>({
    queryKey: ['approvals'],
    queryFn: async () => {
      // Fetch all runs
      const runs = await fetchWaitingRuns();

      // Filter to nd-worker runs only (agent_id should be 'nd-worker')
      const workerRuns = runs.filter((run) => run.agent_id === 'nd-worker');

      // Fetch DAG for each run and find waiting executions
      const allApprovals: ApprovalContext[] = [];

      for (const run of workerRuns) {
        try {
          const dag = await fetchRunDetails(run.run_id);
          const waitingExecutionIds = findWaitingExecutions(dag.dag);

          // Fetch details for each waiting execution
          for (const executionId of waitingExecutionIds) {
            try {
              const executionDetails = await fetchExecutionDetails(executionId);
              const context = parseApprovalContext({ ...run, ...executionDetails });
              if (context) {
                allApprovals.push(context);
              }
            } catch (error) {
              console.error(`Failed to fetch execution ${executionId}:`, error);
            }
          }
        } catch (error) {
          console.error(`Failed to fetch DAG for run ${run.run_id}:`, error);
        }
      }

      return allApprovals;
    },
    refetchInterval: POLL_INTERVAL_MS,
    retry: true,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 10000),
  });
}
