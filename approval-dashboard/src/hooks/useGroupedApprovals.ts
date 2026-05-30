import { useMemo } from 'react';
import { useApprovals } from './useApprovals';
import { groupApprovalsBySource } from '../utils/grouping';

export function useGroupedApprovals() {
  const { data: approvals, ...rest } = useApprovals();

  const grouped = useMemo(() => {
    if (!approvals) return [];
    return groupApprovalsBySource(approvals);
  }, [approvals]);

  return { data: grouped, ...rest };
}
