import { useState } from 'react';
import { DiffViewer } from './DiffViewer';
import { DiffTab } from '../api/types';

interface TabbedDiffViewerProps {
  combined: string;
  tabs: DiffTab[];
}

export function TabbedDiffViewer({ combined, tabs }: TabbedDiffViewerProps) {
  const [activeTab, setActiveTab] = useState<'combined' | number>('combined');

  const allTabs = [
    { id: 'combined' as const, label: 'Combined', diff: combined },
    ...tabs.map((tab, index) => ({ id: index, label: tab.label, diff: tab.diff })),
  ];

  const activeDiff = activeTab === 'combined'
    ? combined
    : tabs[activeTab as number]?.diff || '';

  if (tabs.length === 0 && !combined) {
    return (
      <div className="text-gray-500 text-sm p-4 border border-gray-200 rounded-md">
        No diffs available for this approval group.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {/* Tab Navigation */}
      <div className="flex gap-2 border-b border-gray-200">
        {allTabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`
              px-4 py-2 text-sm font-medium border-b-2 transition-colors
              ${activeTab === tab.id
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-600 hover:text-gray-900 hover:border-gray-300'
              }
            `}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Diff Content */}
      <div>
        {activeDiff ? (
          <DiffViewer diff={activeDiff} />
        ) : (
          <div className="text-gray-500 text-sm p-4">
            No diff available for this tab.
          </div>
        )}
      </div>
    </div>
  );
}
