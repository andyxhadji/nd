import { useState } from 'react';
import { FileCode, Copy, Check, ExternalLink, ChevronDown, ChevronRight } from 'lucide-react';
import { ResponseContext } from '../api/types';

interface ResponseCardProps {
  context: ResponseContext;
  onResponseEdit: (newText: string) => void;
}

export function ResponseCard({ context, onResponseEdit }: ResponseCardProps) {
  const [copied, setCopied] = useState(false);
  const [showComment, setShowComment] = useState(false);
  const [responseText, setResponseText] = useState(context.draftResponse);

  const copyCommitSha = () => {
    navigator.clipboard.writeText(context.commitSha);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleResponseChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const newText = e.target.value;
    setResponseText(newText);
    onResponseEdit(newText);
  };

  return (
    <div className="space-y-4">
      {/* Draft Response (Editable) */}
      <div>
        <h4 className="font-medium text-sm text-gray-900 mb-2">Draft Response</h4>
        <textarea
          value={responseText}
          onChange={handleResponseChange}
          className="w-full px-3 py-2 border border-gray-300 rounded-md resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm"
          rows={8}
        />
        <p className="text-xs text-gray-500 mt-1">
          Edited text will be sent as feedback with the approval.
        </p>
      </div>

      {/* Files Changed */}
      <div>
        <h4 className="font-medium text-sm text-gray-900 mb-2 flex items-center gap-1">
          <FileCode className="w-4 h-4" />
          Files Changed ({context.filesChanged.length})
        </h4>
        <div className="flex flex-wrap gap-1">
          {context.filesChanged.map((file, i) => (
            <span key={i} className="px-2 py-1 bg-gray-100 text-gray-800 text-xs rounded font-mono">
              {file}
            </span>
          ))}
        </div>
      </div>

      {/* Commit SHA */}
      <div>
        <h4 className="font-medium text-sm text-gray-900 mb-2">Commit SHA</h4>
        <div className="flex items-center gap-2">
          <code className="px-3 py-1 bg-gray-100 text-gray-800 text-xs rounded font-mono">
            {context.commitSha.substring(0, 8)}
          </code>
          <button
            onClick={copyCommitSha}
            className="p-1 hover:bg-gray-100 rounded"
            title="Copy full SHA"
          >
            {copied ? (
              <Check className="w-4 h-4 text-green-600" />
            ) : (
              <Copy className="w-4 h-4 text-gray-600" />
            )}
          </button>
        </div>
      </div>

      {/* MR/PR Link */}
      {context.mrUrl && (
        <div>
          <a
            href={context.mrUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm"
          >
            <ExternalLink className="w-4 h-4" />
            Preview in MR
          </a>
        </div>
      )}

      {/* Original Comment */}
      {context.originalComment && (
        <div>
          <button
            onClick={() => setShowComment(!showComment)}
            className="flex items-center gap-2 text-sm font-medium text-gray-700 hover:text-gray-900"
          >
            {showComment ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
            Original Comment
          </button>
          {showComment && (
            <div className="mt-2 p-3 bg-gray-50 border border-gray-200 rounded-md text-sm">
              <p className="whitespace-pre-wrap text-gray-700">{context.originalComment}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
