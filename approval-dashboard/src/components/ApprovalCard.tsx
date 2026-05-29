import { useState } from 'react';
import { ExternalLink } from 'lucide-react';
import { ApprovalContext, ApprovalDecision } from '../api/types';
import { formatDuration, formatExpiration, getApprovalTypeBadge } from '../utils/formatting';
import { useApprovalSubmit } from '../hooks/useApprovalSubmit';
import { SpecReviewCard } from './SpecReviewCard';
import { RoborevCard } from './RoborevCard';
import { ResponseCard } from './ResponseCard';
import { ExecutionHistory } from './ExecutionHistory';
import { ApprovalActions } from './ApprovalActions';

interface ApprovalCardProps {
  approval: ApprovalContext;
  trace: any[];
}

export function ApprovalCard({ approval, trace }: ApprovalCardProps) {
  const [editedResponse, setEditedResponse] = useState<string | undefined>();
  const { mutate, isPending } = useApprovalSubmit();

  const badge = getApprovalTypeBadge(approval.approvalType);
  const isExpired = approval.expiresAt < new Date();

  const handleSubmit = (decision: ApprovalDecision, feedback?: string) => {
    const finalFeedback = editedResponse || feedback;
    mutate({
      requestId: approval.requestId,
      decision,
      feedback: finalFeedback,
    });
  };

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm hover:shadow-md transition-shadow">
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <span className={`px-3 py-1 rounded-full text-sm font-medium ${badge.bg} ${badge.text}`}>
            {badge.label}
          </span>
          {approval.mrUrl && (
            <a
              href={approval.mrUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 text-sm text-blue-600 hover:text-blue-800"
            >
              {approval.taskId}
              <ExternalLink className="w-3 h-3" />
            </a>
          )}
          {!approval.mrUrl && (
            <span className="text-sm text-gray-600">{approval.taskId}</span>
          )}
        </div>
        <div className="text-right text-sm">
          <div className="text-gray-600">{formatDuration(new Date(approval.expiresAt.getTime() - 72 * 3600 * 1000))}</div>
          <div className={`${isExpired ? 'text-red-600 font-medium' : 'text-gray-500'}`}>
            {formatExpiration(approval.expiresAt)}
          </div>
        </div>
      </div>

      {/* Task Info */}
      <div className="mb-4">
        <h3 className="font-semibold text-lg text-gray-900 break-words">
          {approval.originalComment || approval.taskTitle}
        </h3>
        <p className="text-sm text-gray-600 mt-1">{approval.projectName} · Task {approval.taskId}</p>
      </div>

      {/* Type-Specific Content */}
      <div className="mb-6">
        {approval.approvalType === 'spec' && approval.spec && (
          <SpecReviewCard context={approval.spec} />
        )}
        {approval.approvalType === 'roborev' && approval.roborev && (
          <RoborevCard context={approval.roborev} />
        )}
        {approval.approvalType === 'post' && approval.response && (
          <ResponseCard context={approval.response} onResponseEdit={setEditedResponse} />
        )}
      </div>

      {/* Execution History */}
      <ExecutionHistory trace={trace} />

      {/* Actions */}
      <div className="mt-6 pt-6 border-t border-gray-200">
        {isExpired ? (
          <div className="text-center text-red-600 font-medium">
            This approval has expired
          </div>
        ) : (
          <ApprovalActions
            requestId={approval.requestId}
            showRequestChanges={approval.approvalType === 'post'}
            isSubmitting={isPending}
            onSubmit={handleSubmit}
          />
        )}
      </div>
    </div>
  );
}
