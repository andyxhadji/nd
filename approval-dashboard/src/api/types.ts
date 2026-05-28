// AgentField API types

export interface AgentFieldRun {
  runId: string;
  nodeId: string;
  status: 'waiting' | 'running' | 'completed' | 'failed';
  createdAt: string;
  updatedAt: string;
  trace: ReasonerCall[];
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
  filesChanged: string[];
  commitSha: string;
  iterations: number;
  findings: string[];
  originalComment: string;
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
