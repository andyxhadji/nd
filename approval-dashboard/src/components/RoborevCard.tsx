import { useState } from 'react';
import { FileCode, AlertCircle, Copy, Check, ChevronDown, ChevronRight } from 'lucide-react';
import { RoborevContext } from '../api/types';

interface RoborevCardProps {
  context: RoborevContext;
}

export function RoborevCard({ context }: RoborevCardProps) {
  const [copied, setCopied] = useState(false);
  const [showComment, setShowComment] = useState(false);

  const copyCommitSha = () => {
    navigator.clipboard.writeText(context.commitSha);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-4">
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

      {/* Roborev Findings */}
      <div>
        <h4 className="font-medium text-sm text-gray-900 mb-2 flex items-center gap-1">
          <AlertCircle className="w-4 h-4 text-orange-600" />
          Roborev Findings ({context.findings.length})
        </h4>
        <div className="p-3 bg-orange-50 border border-orange-200 rounded-md">
          <p className="text-xs text-orange-800 mb-2">
            After {context.iterations} iteration(s), these issues remain:
          </p>
          <div className="space-y-2">
            {context.findings.slice(0, 10).map((finding, i) => (
              <div key={i} className="p-2 bg-white border border-orange-200 rounded text-xs">
                <pre className="whitespace-pre-wrap font-mono text-gray-800">{finding}</pre>
              </div>
            ))}
            {context.findings.length > 10 && (
              <p className="text-xs text-orange-700">
                ...and {context.findings.length - 10} more finding(s)
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
