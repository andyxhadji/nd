import { useState } from 'react';
import { ChevronDown, ChevronRight, FileCode, AlertTriangle, HelpCircle } from 'lucide-react';
import { SpecReviewContext } from '../api/types';
import { getConfidenceColor } from '../utils/formatting';

interface SpecReviewCardProps {
  context: SpecReviewContext;
}

export function SpecReviewCard({ context }: SpecReviewCardProps) {
  const [showComment, setShowComment] = useState(false);

  const confidenceColor = getConfidenceColor(context.confidence);
  const complexityStars = '★'.repeat(context.complexity) + '☆'.repeat(5 - context.complexity);

  return (
    <div className="space-y-4">
      {/* Original Comment */}
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
            <p className="whitespace-pre-wrap text-gray-700">{context.reasoning}</p>
          </div>
        )}
      </div>

      {/* Analysis Metrics */}
      <div className="flex gap-4">
        <div>
          <span className={`inline-block px-3 py-1 rounded-full text-sm font-medium ${confidenceColor}`}>
            Confidence: {context.confidence}%
          </span>
        </div>
        <div>
          <span className="inline-block px-3 py-1 bg-purple-100 text-purple-800 rounded-full text-sm font-medium">
            Complexity: {complexityStars}
          </span>
        </div>
      </div>

      {/* Suggested Approach */}
      <div className="p-3 bg-blue-50 border-l-4 border-blue-400">
        <h4 className="font-medium text-sm text-blue-900 mb-1">Suggested Approach</h4>
        <p className="text-sm text-blue-800">{context.suggestedApproach}</p>
      </div>

      {/* Spec Document */}
      <div className="space-y-3">
        <div>
          <h4 className="font-medium text-sm text-gray-900 mb-1">Summary</h4>
          <p className="text-sm text-gray-700">{context.spec.summary}</p>
        </div>

        <div>
          <h4 className="font-medium text-sm text-gray-900 mb-1">Problem Statement</h4>
          <p className="text-sm text-gray-700">{context.spec.problemStatement}</p>
        </div>

        <div>
          <h4 className="font-medium text-sm text-gray-900 mb-1">Proposed Solution</h4>
          <p className="text-sm text-gray-700 whitespace-pre-wrap">{context.spec.proposedSolution}</p>
        </div>

        {/* Files */}
        <div>
          <h4 className="font-medium text-sm text-gray-900 mb-2 flex items-center gap-1">
            <FileCode className="w-4 h-4" />
            Files
          </h4>
          <div className="space-y-2">
            {context.spec.filesToModify.length > 0 && (
              <div>
                <span className="text-xs text-gray-600">To Modify:</span>
                <div className="flex flex-wrap gap-1 mt-1">
                  {context.spec.filesToModify.map((file, i) => (
                    <span key={i} className="px-2 py-1 bg-yellow-100 text-yellow-800 text-xs rounded">
                      {file}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {context.spec.filesToCreate.length > 0 && (
              <div>
                <span className="text-xs text-gray-600">To Create:</span>
                <div className="flex flex-wrap gap-1 mt-1">
                  {context.spec.filesToCreate.map((file, i) => (
                    <span key={i} className="px-2 py-1 bg-green-100 text-green-800 text-xs rounded">
                      {file}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Testing Approach */}
        <div>
          <h4 className="font-medium text-sm text-gray-900 mb-1">Testing Approach</h4>
          <p className="text-sm text-gray-700">{context.spec.testingApproach}</p>
        </div>

        {/* Risks */}
        {context.spec.risks.length > 0 && (
          <div>
            <h4 className="font-medium text-sm text-gray-900 mb-2 flex items-center gap-1">
              <AlertTriangle className="w-4 h-4 text-orange-600" />
              Risks
            </h4>
            <ul className="list-disc list-inside space-y-1">
              {context.spec.risks.map((risk, i) => (
                <li key={i} className="text-sm text-gray-700">{risk}</li>
              ))}
            </ul>
          </div>
        )}

        {/* Questions */}
        {context.spec.questions.length > 0 && (
          <div>
            <h4 className="font-medium text-sm text-gray-900 mb-2 flex items-center gap-1">
              <HelpCircle className="w-4 h-4 text-blue-600" />
              Questions
            </h4>
            <ul className="list-disc list-inside space-y-1">
              {context.spec.questions.map((question, i) => (
                <li key={i} className="text-sm text-gray-700">{question}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
