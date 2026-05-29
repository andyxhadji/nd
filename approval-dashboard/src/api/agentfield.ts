import { AgentFieldRun, ApprovalRequest, ApprovalResponse } from './types';
import { generateHmacSignature } from './hmac';

// Use relative URL - nginx will proxy /api/ to agentfield service
export const AGENTFIELD_URL = '';
export const WEBHOOK_SECRET = 'nd-approval-secret-dev';
export const POLL_INTERVAL_MS = 5000;
export const REQUEST_TIMEOUT_MS = 10000;

/**
 * Fetch all runs with status=waiting (approval gates) from AgentField.
 * Uses the /api/ui/v2/workflow-runs endpoint.
 *
 * Note: AgentField uses "waiting" status for executions paused for approval,
 * not "paused". The run overall shows as "running" but has child executions
 * with status="waiting" and status_reason="waiting_for_approval".
 */
export async function fetchWaitingRuns(): Promise<AgentFieldRun[]> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    // Query for runs with "running" status since the root execution continues
    // We'll need to check the DAG for child executions with status="waiting"
    const response = await fetch(
      `${AGENTFIELD_URL}/api/ui/v2/workflow-runs?page=1&page_size=50`,
      { signal: controller.signal }
    );

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const data = await response.json();
    // The API returns { workflows: [...], runs: [...], total_count, page, page_size, has_more }
    return Array.isArray(data.workflows) ? data.workflows : Array.isArray(data.runs) ? data.runs : [];
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') {
      throw new Error('Request timeout');
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }
}

/**
 * Fetch detailed run information including execution DAG.
 * Returns the DAG structure with all child executions.
 */
export async function fetchRunDetails(runId: string): Promise<any> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(
      `${AGENTFIELD_URL}/api/ui/v1/workflows/${runId}/dag`,
      { signal: controller.signal }
    );

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') {
      throw new Error('Request timeout');
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }
}

/**
 * Find all executions waiting for approval in a DAG.
 * Recursively searches for executions with status="waiting" and status_reason="waiting_for_approval".
 * Returns an array of execution_ids.
 */
export function findWaitingExecutions(dag: any): string[] {
  if (!dag) return [];

  const results: string[] = [];

  if (dag.status === 'waiting' && dag.status_reason === 'waiting_for_approval' && dag.execution_id) {
    results.push(dag.execution_id);
  }

  if (Array.isArray(dag.children)) {
    for (const child of dag.children) {
      results.push(...findWaitingExecutions(child));
    }
  }

  return results;
}

/**
 * Fetch execution details including approval context.
 */
export async function fetchExecutionDetails(executionId: string): Promise<any> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(
      `${AGENTFIELD_URL}/api/ui/v1/executions/${executionId}/details`,
      { signal: controller.signal }
    );

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') {
      throw new Error('Request timeout');
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }
}

/**
 * Send approval decision to AgentField with HMAC signature.
 */
export async function sendApproval(
  request: ApprovalRequest
): Promise<ApprovalResponse> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    // Stringify the request body once to ensure HMAC is computed over the exact same string
    const requestBody = JSON.stringify(request);
    const signature = await generateHmacSignature(WEBHOOK_SECRET, requestBody);

    const response = await fetch(
      `${AGENTFIELD_URL}/api/v1/webhooks/approval-response`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Hub-Signature-256': signature,
        },
        body: requestBody,
        signal: controller.signal,
      }
    );

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`HTTP ${response.status}: ${errorText}`);
    }

    return await response.json();
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') {
      throw new Error('Request timeout');
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }
}

/**
 * Trigger an agent reasoner via AgentField REST API.
 * Uses the /api/v1/execute/async endpoint to start reasoner execution.
 */
export async function triggerAgent(
  nodeId: string,
  reasonerId: string
): Promise<any> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 30000); // 30s timeout for agent calls

  try {
    const target = `${nodeId}.${reasonerId}`;
    const response = await fetch(
      `${AGENTFIELD_URL}/api/v1/execute/async/${target}`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          payload: null,
        }),
        signal: controller.signal,
      }
    );

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`HTTP ${response.status}: ${errorText}`);
    }

    const result = await response.json();
    if (!result.execution_id) {
      throw new Error('Invalid response: missing execution_id');
    }
    return result;
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') {
      throw new Error('Request timeout');
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }
}
