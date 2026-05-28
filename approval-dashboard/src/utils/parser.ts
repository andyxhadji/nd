import {
  ApprovalContext,
  ApprovalType,
  SpecReviewContext,
  RoborevContext,
  ResponseContext,
} from '../api/types';

/**
 * Parse AgentField execution details to extract approval context.
 * The data structure comes from /api/ui/v1/executions/{id}/details
 */
export function parseApprovalContext(data: any): ApprovalContext | null {
  const approval_request_id = data.approval_request_id;
  const approval_request_url = data.approval_request_url;

  if (!approval_request_id) {
    return null;
  }

  // Extract approval type and task ID from request ID
  // Format: "spec-{taskId}" | "roborev-{taskId}" | "post-{taskId}"
  const match = approval_request_id.match(/^(spec|roborev|post)-(.+)$/);
  if (!match) {
    console.warn('Invalid approval_request_id format:', approval_request_id);
    return null;
  }

  const approvalType = match[1] as ApprovalType;
  const taskId = match[2];

  // Calculate expiration (72 hours from approval request time)
  const requestedAt = data.approval_requested_at || data.started_at;
  const expiresAt = new Date(new Date(requestedAt).getTime() + 72 * 3600 * 1000);

  // Extract task context from input_data (process_task input)
  const input = data.input_data || {};
  const taskTitle = input.title || 'Unknown Task';
  const projectName = input.project || 'Unknown Project';
  const taskBody = input.body || '';

  // Parse task body to extract original comment
  const commentMatch = taskBody.match(/## Original Comment\n\*\*Author:\*\* [^\n]+\n\n(.*?)\n\n## Metadata/s);
  const originalComment = commentMatch ? commentMatch[1].trim() : 'No comment available';

  const baseContext: ApprovalContext = {
    approvalType,
    taskId,
    runId: data.workflow_id || data.run_id,
    requestId: approval_request_id,
    mrUrl: approval_request_url || undefined,
    expiresAt,
    originalComment,
    taskTitle,
    projectName,
  };

  // Add type-specific context (requires trace data which we'll fetch separately)
  // For now, these will be undefined and we'll enhance them later
  if (approvalType === 'spec') {
    baseContext.spec = parseSpecContext(data);
  } else if (approvalType === 'roborev') {
    baseContext.roborev = parseRoborevContext(data);
  } else if (approvalType === 'post') {
    baseContext.response = parseResponseContext(data);
  }

  return baseContext;
}

function parseSpecContext(_data: any): SpecReviewContext | undefined {
  // Would need to fetch the full trace from other executions
  // For now, return undefined - we'll enhance this later
  return undefined;

  // Extract analysis result from analyze_task
  // const analyzeCall = data.trace?.find((call: any) => call.name.endsWith('.analyze_task'));
  // const analysis = analyzeCall?.output as any;

  // Extract spec from plan_changes
  // const planCall = data.trace?.find((call: any) => call.name.endsWith('.plan_changes'));
  // const spec = planCall?.output as any;

  // if (!analysis || !spec) {
  //   return undefined;
  // }

  // return {
  //   confidence: (analysis.confidence as number) || 0,
  //   complexity: (analysis.complexity as 1 | 2 | 3 | 4 | 5) || 3,
  //   reasoning: (analysis.reasoning as string) || '',
  //   suggestedApproach: (analysis.suggested_approach as string) || '',
  //   filesLikelyAffected: (analysis.files_likely_affected as string[]) || [],
  //   spec: {
  //     summary: (spec.summary as string) || '',
  //     problemStatement: (spec.problem_statement as string) || '',
  //     proposedSolution: (spec.proposed_solution as string) || '',
  //     filesToModify: (spec.files_to_modify as string[]) || [],
  //     filesToCreate: (spec.files_to_create as string[]) || [],
  //     testingApproach: (spec.testing_approach as string) || '',
  //     risks: (spec.risks as string[]) || [],
  //     questions: (spec.questions as string[]) || [],
  //   },
  // };
}

function parseRoborevContext(_data: any): RoborevContext | undefined {
  // Would need to fetch the full trace from other executions
  return undefined;
}

function parseResponseContext(_data: any): ResponseContext | undefined {
  // Would need to fetch the full trace from other executions
  return undefined;
}
