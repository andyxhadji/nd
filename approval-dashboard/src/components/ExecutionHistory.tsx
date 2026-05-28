import { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { ReasonerCall } from '../api/types';

interface ExecutionHistoryProps {
  trace: ReasonerCall[];
}

export function ExecutionHistory({ trace }: ExecutionHistoryProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className="border-t border-gray-200 pt-4">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center gap-2 text-sm font-medium text-gray-700 hover:text-gray-900"
      >
        {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
        Execution History ({trace.length} calls)
      </button>

      {isExpanded && (
        <div className="mt-4 space-y-2">
          {trace.map((call, index) => (
            <TraceItem key={index} call={call} index={index} />
          ))}
        </div>
      )}
    </div>
  );
}

function TraceItem({ call, index }: { call: ReasonerCall; index: number }) {
  const [showInput, setShowInput] = useState(false);
  const [showOutput, setShowOutput] = useState(false);

  return (
    <div className="border border-gray-200 rounded-md p-3 bg-gray-50">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-xs font-mono text-gray-500">#{index + 1}</span>
          <span className="font-medium text-sm">{call.name}</span>
          <span className="text-xs text-gray-500">{call.duration_ms}ms</span>
        </div>
        <span className="text-xs text-gray-400">
          {new Date(call.timestamp).toLocaleTimeString()}
        </span>
      </div>

      <div className="mt-2 flex gap-2">
        <button
          onClick={() => setShowInput(!showInput)}
          className="text-xs text-blue-600 hover:text-blue-800 underline"
        >
          {showInput ? 'Hide' : 'Show'} Input
        </button>
        <button
          onClick={() => setShowOutput(!showOutput)}
          className="text-xs text-blue-600 hover:text-blue-800 underline"
        >
          {showOutput ? 'Hide' : 'Show'} Output
        </button>
      </div>

      {showInput && (
        <pre className="mt-2 p-2 bg-white border border-gray-200 rounded text-xs overflow-x-auto">
          {JSON.stringify(call.input, null, 2)}
        </pre>
      )}

      {showOutput && (
        <pre className="mt-2 p-2 bg-white border border-gray-200 rounded text-xs overflow-x-auto">
          {JSON.stringify(call.output, null, 2)}
        </pre>
      )}
    </div>
  );
}
