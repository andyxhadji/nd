import {
  AgentFieldRun,
  ApprovalContext,
  ApprovalType,
  SpecReviewContext,
  RoborevContext,
  ResponseContext,
} from '../api/types';

/**
 * Parse AgentField execution trace to extract approval context.
 */
export function parseApprovalContext(run: AgentFieldRun): ApprovalContext | null {
  if (!run.pauseContext) {
    return null;
  }

  const { approval_request_id, approval_request_url, expires_in_hours } = run.pauseContext;

  // Extract approval type and task ID from request ID
  // Format: "spec-{taskId}" | "roborev-{taskId}" | "post-{taskId}"
  const match = approval_request_id.match(/^(spec|roborev|post)-(.+)$/);
  if (!match) {
    console.warn('Invalid approval_request_id format:', approval_request_id);
    return null;
  }

  const approvalType = match[1] as ApprovalType;
  const taskId = match[2];

  // Calculate expiration
  const expiresAt = new Date(new Date(run.createdAt).getTime() + expires_in_hours * 3600 * 1000);

  // Extract common context from process_task input
  const processTaskCall = run.trace.find((call) => call.name.endsWith('.process_task'));
  const taskTitle = (processTaskCall?.input.title as string) || 'Unknown Task';
  const projectName = (processTaskCall?.input.project as string) || 'Unknown Project';
  const taskBody = (processTaskCall?.input.body as string) || '';

  // Parse task body to extract original comment
  const commentMatch = taskBody.match(/## Original Comment\n\*\*Author:\*\* [^\n]+\n\n(.*?)\n\n## Metadata/s);
  const originalComment = commentMatch ? commentMatch[1].trim() : 'No comment available';

  const baseContext: ApprovalContext = {
    approvalType,
    taskId,
    runId: run.runId,
    requestId: approval_request_id,
    mrUrl: approval_request_url || undefined,
    expiresAt,
    originalComment,
    taskTitle,
    projectName,
  };

  // Add type-specific context
  if (approvalType === 'spec') {
    baseContext.spec = parseSpecContext(run);
  } else if (approvalType === 'roborev') {
    baseContext.roborev = parseRoborevContext(run);
  } else if (approvalType === 'post') {
    baseContext.response = parseResponseContext(run);
  }

  return baseContext;
}

function parseSpecContext(run: AgentFieldRun): SpecReviewContext | undefined {
  // Extract analysis result from analyze_task
  const analyzeCall = run.trace.find((call) => call.name.endsWith('.analyze_task'));
  const analysis = analyzeCall?.output as any;

  // Extract spec from plan_changes
  const planCall = run.trace.find((call) => call.name.endsWith('.plan_changes'));
  const spec = planCall?.output as any;

  if (!analysis || !spec) {
    return undefined;
  }

  return {
    confidence: (analysis.confidence as number) || 0,
    complexity: (analysis.complexity as 1 | 2 | 3 | 4 | 5) || 3,
    reasoning: (analysis.reasoning as string) || '',
    suggestedApproach: (analysis.suggested_approach as string) || '',
    filesLikelyAffected: (analysis.files_likely_affected as string[]) || [],
    spec: {
      summary: (spec.summary as string) || '',
      problemStatement: (spec.problem_statement as string) || '',
      proposedSolution: (spec.proposed_solution as string) || '',
      filesToModify: (spec.files_to_modify as string[]) || [],
      filesToCreate: (spec.files_to_create as string[]) || [],
      testingApproach: (spec.testing_approach as string) || '',
      risks: (spec.risks as string[]) || [],
      questions: (spec.questions as string[]) || [],
    },
  };
}

function parseRoborevContext(run: AgentFieldRun): RoborevContext | undefined {
  // Extract execution result
  const executeCall = run.trace.find((call) => call.name.endsWith('.execute_changes'));
  const execution = executeCall?.output as any;

  // Extract roborev result
  const roborevCall = run.trace.find((call) => call.name.endsWith('.run_roborev'));
  const roborev = roborevCall?.output as any;

  if (!execution || !roborev) {
    return undefined;
  }

  // Extract original comment from process_task
  const processTaskCall = run.trace.find((call) => call.name.endsWith('.process_task'));
  const taskBody = (processTaskCall?.input.body as string) || '';
  const commentMatch = taskBody.match(/## Original Comment\n\*\*Author:\*\* [^\n]+\n\n(.*?)\n\n## Metadata/s);
  const originalComment = commentMatch ? commentMatch[1].trim() : '';

  return {
    filesChanged: (execution.files_changed as string[]) || [],
    commitSha: (execution.commit_sha as string) || '',
    iterations: (roborev.iterations as number) || 0,
    findings: (roborev.final_findings as string[]) || [],
    originalComment,
  };
}

function parseResponseContext(run: AgentFieldRun): ResponseContext | undefined {
  // Extract execution result
  const executeCall = run.trace.find((call) => call.name.endsWith('.execute_changes'));
  const execution = executeCall?.output as any;

  // Extract draft response
  const draftCall = run.trace.find((call) => call.name.endsWith('.draft_response'));
  const draft = draftCall?.output as any;

  if (!execution || !draft) {
    return undefined;
  }

  return {
    filesChanged: (execution.files_changed as string[]) || [],
    commitSha: (execution.commit_sha as string) || '',
    response: (draft.response as string) || '',
  };
}
