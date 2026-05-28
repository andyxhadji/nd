import { useState, useEffect } from 'react';
import { Clock } from 'lucide-react';
import { useApprovals } from './hooks/useApprovals';
import { ConnectionStatus } from './components/ConnectionStatus';
import { ApprovalCard } from './components/ApprovalCard';
import { fetchRunDetails } from './api/agentfield';

type TabType = 'spec' | 'roborev' | 'post';

export default function App() {
  const { data: approvals, isLoading, isError, dataUpdatedAt } = useApprovals();
  const [activeTab, setActiveTab] = useState<TabType>('spec');
  const [traces, setTraces] = useState<Record<string, any[]>>({});

  // Fetch full traces for each approval
  useEffect(() => {
    if (!approvals) return;

    approvals.forEach(async (approval) => {
      if (!traces[approval.runId]) {
        try {
          const run = await fetchRunDetails(approval.runId);
          setTraces((prev) => ({ ...prev, [approval.runId]: run.trace }));
        } catch (error) {
          console.error(`Failed to fetch trace for ${approval.runId}:`, error);
        }
      }
    });
  }, [approvals]);

  const filteredApprovals = approvals?.filter((a) => a.approvalType === activeTab) || [];

  const specCount = approvals?.filter((a) => a.approvalType === 'spec').length || 0;
  const roborevCount = approvals?.filter((a) => a.approvalType === 'roborev').length || 0;
  const postCount = approvals?.filter((a) => a.approvalType === 'post').length || 0;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold text-gray-900">AgentField Approvals</h1>
            <ConnectionStatus
              isConnected={!isError}
              isLoading={isLoading}
              lastUpdate={dataUpdatedAt ? new Date(dataUpdatedAt) : undefined}
            />
          </div>
        </div>
      </header>

      {/* Tabs */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <nav className="flex gap-8">
            <TabButton
              active={activeTab === 'spec'}
              count={specCount}
              onClick={() => setActiveTab('spec')}
            >
              Spec Reviews
            </TabButton>
            <TabButton
              active={activeTab === 'roborev'}
              count={roborevCount}
              onClick={() => setActiveTab('roborev')}
            >
              Roborev Failures
            </TabButton>
            <TabButton
              active={activeTab === 'post'}
              count={postCount}
              onClick={() => setActiveTab('post')}
            >
              Response Approvals
            </TabButton>
          </nav>
        </div>
      </div>

      {/* Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {isError && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
            <p className="text-red-800 font-medium">Connection lost. Retrying...</p>
            <p className="text-red-600 text-sm mt-2">
              Make sure AgentField is running at http://localhost:8081
            </p>
          </div>
        )}

        {isLoading && !approvals && (
          <div className="flex items-center justify-center py-12">
            <Clock className="w-6 h-6 text-gray-400 animate-spin" />
            <span className="ml-2 text-gray-600">Loading approvals...</span>
          </div>
        )}

        {!isLoading && !isError && filteredApprovals.length === 0 && (
          <div className="text-center py-12">
            <p className="text-gray-600 text-lg">No pending {activeTab} approvals</p>
            <p className="text-gray-500 text-sm mt-2">
              Approvals will appear here when nd worker pauses for review
            </p>
          </div>
        )}

        {filteredApprovals.length > 0 && (
          <div className="space-y-6">
            {filteredApprovals.map((approval) => (
              <ApprovalCard
                key={approval.requestId}
                approval={approval}
                trace={traces[approval.runId] || []}
              />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}

interface TabButtonProps {
  active: boolean;
  count: number;
  onClick: () => void;
  children: React.ReactNode;
}

function TabButton({ active, count, onClick, children }: TabButtonProps) {
  return (
    <button
      onClick={onClick}
      className={`
        py-4 px-1 border-b-2 font-medium text-sm transition-colors
        ${active
          ? 'border-blue-600 text-blue-600'
          : 'border-transparent text-gray-600 hover:text-gray-900 hover:border-gray-300'
        }
      `}
    >
      {children}
      {count > 0 && (
        <span
          className={`
            ml-2 px-2 py-0.5 rounded-full text-xs
            ${active ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-700'}
          `}
        >
          {count}
        </span>
      )}
    </button>
  );
}
