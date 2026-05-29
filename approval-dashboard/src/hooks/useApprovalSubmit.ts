import { useMutation, useQueryClient } from '@tanstack/react-query';
import { sendApproval } from '../api/agentfield';
import { ApprovalRequest } from '../api/types';

/**
 * Hook to submit approval decisions.
 */
export function useApprovalSubmit() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: ApprovalRequest) => sendApproval(request),
    onSuccess: () => {
      // Invalidate approvals query to trigger refresh
      queryClient.invalidateQueries({ queryKey: ['approvals'] });
    },
  });
}
