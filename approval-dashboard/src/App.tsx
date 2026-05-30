import { useState, useEffect } from 'react';
import { Clock, Play } from 'lucide-react';
import { useApprovals } from './hooks/useApprovals';
import { useGroupedApprovals } from './hooks/useGroupedApprovals';
import { ConnectionStatus } from './components/ConnectionStatus';
import { ApprovalCard } from './components/ApprovalCard';
import { GroupedApprovalList } from './components/GroupedApprovalList';
import { fetchRunDetails, triggerAgent } from './api/agentfield';

type TabType = 'source' | 'spec' | 'roborev' | 'post' | 'control';

export default function App() {
  const { data: approvals, isLoading, isError, dataUpdatedAt } = useApprovals();
  const { data: groupedApprovals } = useGroupedApprovals();
  const [activeTab, setActiveTab] = useState<TabType>('source');
  const [traces, setTraces] = useState<Record<string, any[]>>({});
  const [triggering, setTriggering] = useState<Record<string, boolean>>({});

  // Fetch full traces for each approval
  useEffect(() => {
    if (!approvals) return;

    approvals.forEach(async (approval) => {
      if (!traces[approval.runId]) {
        try {
          const run = await fetchRunDetails(approval.runId);
          setTraces((prev) => ({ ...prev, [approval.runId]: run.trace || [] }));
        } catch (error) {
          console.error(`Failed to fetch trace for ${approval.runId}:`, error);
        }
      }
    });
  }, [approvals, traces]);

  const filteredApprovals = approvals?.filter((a) => a.approvalType === activeTab) || [];

  const specCount = approvals?.filter((a) => a.approvalType === 'spec').length || 0;
  const roborevCount = approvals?.filter((a) => a.approvalType === 'roborev').length || 0;
  const postCount = approvals?.filter((a) => a.approvalType === 'post').length || 0;

  const handleTriggerAgent = async (nodeId: string, reasonerId: string) => {
    const key = `${nodeId}.${reasonerId}`;
    setTriggering((prev) => ({ ...prev, [key]: true }));
    try {
      const result = await triggerAgent(nodeId, reasonerId);
      console.log(`Triggered ${key}:`, result);
      alert(`Successfully triggered ${nodeId}.${reasonerId}${result.execution_id ? `\nExecution ID: ${result.execution_id}` : ''}`);
    } catch (error) {
      console.error(`Failed to trigger ${key}:`, error);
      alert(`Failed to trigger ${nodeId}.${reasonerId}: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setTriggering((prev) => ({ ...prev, [key]: false }));
    }
  };

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
              active={activeTab === 'source'}
              count={groupedApprovals?.length || 0}
              onClick={() => setActiveTab('source')}
            >
              By Source
            </TabButton>
            <TabButton
              active={activeTab === 'control'}
              count={0}
              onClick={() => setActiveTab('control')}
            >
              Agent Control
            </TabButton>
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

        {activeTab === 'source' && (
          <GroupedApprovalList groups={groupedApprovals || []} />
        )}

        {activeTab === 'control' && (
          <div className="space-y-6">
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-xl font-semibold text-gray-900 mb-4">Triage Agent</h2>
              <p className="text-gray-600 mb-4">
                Poll for new MR comments and assigned issues, then create kata tasks for actionable items.
              </p>
              <div className="space-y-3">
                <TriggerButton
                  nodeId="nd-triage"
                  reasonerId="poll_issues"
                  label="Poll Issues"
                  description="Poll middleman for assigned issues"
                  onTrigger={handleTriggerAgent}
                  isTriggering={triggering['nd-triage.poll_issues']}
                />
                <TriggerButton
                  nodeId="nd-triage"
                  reasonerId="poll_comments"
                  label="Poll Comments"
                  description="Poll middleman for MR comments"
                  onTrigger={handleTriggerAgent}
                  isTriggering={triggering['nd-triage.poll_comments']}
                />
              </div>
            </div>

            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-xl font-semibold text-gray-900 mb-4">Worker Agent</h2>
              <p className="text-gray-600 mb-4">
                Claim tasks from kata and process them (analyze, execute, validate, post response).
              </p>
              <div className="space-y-3">
                <TriggerButton
                  nodeId="nd-worker"
                  reasonerId="claim_task"
                  label="Claim Task"
                  description="Claim and process a task from kata"
                  onTrigger={handleTriggerAgent}
                  isTriggering={triggering['nd-worker.claim_task']}
                />
              </div>
            </div>
          </div>
        )}

        {activeTab !== 'control' && activeTab !== 'source' && isLoading && !approvals && (
          <div className="flex items-center justify-center py-12">
            <Clock className="w-6 h-6 text-gray-400 animate-spin" />
            <span className="ml-2 text-gray-600">Loading approvals...</span>
          </div>
        )}

        {activeTab !== 'control' && activeTab !== 'source' && !isLoading && !isError && filteredApprovals.length === 0 && (
          <div className="text-center py-12">
            <p className="text-gray-600 text-lg">No pending {activeTab} approvals</p>
            <p className="text-gray-500 text-sm mt-2">
              Approvals will appear here when nd worker pauses for review
            </p>
          </div>
        )}

        {activeTab !== 'control' && activeTab !== 'source' && filteredApprovals.length > 0 && (
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

interface TriggerButtonProps {
  nodeId: string;
  reasonerId: string;
  label: string;
  description: string;
  onTrigger: (nodeId: string, reasonerId: string) => Promise<void>;
  isTriggering?: boolean;
}

function TriggerButton({ nodeId, reasonerId, label, description, onTrigger, isTriggering }: TriggerButtonProps) {
  return (
    <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
      <div className="flex-1">
        <div className="font-medium text-gray-900">{label}</div>
        <div className="text-sm text-gray-600">{description}</div>
      </div>
      <button
        onClick={() => onTrigger(nodeId, reasonerId)}
        disabled={isTriggering}
        className={`
          flex items-center gap-2 px-4 py-2 rounded-md font-medium text-sm
          transition-colors
          ${isTriggering
            ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
            : 'bg-blue-600 text-white hover:bg-blue-700'
          }
        `}
      >
        <Play className="w-4 h-4" />
        {isTriggering ? 'Triggering...' : 'Trigger'}
      </button>
    </div>
  );
}

