import { GroupedApproval } from '../api/types';
import { GroupedApprovalCard } from './GroupedApprovalCard';

interface GroupedApprovalListProps {
  groups: GroupedApproval[];
}

export function GroupedApprovalList({ groups }: GroupedApprovalListProps) {
  if (groups.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-600 text-lg">No pending approvals</p>
        <p className="text-gray-500 text-sm mt-2">
          Approvals will appear here when nd worker pauses for review
        </p>
      </div>
    );
  }

  // Separate ungrouped approvals
  const grouped = groups.filter(g => !g.sourceIdentifier.startsWith('ungrouped:'));
  const ungrouped = groups.filter(g => g.sourceIdentifier.startsWith('ungrouped:'));

  return (
    <div className="space-y-6">
      {/* Grouped approvals */}
      {grouped.map((group) => (
        <GroupedApprovalCard key={group.sourceIdentifier} group={group} />
      ))}

      {/* Ungrouped section */}
      {ungrouped.length > 0 && (
        <div className="mt-8">
          <div className="mb-4 p-3 bg-yellow-50 border border-yellow-200 rounded-md">
            <p className="text-sm text-yellow-800">
              The following approvals could not be grouped (missing source metadata):
            </p>
          </div>
          {ungrouped.map((group) => (
            <GroupedApprovalCard key={group.sourceIdentifier} group={group} />
          ))}
        </div>
      )}
    </div>
  );
}
