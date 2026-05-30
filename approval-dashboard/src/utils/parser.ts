import {
  ApprovalContext,
  ApprovalType,
  SpecReviewContext,
  RoborevContext,
  ResponseContext,
} from '../api/types';
import { fetchExecutionDetails } from '../api/agentfield';

/**
 * Parse AgentField execution details to extract approval context.
 * The data structure comes from /api/ui/v1/executions/{id}/details
 */
export async function parseApprovalContext(data: any): Promise<ApprovalContext | null> {
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

  // Add type-specific context (requires fetching sibling execution details)
  if (approvalType === 'spec') {
    baseContext.spec = await parseSpecContext(data);
  } else if (approvalType === 'roborev') {
    baseContext.roborev = await parseRoborevContext(data);
  } else if (approvalType === 'post') {
    baseContext.response = await parseResponseContext(data);
  }

  return baseContext;
}

async function parseSpecContext(data: any): Promise<SpecReviewContext | undefined> {
  // Extract from the DAG - find analyze_task and plan_changes sibling executions
  if (!data.dag) return undefined;

  // Find the process_task execution (parent of waiting execution)
  const processTask = findExecutionInDAG(data.dag, data.execution_id);
  if (!processTask || !processTask.children) return undefined;

  // Find analyze_task execution
  const analyzeExec = processTask.children.find((child: any) =>
    child.reasoner_id === 'analyze_task' && child.status === 'succeeded'
  );

  // Find plan_changes execution
  const planExec = processTask.children.find((child: any) =>
    child.reasoner_id === 'plan_changes' && child.status === 'succeeded'
  );

  if (!analyzeExec || !planExec) return undefined;

  try {
    // Fetch execution details to get the result data
    const [analyzeDetails, planDetails] = await Promise.all([
      fetchExecutionDetails(analyzeExec.execution_id),
      fetchExecutionDetails(planExec.execution_id),
    ]);

    const analysis = analyzeDetails.output_data || {};
    const spec = planDetails.output_data || {};

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
  } catch (error) {
    console.error('Failed to fetch execution details for spec context:', error);
    return undefined;
  }
}

async function parseRoborevContext(data: any): Promise<RoborevContext | undefined> {
  // Extract roborev details from sibling executions in the DAG
  if (!data.dag) return undefined;

  // Find the process_task execution (parent of waiting execution)
  const processTask = findExecutionInDAG(data.dag, data.execution_id);
  if (!processTask || !processTask.children) return undefined;

  // Find run_roborev execution
  const roborevExec = processTask.children.find((child: any) =>
    child.reasoner_id === 'run_roborev' && child.status === 'succeeded'
  );

  // Find execute_changes execution
  const executeExec = processTask.children.find((child: any) =>
    child.reasoner_id === 'execute_changes' && child.status === 'succeeded'
  );

  if (!roborevExec) return undefined;

  try {
    // Fetch execution details to get the output_data
    const roborevDetails = await fetchExecutionDetails(roborevExec.execution_id);
    const executeDetails = executeExec ? await fetchExecutionDetails(executeExec.execution_id) : null;

    const roborevOutput = roborevDetails.output_data || {};

    return {
      passed: roborevOutput.passed || false,
      iterations: roborevOutput.iterations || 0,
      findings: roborevOutput.final_findings || [],
      filesChanged: executeDetails?.output_data?.files_changed || [],
      commitSha: executeDetails?.output_data?.commit_sha || '',
      diff: executeDetails?.output_data?.diff,
    };
  } catch (error) {
    console.error('Failed to fetch execution details for roborev context:', error);
    return undefined;
  }
}

async function parseResponseContext(data: any): Promise<ResponseContext | undefined> {
  // Extract response details from sibling executions in the DAG
  if (!data.dag) return undefined;

  // Find the process_task execution (parent of waiting execution)
  const processTask = findExecutionInDAG(data.dag, data.execution_id);
  if (!processTask || !processTask.children) return undefined;

  // Find draft_response execution
  const draftExec = processTask.children.find((child: any) =>
    child.reasoner_id === 'draft_response' && child.status === 'succeeded'
  );

  // Find execute_changes execution
  const executeExec = processTask.children.find((child: any) =>
    child.reasoner_id === 'execute_changes' && child.status === 'succeeded'
  );

  // Find publish_changes execution
  const publishExec = processTask.children.find((child: any) =>
    child.reasoner_id === 'publish_changes' && child.status === 'succeeded'
  );

  if (!draftExec) return undefined;

  // Fetch execution details to get the output_data
  try {
    const draftDetails = await fetchExecutionDetails(draftExec.execution_id);
    const executeDetails = executeExec ? await fetchExecutionDetails(executeExec.execution_id) : null;
    const publishDetails = publishExec ? await fetchExecutionDetails(publishExec.execution_id) : null;

    // Extract draft response text
    let draftResponse = draftDetails.output_data?.response_text || '';

    // Handle double-nested JSON (the response_text sometimes contains nested JSON)
    if (typeof draftResponse === 'string' && draftResponse.startsWith('{')) {
      try {
        const parsed = JSON.parse(draftResponse);
        if (parsed.message) {
          draftResponse = parsed.message;
        }
      } catch (e) {
        // Keep original if parsing fails
      }
    }

    return {
      draftResponse,
      filesChanged: executeDetails?.output_data?.files_changed || [],
      commitSha: executeDetails?.output_data?.commit_sha || '',
      originalComment: data.input_data?.body || '',
      mrUrl: publishDetails?.output_data?.merge_request_url || data.approval_request_url || '',
    };
  } catch (error) {
    console.error('Failed to fetch execution details for response context:', error);
    return undefined;
  }
}

function findExecutionInDAG(dag: any, executionId: string): any {
  if (!dag) return null;
  if (dag.execution_id === executionId) return dag;

  if (Array.isArray(dag.children)) {
    for (const child of dag.children) {
      const found = findExecutionInDAG(child, executionId);
      if (found) return found;
    }
  }

  return null;
}
