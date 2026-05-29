import { useState } from 'react';
import { Check, X, MessageSquare } from 'lucide-react';
import { ApprovalDecision } from '../api/types';

interface ApprovalActionsProps {
  requestId: string;
  showRequestChanges?: boolean;
  isSubmitting: boolean;
  onSubmit: (decision: ApprovalDecision, feedback?: string) => void;
}

export function ApprovalActions({
  showRequestChanges = false,
  isSubmitting,
  onSubmit,
}: ApprovalActionsProps) {
  const [showFeedback, setShowFeedback] = useState(false);
  const [feedback, setFeedback] = useState('');

  const handleSubmit = (decision: ApprovalDecision) => {
    onSubmit(decision, feedback.trim() || undefined);
  };

  return (
    <div className="space-y-3">
      {showFeedback && (
        <textarea
          value={feedback}
          onChange={(e) => setFeedback(e.target.value)}
          placeholder="Optional feedback..."
          className="w-full px-3 py-2 border border-gray-300 rounded-md resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
          rows={3}
        />
      )}

      <div className="flex gap-2">
        <button
          onClick={() => handleSubmit('approved')}
          disabled={isSubmitting}
          className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
        >
          <Check className="w-4 h-4" />
          {isSubmitting ? 'Submitting...' : 'Approve'}
        </button>

        <button
          onClick={() => handleSubmit('rejected')}
          disabled={isSubmitting}
          className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
        >
          <X className="w-4 h-4" />
          Reject
        </button>

        {showRequestChanges && (
          <button
            onClick={() => handleSubmit('request_changes')}
            disabled={isSubmitting}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-yellow-600 text-white rounded-md hover:bg-yellow-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
          >
            <MessageSquare className="w-4 h-4" />
            Request Changes
          </button>
        )}
      </div>

      {!showFeedback && (
        <button
          onClick={() => setShowFeedback(true)}
          className="w-full text-sm text-gray-600 hover:text-gray-800 underline"
        >
          Add feedback
        </button>
      )}
    </div>
  );
}
