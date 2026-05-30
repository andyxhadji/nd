// AgentField API types

export interface AgentFieldRun {
  run_id: string;
  workflow_id: string;
  root_execution_id?: string;
  root_execution_status?: 'waiting' | 'running' | 'completed' | 'failed' | 'paused' | 'pending' | 'queued' | 'cancelled' | 'timeout';
  status: 'waiting' | 'running' | 'completed' | 'failed' | 'paused' | 'pending' | 'queued' | 'cancelled' | 'timeout';
  root_reasoner?: string;
  current_task?: string;
  display_name?: string;
  agent_id?: string;
  session_id?: string;
  actor_id?: string;
  started_at: string;
  latest_activity?: string;
  completed_at?: string;
  duration_ms?: number;
  total_executions?: number;
  max_depth?: number;
  active_executions?: number;
  terminal?: boolean;
  status_counts?: Record<string, number>;
  root_error_category?: string;
  root_error_message?: string;
  trace?: ReasonerCall[];
  pauseContext?: PauseContext;
}

export interface PauseContext {
  approval_request_id: string;
  approval_request_url: string;
  expires_in_hours: number;
  timeout: number;
}

export interface ReasonerCall {
  name: string;
  input: Record<string, unknown>;
  output: Record<string, unknown>;
  timestamp: string;
  duration_ms: number;
}

// Parsed approval context

export type ApprovalType = 'spec' | 'roborev' | 'post';

export interface ApprovalContext {
  approvalType: ApprovalType;
  taskId: string;
  runId: string;
  requestId: string;
  mrUrl?: string;
  expiresAt: Date;
  originalComment: string;
  taskTitle: string;
  projectName: string;
  spec?: SpecReviewContext;
  roborev?: RoborevContext;
  response?: ResponseContext;
}

export interface SpecReviewContext {
  confidence: number;
  complexity: 1 | 2 | 3 | 4 | 5;
  reasoning: string;
  suggestedApproach: string;
  filesLikelyAffected: string[];
  spec: {
    summary: string;
    problemStatement: string;
    proposedSolution: string;
    filesToModify: string[];
    filesToCreate: string[];
    testingApproach: string;
    risks: string[];
    questions: string[];
  };
}

export interface RoborevContext {
  passed: boolean;
  iterations: number;
  findings: string[];
  filesChanged: string[];
  commitSha: string;
  diff?: string;
}

export interface ResponseContext {
  draftResponse: string;
  filesChanged: string[];
  commitSha: string;
  originalComment: string;
  mrUrl: string;
}

// Approval webhook types

export type ApprovalDecision = 'approved' | 'rejected' | 'request_changes';

export interface ApprovalRequest {
  requestId: string;
  decision: ApprovalDecision;
  feedback?: string;
}

export interface ApprovalResponse {
  success: boolean;
  message?: string;
}
