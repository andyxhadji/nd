import { useMutation, useQueryClient } from '@tanstack/react-query';
import { sendApproval } from '../api/agentfield';
import { ApprovalDecision } from '../api/types';

interface BatchApprovalRequest {
  requestIds: string[];
  decision: ApprovalDecision;
  feedback?: string;
}

interface BatchApprovalResult {
  succeeded: number;
  failed: number;
  results: PromiseSettledResult<any>[];
}

export function useGroupedApprovalSubmit() {
  const queryClient = useQueryClient();

  return useMutation<BatchApprovalResult, Error, BatchApprovalRequest>({
    mutationFn: async (req: BatchApprovalRequest) => {
      // Send all approval requests in parallel
      const results = await Promise.allSettled(
        req.requestIds.map(id =>
          sendApproval({ requestId: id, decision: req.decision, feedback: req.feedback })
        )
      );

      const succeeded = results.filter(r => r.status === 'fulfilled').length;
      const failed = results.filter(r => r.status === 'rejected').length;

      return { succeeded, failed, results };
    },
    onSuccess: () => {
      // Refetch approvals after successful submission
      queryClient.invalidateQueries({ queryKey: ['approvals'] });
    },
  });
}
