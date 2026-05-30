import { useState } from 'react';
import { ExternalLink, ChevronDown } from 'lucide-react';
import { GroupedApproval, ApprovalDecision } from '../api/types';
import { TabbedDiffViewer } from './TabbedDiffViewer';
import { ApprovalCard } from './ApprovalCard';
import { aggregateDiffs } from '../utils/diff-aggregator';
import { useGroupedApprovalSubmit } from '../hooks/useGroupedApprovalSubmit';

interface GroupedApprovalCardProps {
  group: GroupedApproval;
}

export function GroupedApprovalCard({ group }: GroupedApprovalCardProps) {
  const [expanded, setExpanded] = useState(false);
  const [showFeedback, setShowFeedback] = useState(false);
  const [feedback, setFeedback] = useState('');
  const { mutate, isPending } = useGroupedApprovalSubmit();

  const { combined, tabs } = aggregateDiffs(group.approvals);

  const handleBatchApproval = (decision: ApprovalDecision) => {
    const requestIds = group.approvals.map(a => a.requestId);
    mutate({
      requestIds,
      decision,
      feedback: feedback || undefined,
    });
  };

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm hover:shadow-md transition-shadow">
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <a
              href={group.sourceUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 text-lg font-semibold text-blue-600 hover:text-blue-800"
            >
              {group.sourceIdentifier}
              <ExternalLink className="w-4 h-4" />
            </a>
          </div>
          <p className="text-sm text-gray-600 mt-1">{group.sourceTitle}</p>
        </div>
      </div>

      {/* Approval Counts */}
      <div className="flex gap-2 mb-4">
        <span className="text-sm text-gray-600">
          {group.approvals.length} approval{group.approvals.length !== 1 ? 's' : ''}:
        </span>
        {group.approvalCounts.spec > 0 && (
          <span className="px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs font-medium">
            Spec: {group.approvalCounts.spec}
          </span>
        )}
        {group.approvalCounts.roborev > 0 && (
          <span className="px-2 py-1 bg-orange-100 text-orange-700 rounded text-xs font-medium">
            Roborev: {group.approvalCounts.roborev}
          </span>
        )}
        {group.approvalCounts.post > 0 && (
          <span className="px-2 py-1 bg-green-100 text-green-700 rounded text-xs font-medium">
            Post: {group.approvalCounts.post}
          </span>
        )}
      </div>

      {/* Tabbed Diff Viewer */}
      <div className="mb-6">
        <TabbedDiffViewer combined={combined} tabs={tabs} />
      </div>

      {/* Batch Approval Actions */}
      <div className="space-y-4">
        <div className="flex gap-3">
          <button
            onClick={() => handleBatchApproval('approved')}
            disabled={isPending}
            className="flex-1 px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:bg-gray-300 disabled:cursor-not-allowed font-medium"
          >
            {isPending ? 'Submitting...' : 'Approve All'}
          </button>
          <button
            onClick={() => handleBatchApproval('rejected')}
            disabled={isPending}
            className="flex-1 px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 disabled:bg-gray-300 disabled:cursor-not-allowed font-medium"
          >
            {isPending ? 'Submitting...' : 'Reject All'}
          </button>
          <button
            onClick={() => setExpanded(!expanded)}
            className="px-4 py-2 bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200 font-medium"
          >
            Review Individually
          </button>
        </div>

        {/* Feedback textarea */}
        {showFeedback && (
          <textarea
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            placeholder="Optional feedback (sent to all approvals)"
            className="w-full px-3 py-2 border border-gray-300 rounded-md resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
            rows={3}
          />
        )}
        <button
          onClick={() => setShowFeedback(!showFeedback)}
          className="text-sm text-blue-600 hover:text-blue-800"
        >
          {showFeedback ? 'Hide' : 'Add'} feedback
        </button>
      </div>

      {/* Individual Approvals (expanded) */}
      {expanded && (
        <div className="mt-6 pt-6 border-t border-gray-200">
          <div className="flex items-center gap-2 mb-4">
            <ChevronDown className="w-5 h-5 text-gray-600" />
            <h3 className="font-semibold text-gray-900">Individual Approvals</h3>
          </div>
          <div className="space-y-4">
            {group.approvals.map((approval) => (
              <ApprovalCard
                key={approval.requestId}
                approval={approval}
                trace={[]}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
