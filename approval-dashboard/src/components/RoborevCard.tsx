import { useState } from 'react';
import { FileCode, AlertCircle, Copy, Check } from 'lucide-react';
import { RoborevContext } from '../api/types';
import { DiffViewer } from './DiffViewer';

interface RoborevCardProps {
  context: RoborevContext;
}

export function RoborevCard({ context }: RoborevCardProps) {
  const [copied, setCopied] = useState(false);

  const copyCommitSha = () => {
    navigator.clipboard.writeText(context.commitSha);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-4">
      {/* Review Status */}
      <div className="p-3 bg-orange-50 border border-orange-200 rounded-md">
        <div className="flex items-center gap-2">
          <AlertCircle className="w-5 h-5 text-orange-600" />
          <div>
            <p className="text-sm font-medium text-orange-900">
              Roborev failed after {context.iterations} iteration(s)
            </p>
            <p className="text-xs text-orange-700 mt-1">
              Review the changes and findings below to decide whether to approve or reject.
            </p>
          </div>
        </div>
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

      {/* Git Diff */}
      {context.diff && <DiffViewer diff={context.diff} />}

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
